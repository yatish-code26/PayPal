"""Automated Security & Hardening Tests for FreightGuard
Tests role-based access control, separation of duties, webhook signature verification,
replay deduplication, dynamic credential mode switching, and append-only audit logging.
"""
import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app, run_invoice_audit
from backend.config import WEBHOOK_LOCAL_HMAC_SECRET
from backend.seed_data import populate_seed_data
from backend.paypal_adapter import (
    set_runtime_paypal_credentials,
    reset_runtime_paypal_credentials,
    PayPalPayoutsAdapter,
)
from backend.database import get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db():
    populate_seed_data(reset=True)
    # Ensure credentials are reset
    reset_runtime_paypal_credentials()

def test_forged_webhook_rejected_with_401():
    """Any webhook request without valid signature must be rejected with 401."""
    fake_payload = {
        "id": "WH-FORGED-001",
        "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
        "resource": {"payout_item_id": "ITEM-123", "transaction_status": "SUCCESS"}
    }
    
    # 1. No headers
    res = client.post("/api/webhooks/paypal", json=fake_payload)
    assert res.status_code == 401
    assert "Webhook signature verification failed" in res.json()["detail"]

    # 2. Forged HMAC header
    headers = {"X-FreightGuard-Signature": "sha256=abcdef0123456789"}
    res2 = client.post("/api/webhooks/paypal", json=fake_payload, headers=headers)
    assert res2.status_code == 401

def test_valid_local_hmac_webhook_accepted_and_deduplicated():
    """Valid HMAC signed webhook is accepted, and replaying the same event is safely deduplicated."""
    payload = {
        "id": "WH-HMAC-VERIFIED-991",
        "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
        "summary": "Payout item completed",
        "resource": {
            "payout_item_id": "ITEM-991",
            "transaction_status": "SUCCESS"
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(
        WEBHOOK_LOCAL_HMAC_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    headers = {
        "X-FreightGuard-Signature": f"sha256={sig}",
        "Content-Type": "application/json"
    }

    # 1. Initial delivery
    res = client.post("/api/webhooks/paypal", content=raw_body, headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 2. Replay delivery (idempotency / deduplication)
    res_replay = client.post("/api/webhooks/paypal", content=raw_body, headers=headers)
    assert res_replay.status_code == 200
    assert "Deduplicated" in res_replay.json()["message"] or res_replay.json()["data"]["status"] == "ALREADY_PROCESSED"

def test_unauthorized_clerk_cannot_authorize_settlement():
    """An AP Clerk is prohibited from authorizing payouts (segregation of duties)."""
    # 1. Run audit first so invoice is in AUDITED_DISCREPANCY
    run_invoice_audit("INV-2025-88419")

    # 2. Login as AP Clerk
    login_res = client.post("/api/auth/login", json={"email": "clerk@freightguard.internal"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    # 3. Attempt to authorize settlement
    auth_headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "invoice_id": "INV-2025-88419",
        "first_approver": "clerk@freightguard.internal"
    }
    res = client.post("/api/settlements/authorize", json=payload, headers=auth_headers)
    assert res.status_code == 403
    assert "User role 'CLERK' is not authorized" in res.json()["detail"]

def test_approver_cannot_be_both_first_and_second_approver():
    """The two-approver rule strictly forbids the same individual from approving twice."""
    run_invoice_audit("INV-2025-88419")

    # Login as Sarah Chen (Approver 1)
    login_res = client.post("/api/auth/login", json={"email": "sarah.chen@shipper.internal"})
    token = login_res.json()["token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "invoice_id": "INV-2025-88419",
        "first_approver": "sarah.chen@shipper.internal",
        "second_approver": "sarah.chen@shipper.internal"
    }
    res = client.post("/api/settlements/authorize", json=payload, headers=auth_headers)
    assert res.status_code == 400
    assert "Segregation of duties violation" in res.json()["detail"]

def test_dynamic_paypal_mode_switching_and_masking():
    """Supplying sandbox keys at runtime switches adapter to LIVE_SANDBOX without persisting keys to disk."""
    adapter = PayPalPayoutsAdapter()
    assert adapter.mode() == "LOCAL_DEMO"

    try:
        # Set credentials
        set_runtime_paypal_credentials("sb-client-id-test-12345", "sb-secret-key-test-67890")
        assert adapter.mode() == "LIVE_SANDBOX"

        # Verify settings API masks secrets
        settings_res = client.get("/api/settings")
        assert settings_res.status_code == 200
        data = settings_res.json()
        assert data["paypal_mode"] == "LIVE_SANDBOX"
        assert "12345" in data["paypal_client_id_masked"] or "sb-cl" in data["paypal_client_id_masked"]
        # Secret must not be exposed in cleartext
        assert "sb-secret-key-test-67890" not in str(data)
    finally:
        # Clear credentials back to LOCAL_DEMO
        reset_runtime_paypal_credentials()
        assert adapter.mode() == "LOCAL_DEMO"

def test_append_only_audit_log_captures_lifecycle():
    """Every lifecycle transition creates an append-only audit record."""
    # Audit invoice
    run_invoice_audit("INV-2025-88419")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM audit_events WHERE entity_id = 'INV-2025-88419'")
        logs = cur.fetchall()
        assert len(logs) >= 1
        actions = [l["event_name"] for l in logs]
        assert "AUDIT_COMPLETED" in actions
