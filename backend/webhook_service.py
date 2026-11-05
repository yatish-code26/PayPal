"""FreightGuard Webhook Service
Processes PayPal Payouts webhook events with strict deduplication,
item-level reconciliation, and deterministic state transitions.
"""
from typing import Dict, Any, Tuple
from datetime import datetime, timezone
import json
import sqlite3
from backend.database import record_audit_event

SUPPORTED_PAYOUT_EVENTS = {
    "PAYMENT.PAYOUTSBATCH.PROCESSING",
    "PAYMENT.PAYOUTSBATCH.SUCCESS",
    "PAYMENT.PAYOUTSBATCH.DENIED",
    "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
    "PAYMENT.PAYOUTS-ITEM.FAILED",
    "PAYMENT.PAYOUTS-ITEM.BLOCKED",
    "PAYMENT.PAYOUTS-ITEM.HELD",
    "PAYMENT.PAYOUTS-ITEM.UNCLAIMED"
}

class WebhookDuplicateException(Exception):
    """Raised when an identical webhook event has already been processed."""
    pass

class WebhookService:
    """Handles PayPal webhook validation, deduplication, and financial reconciliation."""

    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn

    def verify_signature(self, headers: Dict[str, str], raw_body: bytes, adapter=None) -> bool:
        """Verifies cryptographic or HMAC signature of the incoming webhook."""
        if adapter is None:
            from backend.paypal_adapter import PayPalPayoutsAdapter
            adapter = PayPalPayoutsAdapter()
        return adapter.verify_webhook_signature(headers, raw_body)

    def process_webhook_event(
        self,
        event_payload: Dict[str, Any],
        is_simulated: int = 1
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Processes an incoming PayPal webhook event idempotently.
        Returns: (success, message, reconciled_data)
        """
        event_id = event_payload.get("id")
        event_type = event_payload.get("event_type")
        summary = event_payload.get("summary", "")
        resource = event_payload.get("resource", {})
        now_str = datetime.now(timezone.utc).isoformat()

        if not event_id or not event_type:
            return (False, "Malformed webhook: Missing event id or event_type.", {})

        if event_type not in SUPPORTED_PAYOUT_EVENTS:
            return (False, f"Ignored unsupported event type: {event_type}", {})

        # 1. Deduplication check
        cur = self.conn.cursor()
        cur.execute("SELECT id, processed FROM webhook_events WHERE event_id = ?", (event_id,))
        existing = cur.fetchone()
        if existing:
            # Event already recorded
            return (True, f"Deduplicated: Event {event_id} already received and processed.", {"event_id": event_id, "status": "ALREADY_PROCESSED"})

        # Record incoming event in DB
        cur.execute(
            """INSERT INTO webhook_events (id, event_id, event_type, summary, resource_id, raw_payload_json, processed, is_simulated, received_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                f"wh_{event_id}",
                event_id,
                event_type,
                summary,
                resource.get("payout_batch_id") or resource.get("payout_item_id") or "UNKNOWN",
                json.dumps(event_payload),
                is_simulated,
                now_str
            )
        )

        reconciliation_info = {"event_id": event_id, "event_type": event_type}

        # 2. Correlate with Payout Records & Invoices
        if event_type.startswith("PAYMENT.PAYOUTS-ITEM."):
            # Item level event
            payout_item_id = resource.get("payout_item_id")
            transaction_status = resource.get("transaction_status")
            payout_batch_id = resource.get("payout_batch_id")

            # Look up payout record
            cur.execute(
                """SELECT pr.*, si.invoice_id FROM payout_records pr
                   JOIN settlement_intents si ON pr.settlement_intent_id = si.id
                   WHERE pr.paypal_item_id = ? OR pr.paypal_batch_id = ? LIMIT 1""",
                (payout_item_id, payout_batch_id)
            )
            payout_row = cur.fetchone()
            
            if payout_row:
                invoice_id = payout_row["invoice_id"]
                payout_id = payout_row["id"]

                new_item_status = "PENDING"
                new_invoice_settlement_status = "PAYOUT_INITIATED"

                if event_type == "PAYMENT.PAYOUTS-ITEM.SUCCEEDED":
                    new_item_status = "SUCCESS"
                    new_invoice_settlement_status = "RECONCILED"
                elif event_type == "PAYMENT.PAYOUTS-ITEM.FAILED":
                    new_item_status = "FAILED"
                    new_invoice_settlement_status = "PAYOUT_FAILED"
                elif event_type == "PAYMENT.PAYOUTS-ITEM.BLOCKED":
                    new_item_status = "BLOCKED"
                    new_invoice_settlement_status = "PAYOUT_BLOCKED"
                elif event_type == "PAYMENT.PAYOUTS-ITEM.HELD":
                    new_item_status = "HELD"
                    new_invoice_settlement_status = "PAYOUT_HELD"
                elif event_type == "PAYMENT.PAYOUTS-ITEM.UNCLAIMED":
                    new_item_status = "UNCLAIMED"
                    new_invoice_settlement_status = "PAYOUT_UNCLAIMED"

                # Update payout record
                cur.execute(
                    """UPDATE payout_records 
                       SET item_status = ?, updated_at = ?
                       WHERE id = ?""",
                    (new_item_status, now_str, payout_id)
                )

                # Update invoice status
                cur.execute(
                    """UPDATE invoices
                       SET settlement_status = ?, updated_at = ?
                       WHERE id = ?""",
                    (new_invoice_settlement_status, now_str, invoice_id)
                )

                record_audit_event(
                    self.conn,
                    "SETTLEMENT",
                    payout_id,
                    f"WEBHOOK_RECONCILED_{event_type}",
                    "WEBHOOK_SERVICE",
                    {
                        "event_id": event_id,
                        "item_status": new_item_status,
                        "invoice_settlement_status": new_invoice_settlement_status,
                        "is_simulated": bool(is_simulated)
                    }
                )

                reconciliation_info.update({
                    "payout_id": payout_id,
                    "invoice_id": invoice_id,
                    "item_status": new_item_status,
                    "settlement_status": new_invoice_settlement_status
                })

        elif event_type.startswith("PAYMENT.PAYOUTSBATCH."):
            batch_id = resource.get("payout_batch_id")
            batch_status = resource.get("batch_status") or ("SUCCESS" if "SUCCESS" in event_type else "DENIED")

            cur.execute(
                """UPDATE payout_records 
                   SET batch_status = ?, updated_at = ?
                   WHERE paypal_batch_id = ?""",
                (batch_status, now_str, batch_id)
            )

            record_audit_event(
                self.conn,
                "SETTLEMENT",
                batch_id or "BATCH",
                f"WEBHOOK_BATCH_{event_type}",
                "WEBHOOK_SERVICE",
                {"batch_id": batch_id, "batch_status": batch_status, "is_simulated": bool(is_simulated)}
            )

        return (True, f"Webhook {event_type} successfully processed and reconciled.", reconciliation_info)
