"""FreightGuard SQLite Database Module
Provides transactional database connection with WAL mode and foreign key enforcement.
"""
import sqlite3
import json
from contextlib import contextmanager
from typing import Generator
from backend.config import DB_PATH

def get_connection() -> sqlite3.Connection:
    """Creates a new SQLite connection with foreign keys and dict-like row factory."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite transactions with automatic commit/rollback."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db() -> None:
    """Initializes all database tables, indexes, and constraints."""
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS carriers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            scac TEXT,
            paypal_email TEXT NOT NULL,
            paypal_receiver_id TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contracts (
            id TEXT PRIMARY KEY,
            carrier_id TEXT NOT NULL REFERENCES carriers(id),
            title TEXT NOT NULL,
            effective_start TEXT NOT NULL,
            effective_end TEXT NOT NULL,
            version TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            document_text TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tariff_rules (
            id TEXT PRIMARY KEY,
            contract_id TEXT NOT NULL REFERENCES contracts(id),
            rule_code TEXT NOT NULL,
            category TEXT NOT NULL,
            clause_reference TEXT NOT NULL,
            rule_description TEXT NOT NULL,
            origin_zone TEXT,
            destination_zone TEXT,
            equipment_type TEXT,
            contracted_rate_cents INTEGER,
            formula_type TEXT,
            parameters_json TEXT
        );

        CREATE TABLE IF NOT EXISTS shipments (
            id TEXT PRIMARY KEY,
            carrier_id TEXT NOT NULL REFERENCES carriers(id),
            bol_number TEXT NOT NULL UNIQUE,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            pickup_time TEXT,
            delivery_time TEXT,
            dwell_time_minutes INTEGER DEFAULT 0,
            free_time_minutes INTEGER DEFAULT 120,
            weight_lbs INTEGER,
            dock_type TEXT,
            pre_authorized_accessorials_json TEXT,
            telematics_verified INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            carrier_id TEXT NOT NULL REFERENCES carriers(id),
            shipment_id TEXT REFERENCES shipments(id),
            invoice_number TEXT NOT NULL UNIQUE,
            invoice_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            currency TEXT DEFAULT 'USD',
            total_billed_cents INTEGER NOT NULL,
            expected_amount_cents INTEGER NOT NULL,
            disputed_amount_cents INTEGER NOT NULL DEFAULT 0,
            approved_payable_cents INTEGER NOT NULL DEFAULT 0,
            held_amount_cents INTEGER NOT NULL DEFAULT 0,
            audit_status TEXT NOT NULL,
            settlement_status TEXT NOT NULL DEFAULT 'UNSETTLED',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS invoice_items (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
            line_number INTEGER NOT NULL,
            charge_code TEXT NOT NULL,
            description TEXT NOT NULL,
            billed_cents INTEGER NOT NULL,
            expected_cents INTEGER NOT NULL,
            discrepancy_cents INTEGER NOT NULL,
            finding_status TEXT NOT NULL,
            rule_reference TEXT,
            explanation TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_findings (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
            item_id TEXT REFERENCES invoice_items(id),
            severity TEXT NOT NULL,
            finding_type TEXT NOT NULL,
            billed_cents INTEGER NOT NULL,
            permitted_cents INTEGER NOT NULL,
            variance_cents INTEGER NOT NULL,
            clause_citation TEXT NOT NULL,
            contract_version TEXT NOT NULL,
            telematics_evidence TEXT NOT NULL,
            calculation_steps_json TEXT NOT NULL,
            ai_confidence_score REAL NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS disputes (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL REFERENCES invoices(id),
            dispute_reference TEXT NOT NULL UNIQUE,
            carrier_id TEXT NOT NULL REFERENCES carriers(id),
            status TEXT NOT NULL,
            disputed_amount_cents INTEGER NOT NULL,
            carrier_contact_email TEXT NOT NULL,
            formal_letter_text TEXT NOT NULL,
            evidence_summary TEXT NOT NULL,
            response_deadline TEXT NOT NULL,
            credit_note_ref TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settlement_intents (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL REFERENCES invoices(id),
            idempotency_key TEXT NOT NULL UNIQUE,
            carrier_id TEXT NOT NULL REFERENCES carriers(id),
            approved_amount_cents INTEGER NOT NULL,
            held_amount_cents INTEGER NOT NULL,
            currency TEXT DEFAULT 'USD',
            receiver_email TEXT NOT NULL,
            first_approver TEXT NOT NULL,
            first_approved_at TEXT NOT NULL,
            second_approver TEXT,
            second_approved_at TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payout_records (
            id TEXT PRIMARY KEY,
            settlement_intent_id TEXT NOT NULL REFERENCES settlement_intents(id),
            invoice_id TEXT NOT NULL REFERENCES invoices(id),
            idempotency_key TEXT NOT NULL UNIQUE,
            paypal_batch_id TEXT,
            paypal_item_id TEXT,
            amount_cents INTEGER NOT NULL,
            currency TEXT DEFAULT 'USD',
            receiver_email TEXT NOT NULL,
            batch_status TEXT NOT NULL,
            item_status TEXT NOT NULL,
            paypal_fee_cents INTEGER DEFAULT 0,
            raw_paypal_response_json TEXT,
            is_simulated INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS webhook_events (
            id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            summary TEXT,
            resource_id TEXT,
            raw_payload_json TEXT NOT NULL,
            processed INTEGER DEFAULT 0,
            is_simulated INTEGER DEFAULT 1,
            received_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            event_name TEXT NOT NULL,
            actor TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_invoices_carrier ON invoices(carrier_id);
        CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(audit_status);
        CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
        CREATE INDEX IF NOT EXISTS idx_findings_invoice ON audit_findings(invoice_id);
        CREATE INDEX IF NOT EXISTS idx_settlement_invoice ON settlement_intents(invoice_id);
        CREATE INDEX IF NOT EXISTS idx_payout_intent ON payout_records(settlement_intent_id);
        CREATE INDEX IF NOT EXISTS idx_audit_events_entity ON audit_events(entity_id);
        """)

def record_audit_event(conn: sqlite3.Connection, entity_type: str, entity_id: str, event_name: str, actor: str, details: dict) -> None:
    """Helper to record an immutable audit event."""
    import uuid
    from datetime import datetime, timezone
    event_id = f"aud_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO audit_events (id, entity_type, entity_id, event_name, actor, details_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (event_id, entity_type, entity_id, event_name, actor, json.dumps(details), now)
    )
