"""Automated Tests for FreightGuard Deterministic Financial Policy Engine
Verifies cents arithmetic, DOE diesel fuel formula, accounting invariants, and policy checks.
"""
import pytest
import decimal
from backend.policy_engine import (
    cents_to_dollars,
    dollars_to_cents,
    verify_accounting_invariant,
    calculate_fuel_surcharge,
    FinancialInvariantViolation
)

def test_cents_conversion_exactness():
    """Verifies that dollar string and decimal conversions have zero floating-point loss."""
    assert dollars_to_cents("2180.00") == 218000
    assert dollars_to_cents("3,342.00") == 334200
    assert dollars_to_cents("$5,522.00") == 552200
    assert dollars_to_cents("0.25") == 25
    assert cents_to_dollars(218000) == "2,180.00"
    assert cents_to_dollars(334200) == "3,342.00"
    assert cents_to_dollars(552200) == "5,522.00"

def test_accounting_invariant_reconciliation():
    """Verifies that original billed amount strictly equals payable + disputed + held."""
    # Signature demo: $5,522.00 = $3,342.00 + $2,180.00 + $0.00
    assert verify_accounting_invariant(
        total_billed_cents=552200,
        approved_payable_cents=334200,
        disputed_amount_cents=218000,
        held_amount_cents=0
    ) is True

def test_accounting_invariant_violation_raises():
    """Verifies that even a 1-cent discrepancy raises FinancialInvariantViolation."""
    with pytest.raises(FinancialInvariantViolation):
        # 1 cent off: 334201 instead of 334200
        verify_accounting_invariant(
            total_billed_cents=552200,
            approved_payable_cents=334201,
            disputed_amount_cents=218000,
            held_amount_cents=0
        )

def test_doe_fuel_surcharge_calculation():
    """Verifies DOE diesel surcharge formula:
    Baseline: $3.50/gal, Diesel price: $3.90/gal -> 4 steps @ 3.0% = 12.0% on $2,850.00 = $342.00 (34200 cents).
    """
    contracted_base = 285000 # $2,850.00
    diesel_price = decimal.Decimal("3.90")
    fsc_cents, fsc_rate, explanation = calculate_fuel_surcharge(contracted_base, diesel_price)
    
    assert fsc_cents == 34200
    assert fsc_rate == decimal.Decimal("0.120")
    assert "DOE National Diesel Index: $3.90" in explanation
