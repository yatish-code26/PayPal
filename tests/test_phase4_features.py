"""Automated Tests for FreightGuard Advanced Features
Verifies:
1. Pay now, hold the rest settlement split
2. Dispute resolution and held reserve release
3. Tamper-evident SHA-256 hash-chain verification
4. Carrier scorecards and renewal talking points
5. Ask FreightGuard grounded assistant
6. Pure-Python PDF dispute notice generation
7. Cross-invoice anomaly detection
"""
import pytest
from backend.seed_data import populate_seed_data
from backend.main import (
    run_invoice_audit,
    pay_now_hold_rest,
    resolve_dispute,
    verify_audit_trail_integrity,
    get_carrier_scorecards,
    chat_ask_freightguard,
    export_dispute_package_pdf,
    get_system_anomalies
)
from backend.models import SettlementPayoutRequest
from backend.database import get_db

@pytest.fixture(autouse=True)
def setup_test_db():
    populate_seed_data(reset=True)

def test_pay_now_hold_the_rest_settlement():
    """Verifies paying undisputed balance immediately and holding disputed funds in reserve."""
    # 1. Audit invoice INV-2025-88419 first
    run_invoice_audit("INV-2025-88419")

    # 2. Execute pay-now-hold-rest
    req = SettlementPayoutRequest(
        invoice_id="INV-2025-88419",
        idempotency_key="IDEM-TEST-HOLD-001"
    )
    res = pay_now_hold_rest(req)

    assert res["status"] == "SUCCESS"
    assert res["settlement_status"] == "PARTIALLY_SETTLED_HELD"
    assert res["paid_amount_cents"] == 334200   # $3,342.00
    assert res["held_amount_cents"] == 218000   # $2,180.00
    assert res["paypal_item_id"].startswith("PAYPAL-ITEM-")

    # Verify DB state
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT settlement_status, held_amount_cents, disputed_amount_cents FROM invoices WHERE id = 'INV-2025-88419'")
        inv = dict(cur.fetchone())
        assert inv["settlement_status"] == "PARTIALLY_SETTLED_HELD"
        assert inv["held_amount_cents"] == 218000
        assert inv["disputed_amount_cents"] == 0

def test_resolve_dispute_releases_held_reserve():
    """Verifies that carrier accepting dispute releases held funds and moves invoice to RECONCILED."""
    # Audit and split-settle invoice
    run_invoice_audit("INV-2025-88419")
    req = SettlementPayoutRequest(invoice_id="INV-2025-88419")
    pay_now_hold_rest(req)

    # Find dispute ID
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM disputes WHERE invoice_id = 'INV-2025-88419'")
        disp = cur.fetchone()
        dispute_id = disp["id"]

    # Resolve dispute
    res = resolve_dispute(dispute_id, {"credit_note_ref": "CN-TEST-9999"})
    assert res["status"] == "SUCCESS"
    assert res["new_status"] == "RESOLVED_CREDITED"

    # Verify invoice status is RECONCILED and held funds released
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT settlement_status, held_amount_cents FROM invoices WHERE id = 'INV-2025-88419'")
        inv = dict(cur.fetchone())
        assert inv["settlement_status"] == "RECONCILED"
        assert inv["held_amount_cents"] == 0

def test_tamper_evident_audit_chain_integrity():
    """Verifies cryptographic SHA-256 hash chaining across all logged events."""
    res = verify_audit_trail_integrity()
    assert res["chain_valid"] is True
    assert res["total_events"] > 0
    assert res["latest_hash"] is not None

def test_carrier_scorecards_generation():
    """Verifies carrier performance calculation and renewal talking points."""
    scorecards = get_carrier_scorecards()
    assert len(scorecards) >= 3

    # Check Apex Global Freight
    apex = next((sc for sc in scorecards if sc["scac"] == "AGFL"), None)
    assert apex is not None
    assert apex["total_invoices"] >= 1
    assert apex["overcharge_rate_pct"] > 0
    assert len(apex["talking_points"]) > 0

def test_ask_freightguard_chat_assistant():
    """Verifies natural-language Q&A grounded in database records."""
    res = chat_ask_freightguard({"question": "Why was invoice INV-2025-88419 disputed?"})
    assert "answer" in res
    assert len(res["answer"]) > 10
    assert "_ai" in res

def test_dispute_pdf_export_endpoint():
    """Verifies that dispute PDF export generates a valid PDF stream."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM disputes LIMIT 1")
        dispute_id = cur.fetchone()["id"]

    response = export_dispute_package_pdf(dispute_id)
    assert response.status_code == 200
    assert response.media_type == "application/pdf"
    assert response.body.startswith(b"%PDF-1.4")

def test_cross_invoice_anomalies_detection():
    """Verifies detection of duplicate shipment IDs and rate drift across invoices."""
    res = get_system_anomalies()
    assert "total_anomalies" in res
    assert "anomalies" in res
    assert res["total_anomalies"] >= 1
    # Duplicate shipment on BOL-99301 should be detected
    dup = next((a for a in res["anomalies"] if a["type"] == "DUPLICATE_SHIPMENT_BILLED"), None)
    assert dup is not None

