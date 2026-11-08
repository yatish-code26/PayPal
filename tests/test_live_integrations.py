"""FreightGuard Live Integration & Mocked HTTP Test Suite
Verifies OAuth, PayPal Sandbox Payouts, Webhook signature verification,
status polling/refresh fallback, and AI schema validation with fallback.
"""
import json
import io
import urllib.request
import urllib.error
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.main import app, run_invoice_audit
from backend.paypal_adapter import (
    PayPalPayoutsAdapter,
    PayPalAdapterException,
    set_runtime_paypal_credentials,
    reset_runtime_paypal_credentials,
)
from backend.ai_service import (
    extract_invoice,
    draft_dispute,
    explain_audit,
    set_runtime_keys,
    active_provider,
)
from backend.seed_data import populate_seed_data

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    populate_seed_data(reset=True)
    reset_runtime_paypal_credentials()
    set_runtime_keys(provider=None, groq_key=None, gemini_key=None, openai_key=None)
    yield
    reset_runtime_paypal_credentials()
    set_runtime_keys(provider=None, groq_key=None, gemini_key=None, openai_key=None)


# -----------------------------------------------------------------------------
# 1. PayPal OAuth2 Token Acquisition & Caching
# -----------------------------------------------------------------------------
def test_paypal_oauth_success_and_caching():
    set_runtime_paypal_credentials("test_client_id_123", "test_client_secret_456")
    adapter = PayPalPayoutsAdapter()
    assert adapter.mode() == "LIVE_SANDBOX"

    fake_token_response = json.dumps({
        "access_token": "MOCKED_LIVE_BEARER_TOKEN_999",
        "token_type": "Bearer",
        "expires_in": 3600
    }).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_token_response
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        # First call: acquires token from endpoint
        tok1 = adapter._acquire_oauth_token()
        assert tok1 == "MOCKED_LIVE_BEARER_TOKEN_999"
        assert mock_urlopen.call_count == 1

        # Second call: uses cached token without network call
        tok2 = adapter._acquire_oauth_token()
        assert tok2 == "MOCKED_LIVE_BEARER_TOKEN_999"
        assert mock_urlopen.call_count == 1


def test_paypal_oauth_failure_handling():
    set_runtime_paypal_credentials("bad_client_id", "bad_secret")
    adapter = PayPalPayoutsAdapter()

    error_resp = io.BytesIO(b'{"error": "invalid_client", "error_description": "Client Authentication failed"}')
    http_err = urllib.error.HTTPError("https://api-m.sandbox.paypal.com/v1/oauth2/token", 401, "Unauthorized", {}, error_resp)

    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(PayPalAdapterException) as exc_info:
            adapter._acquire_oauth_token(force_refresh=True)
        assert "PayPal OAuth Error (401)" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 2. PayPal Sandbox Payout Execution (Success & Failure)
# -----------------------------------------------------------------------------
def test_paypal_payout_success_stores_batch_and_item():
    set_runtime_paypal_credentials("test_client_id_123", "test_client_secret_456")
    adapter = PayPalPayoutsAdapter()

    fake_payout_response = json.dumps({
        "batch_header": {
            "payout_batch_id": "BATCH-MOCK-LIVE-888",
            "batch_status": "PROCESSING",
            "sender_batch_header": {"sender_batch_id": "SENDER-BATCH-01"}
        },
        "items": [
            {
                "payout_item_id": "ITEM-MOCK-LIVE-777",
                "transaction_status": "PENDING"
            }
        ]
    }).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_payout_response
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(adapter, "_acquire_oauth_token", return_value="FAKE_TOKEN"):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = adapter.create_payout(
                idempotency_key="IDEM-TEST-KEY-001",
                sender_batch_id="SENDER-BATCH-01",
                receiver_email="payee@example.com",
                amount_cents=334200,
                currency="USD"
            )
            assert res["is_simulated"] == 0
            assert res["batch_id"] == "BATCH-MOCK-LIVE-888"
            assert res["item_id"] == "ITEM-MOCK-LIVE-777"
            assert res["batch_status"] == "PROCESSING"


def test_paypal_payout_failure_raises_clear_error():
    set_runtime_paypal_credentials("test_client_id_123", "test_client_secret_456")
    adapter = PayPalPayoutsAdapter()

    err_body = io.BytesIO(b'{"name": "INSUFFICIENT_FUNDS", "message": "The sender has insufficient funds"}')
    http_err = urllib.error.HTTPError("https://api-m.sandbox.paypal.com/v1/payments/payouts", 400, "Bad Request", {}, err_body)

    with patch.object(adapter, "_acquire_oauth_token", return_value="FAKE_TOKEN"):
        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(PayPalAdapterException) as exc_info:
                adapter.create_payout(
                    idempotency_key="IDEM-FAIL-001",
                    sender_batch_id="SENDER-FAIL-01",
                    receiver_email="payee@example.com",
                    amount_cents=10000
                )
            assert "INSUFFICIENT_FUNDS" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 3. Duplicate Payout Prevention
# -----------------------------------------------------------------------------
def test_duplicate_payout_prevention():
    set_runtime_paypal_credentials(forced_mode="LOCAL_DEMO")
    run_invoice_audit("INV-2025-88419")

    # Authorize invoice first
    auth_res = client.post("/api/settlements/authorize", json={
        "invoice_id": "INV-2025-88419",
        "first_approver": "sarah.chen@shipper.internal",
        "second_approver": "david.ross@shipper.internal",
    })
    assert auth_res.status_code == 200

    # First payout execution
    res1 = client.post("/api/settlements/payout", json={
        "invoice_id": "INV-2025-88419",
        "idempotency_key": "IDEM-DUP-CHECK-999"
    })
    assert res1.status_code == 200
    assert "paypal_batch_id" in res1.json()

    # Second payout with same idempotency key is safely replayed
    res2 = client.post("/api/settlements/payout", json={
        "invoice_id": "INV-2025-88419",
        "idempotency_key": "IDEM-DUP-CHECK-999"
    })
    assert res2.status_code == 200
    assert res2.json().get("idempotent_replay") is True

    # Re-executing with a NEW idempotency key on an already-paid invoice is blocked by policy invariant
    res3 = client.post("/api/settlements/payout", json={
        "invoice_id": "INV-2025-88419",
        "idempotency_key": "IDEM-DIFFERENT-KEY-888"
    })
    assert res3.status_code == 409
    assert "already in state" in res3.json()["detail"]


# -----------------------------------------------------------------------------
# 4. Live Webhook Signature Verification & Fallback Refresh
# -----------------------------------------------------------------------------
def test_live_webhook_signature_verification_success():
    set_runtime_paypal_credentials("test_id", "test_sec", webhook_id="WH-LIVE-MOCK-ID")
    adapter = PayPalPayoutsAdapter()
    assert adapter.mode() == "LIVE_SANDBOX"

    fake_verify_resp = json.dumps({"verification_status": "SUCCESS"}).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_verify_resp
    mock_resp.__enter__.return_value = mock_resp

    headers = {
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-123",
        "PAYPAL-TRANSMISSION-ID": "trans_12345",
        "PAYPAL-TRANSMISSION-SIG": "sig_abcde",
        "PAYPAL-TRANSMISSION-TIME": "2026-11-08T12:00:00Z"
    }
    raw_body = b'{"id": "WH-EVT-001", "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED"}'

    with patch.object(adapter, "_acquire_oauth_token", return_value="TOKEN"):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            verified = adapter.verify_webhook_signature(headers, raw_body)
            assert verified is True


def test_live_webhook_signature_verification_rejection():
    set_runtime_paypal_credentials("test_id", "test_sec", webhook_id="WH-LIVE-MOCK-ID")
    adapter = PayPalPayoutsAdapter()

    fake_verify_resp = json.dumps({"verification_status": "FAILURE"}).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_verify_resp
    mock_resp.__enter__.return_value = mock_resp

    headers = {
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-123",
        "PAYPAL-TRANSMISSION-ID": "trans_12345",
        "PAYPAL-TRANSMISSION-SIG": "sig_invalid",
        "PAYPAL-TRANSMISSION-TIME": "2026-11-08T12:00:00Z"
    }
    raw_body = b'{"id": "WH-EVT-002", "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED"}'

    with patch.object(adapter, "_acquire_oauth_token", return_value="TOKEN"):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            verified = adapter.verify_webhook_signature(headers, raw_body)
            assert verified is False


def test_refresh_settlement_status_polling_fallback():
    set_runtime_paypal_credentials(forced_mode="LOCAL_DEMO")
    run_invoice_audit("INV-2025-88419")
    client.post("/api/settlements/authorize", json={
        "invoice_id": "INV-2025-88419",
        "first_approver": "sarah.chen@shipper.internal",
        "second_approver": "david.ross@shipper.internal",
    })
    client.post("/api/settlements/payout", json={
        "invoice_id": "INV-2025-88419",
        "idempotency_key": "IDEM-REFRESH-TEST-123"
    })

    # Poll status via refresh endpoint
    res = client.post("/api/settlements/INV-2025-88419/refresh-status")
    assert res.status_code == 200
    data = res.json()
    assert data["invoice_id"] == "INV-2025-88419"
    assert "batch_status" in data
    assert "item_status" in data


# -----------------------------------------------------------------------------
# 5. AI Live Mode & Fallback Integrity
# -----------------------------------------------------------------------------
def test_ai_live_mode_success():
    set_runtime_keys(provider="GROQ", groq_key="gsk_mock_live_api_key_123")
    assert active_provider() == "GROQ"

    mock_ai_json = json.dumps({
        "carrier_name": "Apex Global Freight Logistics",
        "invoice_number": "INV-2025-LIVE-01",
        "invoice_date": "2026-11-08",
        "shipment_reference": "BOL-99214",
        "currency": "USD",
        "total_billed_cents": 552200,
        "line_items": [
            {
                "line_number": 1,
                "charge_code": "LINEHAUL",
                "description": "Dry Van Linehaul",
                "billed_cents": 345000
            }
        ]
    })

    with patch("backend.ai_service._call_chat_completion", return_value=(True, mock_ai_json, None)):
        res = extract_invoice("Test raw freight bill text...")
        assert res["_ai"] == "GROQ"
        assert res["invoice_number"] == "INV-2025-LIVE-01"
        assert res["total_billed_cents"] == 552200


def test_ai_live_mode_error_falls_back():
    set_runtime_keys(provider="OPENAI", openai_key="sk_mock_failing_key")
    assert active_provider() == "OPENAI"

    with patch("backend.ai_service._call_chat_completion", return_value=(False, None, "503 Service Unavailable")):
        res = extract_invoice("Test raw invoice text...")
        assert "FALLBACK (OPENAI error" in res["_ai"]
        assert res["total_billed_cents"] > 0


def test_ai_cannot_decide_money_tampering_blocked():
    from backend.ai_service import verify_ai_financial_integrity

    # Exact server amount matches
    assert verify_ai_financial_integrity(
        original_billed_cents=552200,
        deterministic_payable_cents=334200,
        deterministic_disputed_cents=218000,
        ai_output={"approved_payable_cents": 334200, "disputed_amount_cents": 218000}
    ) is True

    # Tampered amount rejected
    assert verify_ai_financial_integrity(
        original_billed_cents=552200,
        deterministic_payable_cents=334200,
        deterministic_disputed_cents=218000,
        ai_output={"approved_payable_cents": 500000, "disputed_amount_cents": 52200}
    ) is False
