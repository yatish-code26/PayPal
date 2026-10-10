"""Automated Tests for FreightGuard Invoice Audit Engine
Tests the signature demo scenario ($2,180 discrepancy) and edge cases.
"""
import pytest
from backend.database import get_db, init_db
from backend.seed_data import populate_seed_data
from backend.main import run_invoice_audit, get_invoice_details

@pytest.fixture(autouse=True)
def setup_test_db():
    populate_seed_data(reset=True)

def test_signature_demo_invoice_audit_yields_exact_2180_discrepancy():
    """Verifies that running audit on INV-2025-88419 calculates exactly:
    - Total Billed: $5,522.00 (552,200¢)
    - Disputed Amount: $2,180.00 (218,000¢)
    - Approved Payable: $3,342.00 (334,200¢)
    - Sum: $3,342.00 + $2,180.00 = $5,522.00
    """
    res = run_invoice_audit("INV-2025-88419")
    
    assert res["invoice_id"] == "INV-2025-88419"
    assert res["total_billed_cents"] == 552200
    assert res["disputed_amount_cents"] == 218000
    assert res["approved_payable_cents"] == 334200
    assert res["reconciliation_valid"] is True
    assert res["audit_status"] == "AUDITED_DISCREPANCY"
    
    # Check individual findings
    findings = res["findings"]
    assert len(findings) == 4 # Base rate mismatch, fuel surcharge, unauthorized liftgate, duplicate congestion
    
    finding_types = [f["finding_type"] for f in findings]
    assert "RATE_MISMATCH" in finding_types
    assert "FUEL_OVERCHARGE" in finding_types
    assert "UNAUTHORIZED_ACCESSORIAL" in finding_types
    assert "DUPLICATE_CHARGE" in finding_types

    # Sum of variance in findings
    total_finding_variance = sum(f["variance_cents"] for f in findings)
    assert total_finding_variance == 218000 # Exactly $2,180.00!

def test_clean_invoice_audit_yields_zero_discrepancy():
    """Verifies that running audit on conforming invoice (INV-2025-77102) passes cleanly."""
    res = run_invoice_audit("INV-2025-77102")
    assert res["disputed_amount_cents"] == 0
    assert res["approved_payable_cents"] == 185000
    assert res["findings_count"] == 0
    assert res["audit_status"] == "AUDITED_CLEAN"
