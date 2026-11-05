"""Automated Tests for FreightGuard AI Layer
Tests BM25 contract clause ranking, AI invoice extraction, dispute drafting,
explain_audit, and financial boundary enforcement ("AI never decides money").
"""
import pytest
from backend.ai_service import (
    extract_invoice,
    draft_dispute,
    explain_audit,
    verify_ai_financial_integrity,
    active_provider,
    set_runtime_keys,
)
from backend.tariff_engine import TariffRAGEngine, bm25_rank
from backend.database import get_db
from backend.seed_data import populate_seed_data


@pytest.fixture(autouse=True)
def setup_db():
    populate_seed_data(reset=True)


def test_active_provider_defaults_to_local_deterministic():
    """With zero keys set, active_provider returns LOCAL_DETERMINISTIC."""
    set_runtime_keys(provider=None, groq_key=None, gemini_key=None, openai_key=None)
    assert active_provider() == "LOCAL_DETERMINISTIC"


def test_ai_extraction_offline_simulation():
    """Simulated extraction extracts invoice details and line items without external network."""
    sample_text = """
    INVOICE #INV-2025-99882
    Date: 2025-05-15
    Carrier: Apex Global Freight Logistics
    BOL: SH-884192
    Charges:
    Linehaul Transportation: $3,450.00
    Fuel Surcharge Pegged: $722.00
    Destination Liftgate: $350.00
    Detention at Origin: $150.00
    Congestion Surcharge: $850.00
    Total: $5,522.00
    """
    extracted = extract_invoice(sample_text)
    assert extracted["invoice_number"] == "INV-2025-99882"
    assert extracted["total_billed_cents"] == 552200
    assert len(extracted["line_items"]) == 5
    assert extracted["_ai"] == "LOCAL_DETERMINISTIC"


def test_bm25_contract_clause_ranking():
    """Tests local BM25 ranking over contract rules based on discrepancy queries."""
    with get_db() as conn:
        rag = TariffRAGEngine(conn)
        findings = [
            {"finding_type": "FUEL_OVERCHARGE", "clause_citation": "Clause 4.2", "explanation": "Fuel index discrepancy"}
        ]
        ranked = rag.rank_clauses_for_findings("AGF-MSA-2025-V2", findings)
        assert len(ranked) > 0
        # The top-ranked clause should be the FUEL clause
        assert ranked[0]["category"] == "FUEL"
        assert ranked[0]["bm25_score"] > 0


def test_ai_never_decides_money_invariant():
    """Policy blocks any AI output that attempts to modify server-calculated financial amounts."""
    # Legitimate matching amounts
    valid = verify_ai_financial_integrity(
        original_billed_cents=552200,
        deterministic_payable_cents=334200,
        deterministic_disputed_cents=218000,
        ai_output={
            "total_billed_cents": 552200,
            "approved_payable_cents": 334200,
            "disputed_amount_cents": 218000,
        }
    )
    assert valid is True

    # Tampered payable amount (AI attempts to approve more)
    tampered = verify_ai_financial_integrity(
        original_billed_cents=552200,
        deterministic_payable_cents=334200,
        deterministic_disputed_cents=218000,
        ai_output={
            "total_billed_cents": 552200,
            "approved_payable_cents": 400000, # TAMPERED!
            "disputed_amount_cents": 152200,
        }
    )
    assert tampered is False


def test_explain_audit_output():
    """Tests executive plain-English summary generation."""
    inv = {"invoice_number": "INV-2025-88419", "total_billed_cents": 552200, "approved_payable_cents": 334200}
    findings = [
        {"finding_type": "RATE_MISMATCH", "variance_cents": 60000, "explanation": "Off-tariff spot rate"},
        {"finding_type": "FUEL_OVERCHARGE", "variance_cents": 38000, "explanation": "Excessive fuel index"},
    ]
    explanation = explain_audit(inv, findings)
    assert "executive_summary" in explanation
    assert len(explanation["key_findings"]) >= 2
    assert "carrier_action_required" in explanation
    assert explanation["financial_defense_status"] == "DETERMINISTIC_INVARIANTS_ENFORCED"

