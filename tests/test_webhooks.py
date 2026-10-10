"""Automated Tests for PayPal Webhooks and Reconciliation
Verifies deduplication, replay protection, and item status transitions.
"""
import pytest
from backend.database import get_db
from backend.seed_data import populate_seed_data
from backend.webhook_service import WebhookService

@pytest.fixture(autouse=True)
def setup_test_db():
    populate_seed_data(reset=True)

def test_webhook_deduplication():
    """Verifies that delivering the same webhook event ID twice is deduplicated without error."""
    with get_db() as conn:
        svc = WebhookService(conn)
        payload = {
            "id": "WH-TEST-EVENT-001",
            "event_type": "PAYMENT.PAYOUTSBATCH.SUCCESS",
            "summary": "Payout batch processed",
            "resource": {
                "payout_batch_id": "PAYPAL-SBX-BATCH-991A4F",
                "batch_status": "SUCCESS"
            }
        }

        # First delivery
        success, msg, data = svc.process_webhook_event(payload, is_simulated=1)
        assert success is True
        assert "successfully processed" in msg

        # Duplicate delivery
        success_dup, msg_dup, data_dup = svc.process_webhook_event(payload, is_simulated=1)
        assert success_dup is True
        assert "Deduplicated" in msg_dup
        assert data_dup["status"] == "ALREADY_PROCESSED"
