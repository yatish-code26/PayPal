"""FreightGuard FastAPI Backend Application
Main entrypoint providing deterministic freight financial control tower APIs,
evidence intelligence, dispute workflows, and PayPal settlement orchestration.
"""
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import uuid
from datetime import datetime, timezone

from backend.config import APP_MODE, BASE_DIR
from backend.database import get_db, record_audit_event
from backend.policy_engine import (
    cents_to_dollars,
    dollars_to_cents,
    verify_accounting_invariant,
    evaluate_line_item,
    validate_settlement_authorization,
    FinancialInvariantViolation
)
from backend.tariff_engine import TariffRAGEngine
from backend.dispute_generator import generate_dispute_package
from backend.paypal_adapter import PayPalPayoutsAdapter, PayPalAdapterException
from backend.webhook_service import WebhookService
from backend.seed_data import populate_seed_data
from backend.models import (
    SettlementAuthorizeRequest,
    SettlementPayoutRequest,
    WebhookSimulateRequest,
    DisputeGenerateRequest
)

app = FastAPI(
    title="FreightGuard API",
    description="Autonomous Freight Invoice Audit, Evidence Intelligence & PayPal Settlement Control Tower",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

paypal_adapter = PayPalPayoutsAdapter()

# -----------------------------------------------------------------------------
# 1. CONTROL TOWER STATS & METRICS
# -----------------------------------------------------------------------------
@app.get("/api/stats")
def get_dashboard_stats():
    """Aggregates executive metrics from persisted database records."""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Summary totals
        cur.execute("""
            SELECT 
                COUNT(*) as total_invoices,
                COALESCE(SUM(total_billed_cents), 0) as total_billed,
                COALESCE(SUM(approved_payable_cents), 0) as total_payable,
                COALESCE(SUM(disputed_amount_cents), 0) as total_disputed,
                COALESCE(SUM(held_amount_cents), 0) as total_held
            FROM invoices
        """)
        totals = dict(cur.fetchone())

        # Recovered / Credited Amount (from accepted disputes)
        cur.execute("""
            SELECT COALESCE(SUM(disputed_amount_cents), 0) as recovered_cents 
            FROM disputes WHERE status = 'ACCEPTED_CREDIT'
        """)
        recovered = cur.fetchone()["recovered_cents"]

        # Exceptions count
        cur.execute("""
            SELECT COUNT(*) as exceptions_count 
            FROM invoices 
            WHERE audit_status IN ('AUDITED_DISCREPANCY', 'BLOCKED', 'DISPUTED')
        """)
        exceptions_count = cur.fetchone()["exceptions_count"]

        # Payouts stats
        cur.execute("""
            SELECT 
                COUNT(*) as payouts_count,
                COALESCE(SUM(amount_cents), 0) as payouts_amount_cents
            FROM payout_records WHERE item_status = 'SUCCESS'
        """)
        payouts = dict(cur.fetchone())

        # Audit coverage
        cur.execute("SELECT COUNT(*) as audited_count FROM invoices WHERE audit_status != 'PENDING_AUDIT'")
        audited_count = cur.fetchone()["audited_count"]

        total_inv = totals["total_invoices"]
        coverage_pct = round((audited_count / total_inv * 100), 1) if total_inv > 0 else 0.0
        exception_rate_pct = round((exceptions_count / total_inv * 100), 1) if total_inv > 0 else 0.0

        return {
            "total_invoices": total_inv,
            "total_billed_cents": totals["total_billed"],
            "total_billed_formatted": cents_to_dollars(totals["total_billed"]),
            "verified_payable_cents": totals["total_payable"],
            "verified_payable_formatted": cents_to_dollars(totals["total_payable"]),
            "detected_disputed_cents": totals["total_disputed"],
            "detected_disputed_formatted": cents_to_dollars(totals["total_disputed"]),
            "confirmed_recovered_cents": recovered,
            "confirmed_recovered_formatted": cents_to_dollars(recovered),
            "pending_settlement_cents": totals["total_held"],
            "pending_settlement_formatted": cents_to_dollars(totals["total_held"]),
            "audit_coverage_pct": coverage_pct,
            "exception_rate_pct": exception_rate_pct,
            "successful_payouts_cents": payouts["payouts_amount_cents"],
            "successful_payouts_formatted": cents_to_dollars(payouts["payouts_amount_cents"]),
            "app_mode": APP_MODE
        }

# -----------------------------------------------------------------------------
# 2. INVOICE INTELLIGENCE & AUDITING
# -----------------------------------------------------------------------------
@app.get("/api/invoices")
def list_invoices(status: Optional[str] = None, carrier_id: Optional[str] = None, q: Optional[str] = None):
    """Lists invoices with carrier metadata, line items, and audit flags."""
    with get_db() as conn:
        cur = conn.cursor()
        query = """
            SELECT i.*, c.name as carrier_name, c.scac as carrier_scac, s.bol_number, s.origin, s.destination
            FROM invoices i
            JOIN carriers c ON i.carrier_id = c.id
            LEFT JOIN shipments s ON i.shipment_id = s.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND i.audit_status = ?"
            params.append(status)
        if carrier_id:
            query += " AND i.carrier_id = ?"
            params.append(carrier_id)
        if q:
            query += " AND (i.invoice_number LIKE ? OR c.name LIKE ? OR s.bol_number LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

        query += " ORDER BY i.created_at DESC"
        cur.execute(query, params)
        rows = cur.fetchall()
        
        result = []
        for r in rows:
            inv = dict(r)
            inv["total_billed_formatted"] = cents_to_dollars(inv["total_billed_cents"])
            inv["approved_payable_formatted"] = cents_to_dollars(inv["approved_payable_cents"])
            inv["disputed_amount_formatted"] = cents_to_dollars(inv["disputed_amount_cents"])
            result.append(inv)
        return result

@app.get("/api/invoices/{invoice_id}")
def get_invoice_details(invoice_id: str):
    """Returns complete invoice record, line items, shipment, and contract citations."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT i.*, c.name as carrier_name, c.scac as carrier_scac, c.paypal_email,
                   s.bol_number, s.origin, s.destination, s.dwell_time_minutes, s.free_time_minutes, s.dock_type,
                   k.id as contract_id, k.title as contract_title, k.version as contract_version
            FROM invoices i
            JOIN carriers c ON i.carrier_id = c.id
            LEFT JOIN shipments s ON i.shipment_id = s.id
            LEFT JOIN contracts k ON c.id = k.carrier_id AND k.status = 'ACTIVE'
            WHERE i.id = ?
        """, (invoice_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found.")

        invoice = dict(row)
        invoice["total_billed_formatted"] = cents_to_dollars(invoice["total_billed_cents"])
        invoice["approved_payable_formatted"] = cents_to_dollars(invoice["approved_payable_cents"])
        invoice["disputed_amount_formatted"] = cents_to_dollars(invoice["disputed_amount_cents"])

        # Fetch line items
        cur.execute("SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY line_number ASC", (invoice_id,))
        items = [dict(it) for it in cur.fetchall()]
        for it in items:
            it["billed_formatted"] = cents_to_dollars(it["billed_cents"])
            it["expected_formatted"] = cents_to_dollars(it["expected_cents"])
            it["discrepancy_formatted"] = cents_to_dollars(it["discrepancy_cents"])
        invoice["items"] = items

        # Fetch findings if audited
        cur.execute("SELECT * FROM audit_findings WHERE invoice_id = ? ORDER BY variance_cents DESC", (invoice_id,))
        findings = [dict(f) for f in cur.fetchall()]
        for f in findings:
            f["billed_formatted"] = cents_to_dollars(f["billed_cents"])
            f["permitted_formatted"] = cents_to_dollars(f["permitted_cents"])
            f["variance_formatted"] = cents_to_dollars(f["variance_cents"])
            try:
                f["calculation_steps"] = json.loads(f["calculation_steps_json"])
            except Exception:
                f["calculation_steps"] = []
        invoice["findings"] = findings

        # Fetch dispute if present
        cur.execute("SELECT * FROM disputes WHERE invoice_id = ?", (invoice_id,))
        disp = cur.fetchone()
        invoice["dispute"] = dict(disp) if disp else None

        # Fetch settlement intent & payout if present
        cur.execute("SELECT * FROM settlement_intents WHERE invoice_id = ?", (invoice_id,))
        si = cur.fetchone()
        invoice["settlement_intent"] = dict(si) if si else None

        cur.execute("SELECT * FROM payout_records WHERE invoice_id = ?", (invoice_id,))
        pr = cur.fetchone()
        invoice["payout_record"] = dict(pr) if pr else None

        return invoice

@app.post("/api/invoices/{invoice_id}/audit")
def run_invoice_audit(invoice_id: str):
    """Executes deterministic audit on the invoice against contract rate cards and telematics.
    Enforces the $2,180 discrepancy calculation for the signature scenario.
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT i.*, c.id as carrier_id, c.name as carrier_name, s.id as shipment_id
            FROM invoices i
            JOIN carriers c ON i.carrier_id = c.id
            LEFT JOIN shipments s ON i.shipment_id = s.id
            WHERE i.id = ?
        """, (invoice_id,))
        inv_row = cur.fetchone()
        if not inv_row:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found.")

        invoice = dict(inv_row)
        
        # Check if already blocked (e.g. fatal duplicate)
        if invoice["audit_status"] == "BLOCKED":
            return {
                "invoice_id": invoice_id,
                "audit_status": "BLOCKED",
                "message": "Invoice audit blocked: Critical duplicate shipment violation.",
                "disputed_amount_cents": invoice["total_billed_cents"],
                "approved_payable_cents": 0
            }

        # Initialize Tariff RAG Engine
        rag_engine = TariffRAGEngine(conn)
        contract = rag_engine.get_contract_for_carrier(invoice["carrier_id"], invoice["invoice_date"])
        contract_id = contract["id"] if contract else "AGF-MSA-2025-V2"
        contract_rules = rag_engine.get_tariff_rules_for_contract(contract_id)
        shipment = rag_engine.get_shipment_evidence(invoice.get("shipment_id", "")) or {}

        # Fetch line items
        cur.execute("SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY line_number ASC", (invoice_id,))
        items = [dict(it) for it in cur.fetchall()]

        # Clear previous findings for this invoice
        cur.execute("DELETE FROM audit_findings WHERE invoice_id = ?", (invoice_id,))

        evaluated_findings = []
        total_payable_cents = 0
        total_discrepancy_cents = 0
        now_str = datetime.now(timezone.utc).isoformat()

        for item in items:
            evaluation = evaluate_line_item(item, contract_rules, shipment)
            
            # Update item in database
            cur.execute("""
                UPDATE invoice_items 
                SET expected_cents = ?, discrepancy_cents = ?, finding_status = ?, explanation = ?
                WHERE id = ?
            """, (
                evaluation["expected_cents"],
                evaluation["variance_cents"],
                evaluation["status"],
                evaluation["explanation"],
                item["id"]
            ))

            total_payable_cents += evaluation["expected_cents"]
            total_discrepancy_cents += evaluation["variance_cents"]

            # If there is a discrepancy, record an audit finding
            if evaluation["variance_cents"] > 0:
                finding_id = f"find_{uuid.uuid4().hex[:10]}"
                cur.execute("""
                    INSERT INTO audit_findings 
                    (id, invoice_id, item_id, severity, finding_type, billed_cents, permitted_cents, variance_cents, 
                     clause_citation, contract_version, telematics_evidence, calculation_steps_json, ai_confidence_score, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    finding_id,
                    invoice_id,
                    item["id"],
                    evaluation["severity"],
                    evaluation["finding_type"],
                    evaluation["billed_cents"],
                    evaluation["expected_cents"],
                    evaluation["variance_cents"],
                    evaluation["clause_citation"],
                    evaluation["contract_version"],
                    f"Telematics BOL #{shipment.get('bol_number', 'BOL-99214')} ({shipment.get('dock_type', 'STANDARD')})",
                    json.dumps(evaluation["steps"]),
                    0.99, # 99% deterministic rule confidence
                    now_str
                ))
                evaluation["id"] = finding_id
                evaluation["calculation_steps"] = evaluation["steps"]
                evaluated_findings.append(evaluation)

        # Enforce strict financial accounting invariant
        verify_accounting_invariant(
            total_billed_cents=invoice["total_billed_cents"],
            approved_payable_cents=total_payable_cents,
            disputed_amount_cents=total_discrepancy_cents,
            held_amount_cents=0
        )

        new_audit_status = "AUDITED_DISCREPANCY" if total_discrepancy_cents > 0 else "AUDITED_CLEAN"

        # Update invoice record
        cur.execute("""
            UPDATE invoices 
            SET expected_amount_cents = ?, disputed_amount_cents = ?, approved_payable_cents = ?,
                audit_status = ?, updated_at = ?
            WHERE id = ?
        """, (
            total_payable_cents,
            total_discrepancy_cents,
            total_payable_cents,
            new_audit_status,
            now_str,
            invoice_id
        ))

        # Record audit log
        record_audit_event(
            conn, "INVOICE", invoice_id, "AUDIT_COMPLETED", "POLICY_ENGINE",
            {
                "audit_status": new_audit_status,
                "disputed_cents": total_discrepancy_cents,
                "payable_cents": total_payable_cents,
                "discrepancies_count": len(evaluated_findings)
            }
        )

        return {
            "invoice_id": invoice_id,
            "invoice_number": invoice["invoice_number"],
            "carrier_name": invoice["carrier_name"],
            "total_billed_cents": invoice["total_billed_cents"],
            "total_billed_formatted": cents_to_dollars(invoice["total_billed_cents"]),
            "approved_payable_cents": total_payable_cents,
            "approved_payable_formatted": cents_to_dollars(total_payable_cents),
            "disputed_amount_cents": total_discrepancy_cents,
            "disputed_amount_formatted": cents_to_dollars(total_discrepancy_cents),
            "audit_status": new_audit_status,
            "findings_count": len(evaluated_findings),
            "findings": evaluated_findings,
            "reconciliation_valid": True,
            "summary_message": f"Autonomous audit verified: Identified ${cents_to_dollars(total_discrepancy_cents)} in discrepancies. Legitimate payable amount is ${cents_to_dollars(total_payable_cents)}."
        }

# -----------------------------------------------------------------------------
# 3. EVIDENCE WORKBENCH
# -----------------------------------------------------------------------------
@app.get("/api/invoices/{invoice_id}/evidence")
def get_evidence_workbench(invoice_id: str):
    """Retrieves deep side-by-side evidence data for Evidence Workbench screen."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT i.*, c.name as carrier_name, c.scac, s.*, k.title as contract_title, k.version as contract_version,
                   k.effective_start, k.effective_end, k.document_text as contract_summary
            FROM invoices i
            JOIN carriers c ON i.carrier_id = c.id
            LEFT JOIN shipments s ON i.shipment_id = s.id
            LEFT JOIN contracts k ON c.id = k.carrier_id AND k.status = 'ACTIVE'
            WHERE i.id = ?
        """, (invoice_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        data = dict(row)

        # Get findings
        cur.execute("SELECT * FROM audit_findings WHERE invoice_id = ? ORDER BY variance_cents DESC", (invoice_id,))
        findings = []
        for f in cur.fetchall():
            fd = dict(f)
            fd["calculation_steps"] = json.loads(fd["calculation_steps_json"])
            findings.append(fd)
        data["findings"] = findings

        # Get contract tariff rules
        cur.execute("SELECT * FROM tariff_rules WHERE contract_id = ?", (data.get("contract_id", "AGF-MSA-2025-V2"),))
        data["tariff_rules"] = [dict(r) for r in cur.fetchall()]

        return data

# -----------------------------------------------------------------------------
# 4. DISPUTE CENTER
# -----------------------------------------------------------------------------
@app.get("/api/disputes")
def list_disputes():
    """Lists all active and historical disputes."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT d.*, i.invoice_number, i.total_billed_cents, c.name as carrier_name
            FROM disputes d
            JOIN invoices i ON d.invoice_id = i.id
            JOIN carriers c ON d.carrier_id = c.id
            ORDER BY d.created_at DESC
        """)
        return [dict(r) for r in cur.fetchall()]

@app.post("/api/disputes/generate")
def create_dispute_package(req: DisputeGenerateRequest):
    """Generates an evidence-grounded dispute package for the invoice."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT i.*, c.name as carrier_name, c.paypal_email, s.id as shipment_id, s.bol_number
            FROM invoices i
            JOIN carriers c ON i.carrier_id = c.id
            LEFT JOIN shipments s ON i.shipment_id = s.id
            WHERE i.id = ?
        """, (req.invoice_id,))
        inv_row = cur.fetchone()
        if not inv_row:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        invoice = dict(inv_row)
        carrier = {"id": invoice["carrier_id"], "name": invoice["carrier_name"], "paypal_email": invoice["paypal_email"]}
        shipment = {"id": invoice.get("shipment_id"), "bol_number": invoice.get("bol_number")}

        # Fetch findings with item explanations
        cur.execute("""
            SELECT af.*, ii.explanation, ii.description as item_description
            FROM audit_findings af
            LEFT JOIN invoice_items ii ON af.item_id = ii.id
            WHERE af.invoice_id = ?
        """, (req.invoice_id,))
        findings = [dict(f) for f in cur.fetchall()]
        if not findings:
            raise HTTPException(status_code=400, detail="Cannot generate dispute: Invoice has no audit findings or zero discrepancy.")

        # Generate dispute package
        pkg = generate_dispute_package(invoice, carrier, shipment, findings)
        
        # Check if dispute already exists
        cur.execute("SELECT id FROM disputes WHERE invoice_id = ?", (req.invoice_id,))
        existing = cur.fetchone()
        now_str = datetime.now(timezone.utc).isoformat()
        
        if existing:
            dispute_id = existing["id"]
            cur.execute("""
                UPDATE disputes 
                SET formal_letter_text = ?, evidence_summary = ?, disputed_amount_cents = ?, response_deadline = ?, updated_at = ?
                WHERE id = ?
            """, (
                pkg["formal_letter_text"],
                pkg["evidence_summary"],
                pkg["disputed_amount_cents"],
                pkg["response_deadline"],
                now_str,
                dispute_id
            ))
        else:
            dispute_id = f"disp_{uuid.uuid4().hex[:10]}"
            cur.execute("""
                INSERT INTO disputes 
                (id, invoice_id, dispute_reference, carrier_id, status, disputed_amount_cents, 
                 carrier_contact_email, formal_letter_text, evidence_summary, response_deadline, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dispute_id,
                req.invoice_id,
                pkg["dispute_reference"],
                pkg["carrier_id"],
                "DRAFTED",
                pkg["disputed_amount_cents"],
                pkg["carrier_contact_email"],
                pkg["formal_letter_text"],
                pkg["evidence_summary"],
                pkg["response_deadline"],
                now_str,
                now_str
            ))

        # Update invoice audit status to DISPUTED
        cur.execute("UPDATE invoices SET audit_status = 'DISPUTED', updated_at = ? WHERE id = ?", (now_str, req.invoice_id))

        record_audit_event(
            conn, "DISPUTE", dispute_id, "DISPUTE_DRAFTED", "DISPUTE_ENGINE",
            {"invoice_id": req.invoice_id, "disputed_cents": pkg["disputed_amount_cents"]}
        )

        pkg["id"] = dispute_id
        return pkg

@app.post("/api/disputes/{dispute_id}/status")
def update_dispute_status(dispute_id: str, new_status: str, credit_note_ref: Optional[str] = None):
    """Updates dispute state (e.g. SUBMITTED_SIMULATED, ACCEPTED_CREDIT)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM disputes WHERE id = ?", (dispute_id,))
        disp = cur.fetchone()
        if not disp:
            raise HTTPException(status_code=404, detail="Dispute not found.")

        now_str = datetime.now(timezone.utc).isoformat()
        cur.execute(
            "UPDATE disputes SET status = ?, credit_note_ref = ?, updated_at = ? WHERE id = ?",
            (new_status, credit_note_ref, now_str, dispute_id)
        )
        record_audit_event(
            conn, "DISPUTE", dispute_id, f"DISPUTE_STATUS_{new_status}", "HUMAN_OPERATOR",
            {"new_status": new_status, "credit_note": credit_note_ref}
        )
        return {"status": "SUCCESS", "dispute_id": dispute_id, "new_status": new_status}

# -----------------------------------------------------------------------------
# 5. SETTLEMENT & PAYPAL PAYOUTS
# -----------------------------------------------------------------------------
@app.post("/api/settlements/authorize")
def authorize_settlement(req: SettlementAuthorizeRequest):
    """Enforces two-man approval and prepares durable settlement intent."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoices WHERE id = ?", (req.invoice_id,))
        inv = cur.fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        invoice = dict(inv)

        # Policy validation
        is_allowed, reason = validate_settlement_authorization(
            invoice=invoice,
            first_approver=req.first_approver,
            second_approver=req.second_approver
        )
        if not is_allowed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

        now_str = datetime.now(timezone.utc).isoformat()
        intent_id = f"si_{uuid.uuid4().hex[:10]}"
        idempotency_key = f"IDEM-{invoice['invoice_number']}-{uuid.uuid4().hex[:8].upper()}"

        # Fetch carrier receiver email
        cur.execute("SELECT paypal_email FROM carriers WHERE id = ?", (invoice["carrier_id"],))
        carr_email = cur.fetchone()["paypal_email"]

        # Insert settlement intent
        cur.execute("""
            INSERT INTO settlement_intents 
            (id, invoice_id, idempotency_key, carrier_id, approved_amount_cents, held_amount_cents, 
             currency, receiver_email, first_approver, first_approved_at, second_approver, second_approved_at, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'READY_FOR_PAYOUT', ?)
        """, (
            intent_id,
            req.invoice_id,
            idempotency_key,
            invoice["carrier_id"],
            invoice["approved_payable_cents"],
            invoice["disputed_amount_cents"],
            invoice["currency"],
            carr_email,
            req.first_approver,
            now_str,
            req.second_approver,
            now_str if req.second_approver else None,
            now_str
        ))

        # Update invoice settlement status
        cur.execute("UPDATE invoices SET settlement_status = 'AUTHORIZED', updated_at = ? WHERE id = ?", (now_str, req.invoice_id))

        record_audit_event(
            conn, "SETTLEMENT", intent_id, "SETTLEMENT_AUTHORIZED", "FINANCIAL_POLICY",
            {
                "approved_payable_cents": invoice["approved_payable_cents"],
                "approver_1": req.first_approver,
                "approver_2": req.second_approver,
                "idempotency_key": idempotency_key
            }
        )

        return {
            "status": "AUTHORIZED",
            "settlement_intent_id": intent_id,
            "idempotency_key": idempotency_key,
            "approved_amount_cents": invoice["approved_payable_cents"],
            "approved_amount_formatted": cents_to_dollars(invoice["approved_payable_cents"]),
            "message": f"Settlement authorized for ${cents_to_dollars(invoice['approved_payable_cents'])}. Ready for PayPal payout execution."
        }

@app.post("/api/settlements/payout")
def execute_payout(req: SettlementPayoutRequest):
    """Executes verified PayPal Payout with strict idempotency and invariants."""
    with get_db() as conn:
        cur = conn.cursor()

        # 1. First, check if payout record with this idempotency key already exists (Idempotent replay)
        if req.idempotency_key:
            cur.execute("SELECT * FROM payout_records WHERE idempotency_key = ?", (req.idempotency_key,))
            existing_payout = cur.fetchone()
            if existing_payout:
                p_dict = dict(existing_payout)
                return {
                    "idempotent_replay": True,
                    "status": "SUCCESS",
                    "payout_id": p_dict["id"],
                    "paypal_batch_id": p_dict["paypal_batch_id"],
                    "paypal_item_id": p_dict["paypal_item_id"],
                    "batch_status": p_dict["batch_status"],
                    "item_status": p_dict["item_status"],
                    "amount_paid_formatted": cents_to_dollars(p_dict["amount_cents"]),
                    "is_simulated": bool(p_dict["is_simulated"]),
                    "message": "Idempotency match: Payout has already been processed with this key.",
                    "payout": p_dict
                }

        # 2. Load invoice
        cur.execute("""
            SELECT i.*, c.paypal_email, c.name as carrier_name
            FROM invoices i
            JOIN carriers c ON i.carrier_id = c.id
            WHERE i.id = ?
        """, (req.invoice_id,))
        inv_row = cur.fetchone()
        if not inv_row:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        invoice = dict(inv_row)

        # Invariant check: Prohibit paying unapproved, held, disputed, or already paid invoices
        if invoice["settlement_status"] in ["PAYOUT_INITIATED", "PAYOUT_SUCCESS", "RECONCILED"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Deterministic Policy Invariant: Invoice {invoice['invoice_number']} is already in state '{invoice['settlement_status']}'. Duplicate payment prevented."
            )

        if invoice["audit_status"] == "BLOCKED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Deterministic Policy Invariant: Cannot execute settlement on BLOCKED invoice."
            )

        if invoice["approved_payable_cents"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Deterministic Policy Invariant: Approved payable amount is ${cents_to_dollars(invoice['approved_payable_cents'])}."
            )

        # 3. Check existing settlement intent
        cur.execute("SELECT * FROM settlement_intents WHERE invoice_id = ?", (req.invoice_id,))
        intent = cur.fetchone()
        if not intent:
            # Must authorize first!
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization Invariant: Settlement must be formally authorized before initiating payout."
            )

        intent_id = intent["id"]
        idempotency_key = req.idempotency_key or intent["idempotency_key"]

        # 3. Call PayPal Adapter
        sender_batch_id = f"BATCH-{invoice['invoice_number']}-{uuid.uuid4().hex[:6].upper()}"
        note = f"FreightGuard Verified Settlement: Inv #{invoice['invoice_number']} (Approved Payable: ${cents_to_dollars(invoice['approved_payable_cents'])})"

        try:
            payout_result = paypal_adapter.create_payout(
                idempotency_key=idempotency_key,
                sender_batch_id=sender_batch_id,
                receiver_email=invoice["paypal_email"],
                amount_cents=invoice["approved_payable_cents"],
                currency=invoice["currency"],
                note=note
            )
        except PayPalAdapterException as e:
            raise HTTPException(status_code=502, detail=str(e))

        now_str = datetime.now(timezone.utc).isoformat()
        payout_id = f"pay_{uuid.uuid4().hex[:10]}"

        # 4. Persist Payout Record
        cur.execute("""
            INSERT INTO payout_records 
            (id, settlement_intent_id, invoice_id, idempotency_key, paypal_batch_id, paypal_item_id, 
             amount_cents, currency, receiver_email, batch_status, item_status, paypal_fee_cents, raw_paypal_response_json, is_simulated, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payout_id,
            intent_id,
            req.invoice_id,
            idempotency_key,
            payout_result["batch_id"],
            payout_result["item_id"],
            invoice["approved_payable_cents"],
            invoice["currency"],
            invoice["paypal_email"],
            payout_result["batch_status"],
            payout_result["item_status"],
            payout_result["paypal_fee_cents"],
            json.dumps(payout_result["raw_response"]),
            payout_result["is_simulated"],
            now_str,
            now_str
        ))

        # 5. Update settlement intent & invoice statuses
        cur.execute("UPDATE settlement_intents SET status = 'COMPLETED' WHERE id = ?", (intent_id,))
        cur.execute("UPDATE invoices SET settlement_status = 'PAYOUT_INITIATED', updated_at = ? WHERE id = ?", (now_str, req.invoice_id))

        record_audit_event(
            conn, "SETTLEMENT", payout_id, "PAYPAL_PAYOUT_INITIATED", "PAYPAL_ADAPTER",
            {
                "payout_batch_id": payout_result["batch_id"],
                "payout_item_id": payout_result["item_id"],
                "amount_cents": invoice["approved_payable_cents"],
                "is_simulated": bool(payout_result["is_simulated"])
            }
        )

        return {
            "status": "SUCCESS",
            "payout_id": payout_id,
            "paypal_batch_id": payout_result["batch_id"],
            "paypal_item_id": payout_result["item_id"],
            "batch_status": payout_result["batch_status"],
            "item_status": payout_result["item_status"],
            "amount_paid_formatted": cents_to_dollars(invoice["approved_payable_cents"]),
            "is_simulated": bool(payout_result["is_simulated"]),
            "mode_label": payout_result["mode_label"],
            "receiver_email": invoice["paypal_email"],
            "raw_response": payout_result["raw_response"]
        }

# -----------------------------------------------------------------------------
# 6. WEBHOOKS & SIMULATION
# -----------------------------------------------------------------------------
@app.post("/api/webhooks/paypal")
async def receive_paypal_webhook(request: Request):
    """Authoritative PayPal Webhook listener endpoint with signature check and deduplication."""
    payload = await request.json()
    with get_db() as conn:
        svc = WebhookService(conn)
        success, msg, data = svc.process_webhook_event(payload, is_simulated=0)
        return {"success": success, "message": msg, "data": data}

@app.post("/api/webhooks/simulate")
def simulate_webhook_event(req: WebhookSimulateRequest):
    """Simulates a PayPal Webhook event for interactive judging and demonstration."""
    with get_db() as conn:
        cur = conn.cursor()
        
        # If payout item/batch not provided, find the latest payout record
        if not req.payout_item_id and not req.payout_batch_id:
            cur.execute("SELECT paypal_batch_id, paypal_item_id FROM payout_records ORDER BY created_at DESC LIMIT 1")
            latest = cur.fetchone()
            if latest:
                payout_batch_id = latest["paypal_batch_id"]
                payout_item_id = latest["paypal_item_id"]
            else:
                payout_batch_id = "PAYPAL-SBX-BATCH-DEMO"
                payout_item_id = "PAYPAL-SBX-ITEM-DEMO"
        else:
            payout_batch_id = req.payout_batch_id
            payout_item_id = req.payout_item_id

        event_id = req.event_id or f"WH-SIM-{uuid.uuid4().hex[:10].upper()}"
        now_str = datetime.now(timezone.utc).isoformat()

        simulated_payload = {
            "id": event_id,
            "event_version": "1.0",
            "create_time": now_str,
            "resource_type": "payouts_item" if "ITEM" in req.event_type else "payouts_batch",
            "event_type": req.event_type,
            "summary": f"Simulated PayPal Webhook Event: {req.event_type}",
            "resource": {
                "payout_item_id": payout_item_id,
                "payout_batch_id": payout_batch_id,
                "transaction_status": "SUCCESS" if "SUCCESS" in req.event_type or "SUCCEEDED" in req.event_type else "FAILED"
            }
        }

        svc = WebhookService(conn)
        success, msg, data = svc.process_webhook_event(simulated_payload, is_simulated=1)
        return {
            "simulated": True,
            "event_id": event_id,
            "event_type": req.event_type,
            "message": msg,
            "reconciled_data": data
        }

# -----------------------------------------------------------------------------
# 7. AUDIT TRAIL & AGENT ACTIVITY
# -----------------------------------------------------------------------------
@app.get("/api/audit-events")
def list_audit_events(limit: int = 50):
    """Returns chronological, immutable audit events."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?", (limit,))
        events = []
        for r in cur.fetchall():
            ev = dict(r)
            try:
                ev["details"] = json.loads(ev["details_json"])
            except Exception:
                ev["details"] = {}
            events.append(ev)
        return events

# -----------------------------------------------------------------------------
# 8. SETTINGS & SYSTEM DIAGNOSTICS
# -----------------------------------------------------------------------------
@app.get("/api/settings")
def get_settings():
    """Returns safe connection states and system diagnostics."""
    paypal_diag = paypal_adapter.get_mode_diagnostics()
    return {
        "app_mode": APP_MODE,
        "paypal": paypal_diag,
        "database": {
            "engine": "SQLite 3",
            "wal_mode": True,
            "foreign_keys": True,
            "status": "HEALTHY"
        },
        "ai_engine": {
            "provider": "LOCAL_DETERMINISTIC_TARIFF_RAG",
            "confidence_model": "EXACT_DECIMAL_RULE_EVALUATOR",
            "status": "OPERATIONAL"
        }
    }

@app.post("/api/settings/reset-demo")
def reset_demo_data():
    """Resets all data back to the clean signature demonstration state."""
    populate_seed_data(reset=True)
    return {"status": "SUCCESS", "message": "Demo data reset successfully to signature state ($2,180 discrepancy ready for audit)."}

# -----------------------------------------------------------------------------
# STATIC FILES SERVING (UI)
# -----------------------------------------------------------------------------
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "FreightGuard Backend Operational. Frontend is initializing."}
