"""Automated Tests for FreightGuard Settlement Controls and Financial Invariants
Verifies that prohibited payouts cannot bypass security rules.
"""
import pytest
from fastapi import HTTPException
from backend.seed_data import populate_seed_data
from backend.main import (
    authorize_settlement,
    execute_payout,
    run_invoice_audit
)
from backend.models import SettlementAuthorizeRequest, SettlementPayoutRequest

@pytest.fixture(autouse=True)
def setup_test_db():
    populate_seed_data(reset=True)

def test_cannot_authorize_un_audited_invoice():
    """Attempting to authorize an un-audited invoice raises 400 Bad Request."""
    req = SettlementAuthorizeRequest(
        invoice_id="INV-2025-88419", # Still PENDING_AUDIT
        first_approver="sarah.chen@shipper.internal"
    )
    with pytest.raises(HTTPException) as exc:
        authorize_settlement(req)
    assert exc.value.status_code == 400
    assert "audit has not been completed" in exc.value.detail

def test_cannot_authorize_blocked_duplicate_invoice():
    """Attempting to authorize a blocked invoice (INV-2025-99301) raises 400 Bad Request."""
    req = SettlementAuthorizeRequest(
        invoice_id="INV-2025-99301",
        first_approver="sarah.chen@shipper.internal"
    )
    with pytest.raises(HTTPException) as exc:
        authorize_settlement(req)
    assert exc.value.status_code == 400
    assert "BLOCKED" in exc.value.detail

def test_authorized_payout_execution_and_idempotency():
    """Audits invoice, authorizes settlement, executes payout, and verifies idempotency."""
    # 1. Audit invoice
    run_invoice_audit("INV-2025-88419")
    
    # 2. Authorize settlement
    auth_req = SettlementAuthorizeRequest(
        invoice_id="INV-2025-88419",
        first_approver="sarah.chen@shipper.internal",
        second_approver="david.ross@shipper.internal"
    )
    auth_res = authorize_settlement(auth_req)
    assert auth_res["status"] == "AUTHORIZED"
    idem_key = auth_res["idempotency_key"]

    # 3. Execute payout
    pay_req = SettlementPayoutRequest(
        invoice_id="INV-2025-88419",
        idempotency_key=idem_key,
        first_approver="sarah.chen@shipper.internal",
        second_approver="david.ross@shipper.internal"
    )
    pay_res = execute_payout(pay_req)
    assert pay_res["status"] == "SUCCESS"
    assert pay_res["amount_paid_formatted"] == "3,342.00"
    assert pay_res["paypal_batch_id"].startswith("PAYPAL-SBX-BATCH-")

    # 4. Attempt duplicate payout with same idempotency key
    replay_res = execute_payout(pay_req)
    assert replay_res.get("idempotent_replay") is True

    # 5. Attempt second payout with NEW key for already-paid invoice -> 409 Conflict
    pay_req_new_key = SettlementPayoutRequest(
        invoice_id="INV-2025-88419",
        idempotency_key="IDEM-NEW-KEY-ATTEMPT-DUPLICATE",
        first_approver="sarah.chen@shipper.internal"
    )
    with pytest.raises(HTTPException) as exc:
        execute_payout(pay_req_new_key)
    assert exc.value.status_code == 409
    assert "Duplicate payment prevented" in exc.value.detail
