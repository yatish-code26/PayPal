"""Automated Tests for Freight Financial Dashboard Reconciliation
Verifies that every dashboard figure derives from ONE single source of truth
in the SQLite database and that financial invariants hold to the exact cent.
"""
import pytest
from backend.seed_data import populate_seed_data
from backend.main import get_dashboard_stats
from backend.database import get_db

@pytest.fixture(autouse=True)
def setup_test_db():
    populate_seed_data(reset=True)

def test_dashboard_reconciles_to_exact_cent():
    """Invariant: total_billed = approved_payable + disputed_amount + held_amount in cents."""
    stats = get_dashboard_stats()

    billed = stats["total_billed_cents"]
    approved = stats["approved_payable_cents"]
    disputed = stats["disputed_amount_cents"]
    held = stats["held_amount_cents"]

    # Invariant check
    assert billed == approved + disputed + held, (
        f"Reconciliation failure: Billed {billed} != Approved {approved} + Disputed {disputed} + Held {held}"
    )
    assert stats["invariant_reconciles"] is True

def test_dashboard_initial_seed_values():
    """Verifies the exact seed figures match the accounting records."""
    stats = get_dashboard_stats()

    assert stats["total_invoices"] == 5
    assert stats["total_billed_cents"] == 1973400      # $19,734.00
    assert stats["approved_payable_cents"] == 1104200  # $11,042.00
    assert stats["disputed_amount_cents"] == 317000    # $3,170.00
    assert stats["held_amount_cents"] == 552200        # $5,522.00
    assert stats["total_billed_formatted"] == "19,734.00"

def test_database_individual_invoice_sum_matches_dashboard():
    """Verifies that summing the database rows directly equals get_dashboard_stats()."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                SUM(total_billed_cents) as b,
                SUM(approved_payable_cents) as a,
                SUM(disputed_amount_cents) as d,
                SUM(held_amount_cents) as h
            FROM invoices
        """)
        row = cur.fetchone()

        stats = get_dashboard_stats()
        assert stats["total_billed_cents"] == row["b"]
        assert stats["approved_payable_cents"] == row["a"]
        assert stats["disputed_amount_cents"] == row["d"]
        assert stats["held_amount_cents"] == row["h"]

def test_attention_queue_populated():
    """Verifies the operational attention queue returns structured actionable items."""
    stats = get_dashboard_stats()

    assert "invoices_to_review" in stats
    assert "disputes_awaiting_reply" in stats
    assert "payments_awaiting_approval" in stats

    assert isinstance(stats["invoices_to_review"], list)
    assert isinstance(stats["disputes_awaiting_reply"], list)
    assert isinstance(stats["payments_awaiting_approval"], list)

def test_recovered_only_counts_accepted_disputes():
    """Recovered funds must only be counted after carrier acceptance/resolution."""
    stats = get_dashboard_stats()
    # Initially no disputes are accepted, so recovered is 0
    assert stats["recovered_amount_cents"] == 0

