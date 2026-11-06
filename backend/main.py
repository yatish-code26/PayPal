"""FreightGuard FastAPI Backend Application
Main entrypoint providing deterministic freight financial control tower APIs,
evidence intelligence, dispute workflows, and PayPal settlement orchestration.
"""
from fastapi import FastAPI, HTTPException, Request, Depends, status, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import uuid
import io
from datetime import datetime, timezone

from backend.config import APP_MODE, BASE_DIR, CORS_ALLOWED_ORIGINS
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
from backend.paypal_adapter import PayPalPayoutsAdapter, PayPalAdapterException, generate_local_webhook_signature
from backend.webhook_service import WebhookService
from backend.seed_data import populate_seed_data
import backend.ai_service as ai_service
from backend.auth import (
    DEMO_USERS,
    create_token_for_user,
    decode_token,
    get_current_user,
    get_optional_user,
)
from backend.rate_limiter import settlement_limiter
from backend.models import (
    SettlementAuthorizeRequest,
    SettlementPayoutRequest,
    WebhookSimulateRequest,
    DisputeGenerateRequest,
    SettingsUpdateSchema
)

app = FastAPI(
    title="FreightGuard API",
    description="Autonomous Freight Invoice Audit, Evidence Intelligence & PayPal Settlement Control Tower",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
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
    """Aggregates executive metrics from persisted database records with strict invariant verification."""
    with get_db() as conn:
        cur = conn.cursor()
        
        # Summary totals directly from persistent invoice records
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

        # Recovered / Credited Amount (from accepted/resolved disputes only)
        cur.execute("""
            SELECT COALESCE(SUM(disputed_amount_cents), 0) as recovered_cents 
            FROM disputes WHERE status IN ('ACCEPTED_CREDIT', 'RESOLVED_CREDITED')
        """)
        recovered = cur.fetchone()["recovered_cents"]

        # Exceptions count
        cur.execute("""
            SELECT COUNT(*) as exceptions_count 
            FROM invoices 
            WHERE audit_status IN ('AUDITED_DISCREPANCY', 'BLOCKED', 'DISPUTED')
        """)
        exceptions_count = cur.fetchone()["exceptions_count"]

        # Payouts stats from completed PayPal transactions
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

        # Invariant verification: billed = approved + disputed + held (cents exactness)
        invariant_reconciles = totals["total_billed"] == (totals["total_payable"] + totals["total_disputed"] + totals["total_held"])

        # Attention queue items
        cur.execute("""
            SELECT i.id, i.invoice_number, i.total_billed_cents, i.disputed_amount_cents, i.audit_status, c.name as carrier_name
            FROM invoices i JOIN carriers c ON i.carrier_id = c.id
            WHERE i.audit_status IN ('PENDING_AUDIT', 'AUDITED_DISCREPANCY') AND i.settlement_status = 'UNSETTLED'
            ORDER BY i.created_at DESC LIMIT 5
        """)
        invoices_to_review = [
            {
                **dict(r),
                "total_billed_formatted": cents_to_dollars(r["total_billed_cents"]),
                "disputed_formatted": cents_to_dollars(r["disputed_amount_cents"])
            }
            for r in cur.fetchall()
        ]

        cur.execute("""
            SELECT d.id, d.invoice_id, d.disputed_amount_cents, d.status, c.name as carrier_name, i.invoice_number
            FROM disputes d
            JOIN carriers c ON d.carrier_id = c.id
            JOIN invoices i ON d.invoice_id = i.id
            WHERE d.status IN ('PENDING_CARRIER_REVIEW', 'DRAFT')
            ORDER BY d.created_at DESC LIMIT 5
        """)
        disputes_awaiting_reply = [
            {
                **dict(r),
                "disputed_formatted": cents_to_dollars(r["disputed_amount_cents"])
            }
            for r in cur.fetchall()
        ]

        cur.execute("""
            SELECT i.id, i.invoice_number, i.approved_payable_cents, c.name as carrier_name, i.settlement_status
            FROM invoices i JOIN carriers c ON i.carrier_id = c.id
            WHERE i.settlement_status IN ('UNSETTLED', 'AUTHORIZED') AND i.approved_payable_cents > 0 AND i.audit_status != 'BLOCKED'
            ORDER BY i.created_at DESC LIMIT 5
        """)
        payments_awaiting_approval = [
            {
                **dict(r),
                "approved_payable_formatted": cents_to_dollars(r["approved_payable_cents"])
            }
            for r in cur.fetchall()
        ]

        return {
            "total_invoices": total_inv,
            "total_billed_cents": totals["total_billed"],
            "total_billed_formatted": cents_to_dollars(totals["total_billed"]),
            "approved_payable_cents": totals["total_payable"],
            "approved_payable_formatted": cents_to_dollars(totals["total_payable"]),
            "verified_payable_cents": totals["total_payable"],
            "verified_payable_formatted": cents_to_dollars(totals["total_payable"]),
            "disputed_amount_cents": totals["total_disputed"],
            "disputed_amount_formatted": cents_to_dollars(totals["total_disputed"]),
            "detected_disputed_cents": totals["total_disputed"],
            "detected_disputed_formatted": cents_to_dollars(totals["total_disputed"]),
            "held_amount_cents": totals["total_held"],
            "held_amount_formatted": cents_to_dollars(totals["total_held"]),
            "pending_settlement_cents": totals["total_held"],
            "pending_settlement_formatted": cents_to_dollars(totals["total_held"]),
            "paid_amount_cents": payouts["payouts_amount_cents"],
            "paid_amount_formatted": cents_to_dollars(payouts["payouts_amount_cents"]),
            "successful_payouts_cents": payouts["payouts_amount_cents"],
            "successful_payouts_formatted": cents_to_dollars(payouts["payouts_amount_cents"]),
            "confirmed_recovered_cents": recovered,
            "confirmed_recovered_formatted": cents_to_dollars(recovered),
            "recovered_amount_cents": recovered,
            "recovered_amount_formatted": cents_to_dollars(recovered),
            "audit_coverage_pct": coverage_pct,
            "exception_rate_pct": exception_rate_pct,
            "invariant_reconciles": invariant_reconciles,
            "attention_queue": {
                "invoices_to_review": invoices_to_review,
                "disputes_awaiting_reply": disputes_awaiting_reply,
                "payments_awaiting_approval": payments_awaiting_approval,
            },
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

@app.post("/api/invoices/upload")
async def upload_invoice(file: UploadFile = File(...)):
    """Uploads an invoice (PDF or text), extracts structured fields via AI service,
    persists the invoice and line items in SQLite, and executes the deterministic audit pipeline.
    """
    filename = file.filename or "uploaded_invoice.txt"
    content_bytes = await file.read()
    raw_text = ""

    if filename.lower().endswith(".pdf") or (file.content_type and "pdf" in file.content_type.lower()):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            raw_text = "\n".join(pages)
        except Exception:
            try:
                import fitz
                doc = fitz.open(stream=content_bytes, filetype="pdf")
                raw_text = "\n".join([page.get_text() for page in doc])
            except Exception:
                raw_text = content_bytes.decode("utf-8", errors="ignore")
    else:
        raw_text = content_bytes.decode("utf-8", errors="ignore")

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Uploaded file contains no readable text content.")

    # Call AI extraction service
    extracted = ai_service.extract_invoice(raw_text)

    with get_db() as conn:
        cur = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()

        carrier_name = extracted.get("carrier_name", "Apex Global Freight Logistics")
        cur.execute("SELECT id FROM carriers WHERE name LIKE ? LIMIT 1", (f"%{carrier_name[:10]}%",))
        c_row = cur.fetchone()
        carrier_id = c_row["id"] if c_row else "carr_apex_01"

        inv_num = extracted.get("invoice_number") or f"INV-UPL-{uuid.uuid4().hex[:6].upper()}"
        inv_id = inv_num
        shipment_ref = extracted.get("shipment_reference") or "SH-884192"

        cur.execute("SELECT id FROM shipments WHERE id = ? OR bol_number = ?", (shipment_ref, shipment_ref))
        s_row = cur.fetchone()
        shipment_id = s_row["id"] if s_row else "SH-884192"

        total_billed = extracted.get("total_billed_cents", 0)
        inv_date = extracted.get("invoice_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        cur.execute("""
            INSERT OR REPLACE INTO invoices
            (id, carrier_id, shipment_id, invoice_number, invoice_date, due_date, currency,
             total_billed_cents, expected_amount_cents, disputed_amount_cents, approved_payable_cents,
             held_amount_cents, audit_status, settlement_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 'PENDING_AUDIT', 'UNSETTLED', ?, ?)
        """, (
            inv_id, carrier_id, shipment_id, inv_num, inv_date, inv_date,
            extracted.get("currency", "USD"), total_billed, now_str, now_str
        ))

        cur.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (inv_id,))

        line_items = extracted.get("line_items", [])
        for idx, item in enumerate(line_items, 1):
            item_id = f"item_{inv_id}_{idx}"
            cur.execute("""
                INSERT INTO invoice_items
                (id, invoice_id, line_number, charge_code, description, billed_cents,
                 expected_cents, discrepancy_cents, finding_status, rule_reference, explanation)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'PENDING', NULL, NULL)
            """, (
                item_id, inv_id, idx,
                item.get("charge_code", "MISC"),
                item.get("description", "Extracted charge item"),
                item.get("billed_cents", 0)
            ))

        record_audit_event(
            conn, "INVOICE", inv_id, "INVOICE_UPLOADED_AND_EXTRACTED", "AI_INGESTION_SERVICE",
            {"ai_provider": extracted.get("_ai"), "items_count": len(line_items), "filename": filename}
        )

    # Run deterministic audit pipeline immediately
    audit_res = run_invoice_audit(inv_id)
    audit_res["_ai"] = extracted.get("_ai")
    audit_res["extracted_invoice"] = extracted
    return audit_res

@app.get("/api/ai/explain/{invoice_id}")
def get_ai_explanation(invoice_id: str):
    """Returns plain-English executive AI summary and breakdown of audit findings."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        inv = cur.fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        invoice = dict(inv)

        cur.execute("""
            SELECT af.*, ii.explanation, ii.description as item_description
            FROM audit_findings af
            LEFT JOIN invoice_items ii ON af.item_id = ii.id
            WHERE af.invoice_id = ?
        """, (invoice_id,))
        findings = [dict(f) for f in cur.fetchall()]

        return ai_service.explain_audit(invoice, findings)

@app.get("/api/ai/provider")
def get_ai_provider():
    """Returns active AI provider and supported model list."""
    return {
        "active_provider": ai_service.active_provider(),
        "available_providers": ["GROQ", "GEMINI", "OPENAI", "LOCAL_DETERMINISTIC"],
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

        # Rank clauses via local BM25 and draft dispute using AI service (or deterministic fallback)
        rag_engine = TariffRAGEngine(conn)
        contract = rag_engine.get_contract_for_carrier(invoice["carrier_id"], invoice["invoice_date"])
        contract_id = contract["id"] if contract else "AGF-MSA-2025-V2"
        ranked_clauses = rag_engine.rank_clauses_for_findings(contract_id, findings)

        pkg = ai_service.draft_dispute(invoice, carrier, shipment, findings, ranked_clauses)

        # Enforce financial boundary: AI cannot manipulate monetary amounts
        if not ai_service.verify_ai_financial_integrity(
            invoice["total_billed_cents"],
            invoice["approved_payable_cents"],
            pkg.get("disputed_amount_cents", 0),
            pkg
        ):
            pkg = generate_dispute_package(invoice, carrier, shipment, findings)
            pkg["_ai"] = "FALLBACK (Financial policy blocked AI monetary alteration)"
        
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
def authorize_settlement(
    req: SettlementAuthorizeRequest,
    request: Request = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Enforces two-man approval and prepares durable settlement intent."""
    user_dict = current_user if isinstance(current_user, dict) else None
    if request:
        settlement_limiter.check(request, identifier=user_dict.get("email") if user_dict else None)

    first_approver = req.first_approver
    second_approver = req.second_approver

    # If authenticated user is present, bind identity and enforce authorization
    if user_dict:
        if not user_dict.get("can_approve", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{user_dict.get('role')}' is not authorized to sign off on financial settlements."
            )
        first_approver = user_dict["email"]
        if second_approver and second_approver == first_approver:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Segregation of duties violation: First approver and second approver cannot be the same individual."
            )

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
            first_approver=first_approver,
            second_approver=second_approver
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
            first_approver,
            now_str,
            second_approver,
            now_str if second_approver else None,
            now_str
        ))

        # Update invoice settlement status
        cur.execute("UPDATE invoices SET settlement_status = 'AUTHORIZED', updated_at = ? WHERE id = ?", (now_str, req.invoice_id))

        record_audit_event(
            conn, "SETTLEMENT", intent_id, "SETTLEMENT_AUTHORIZED", "FINANCIAL_POLICY",
            {
                "approved_payable_cents": invoice["approved_payable_cents"],
                "approver_1": first_approver,
                "approver_2": second_approver,
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
def execute_payout(
    req: SettlementPayoutRequest,
    request: Request = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Executes verified PayPal Payout with strict idempotency and invariants."""
    user_dict = current_user if isinstance(current_user, dict) else None
    if request:
        settlement_limiter.check(request, identifier=user_dict.get("email") if user_dict else None)
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

@app.post("/api/settlements/pay-now-hold-rest")
def pay_now_hold_rest(
    req: SettlementPayoutRequest,
    request: Request = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Executes partial settlement: pays undisputed approved balance immediately,
    and moves disputed variance into a visible held state."""
    user_dict = current_user if isinstance(current_user, dict) else None
    if request:
        settlement_limiter.check(request, identifier=user_dict.get("email") if user_dict else None)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoices WHERE id = ?", (req.invoice_id,))
        inv_row = cur.fetchone()
        if not inv_row:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        invoice = dict(inv_row)

        if invoice["audit_status"] == "BLOCKED":
            raise HTTPException(status_code=403, detail="Cannot execute settlement on BLOCKED invoice.")

        if invoice["approved_payable_cents"] <= 0:
            raise HTTPException(status_code=400, detail="No approved payable balance available for payout.")

        cur.execute("SELECT * FROM settlement_intents WHERE invoice_id = ?", (req.invoice_id,))
        intent = cur.fetchone()
        now_str = datetime.now(timezone.utc).isoformat()

        cur.execute("SELECT paypal_email FROM carriers WHERE id = ?", (invoice["carrier_id"],))
        carr_email = cur.fetchone()["paypal_email"]

        if not intent:
            intent_id = f"si_{uuid.uuid4().hex[:10]}"
            idempotency_key = req.idempotency_key or f"IDEM-HOLD-{invoice['invoice_number']}-{uuid.uuid4().hex[:6].upper()}"
            cur.execute("""
                INSERT INTO settlement_intents
                (id, invoice_id, idempotency_key, carrier_id, approved_amount_cents, held_amount_cents,
                 currency, receiver_email, first_approver, first_approved_at, second_approver, second_approved_at, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PARTIALLY_AUTHORIZED', ?)
            """, (
                intent_id, req.invoice_id, idempotency_key, invoice["carrier_id"],
                invoice["approved_payable_cents"], invoice["disputed_amount_cents"],
                invoice["currency"], carr_email,
                user_dict.get("email", "sarah.chen@shipper.internal") if user_dict else "sarah.chen@shipper.internal",
                now_str,
                "david.ross@shipper.internal",
                now_str,
                now_str
            ))
        else:
            intent_id = intent["id"]
            idempotency_key = req.idempotency_key or intent["idempotency_key"]

        sender_batch_id = f"BATCH-HOLD-{invoice['invoice_number']}-{uuid.uuid4().hex[:6].upper()}"
        note = f"FreightGuard Partial Payout: Inv #{invoice['invoice_number']} (Paid: ${cents_to_dollars(invoice['approved_payable_cents'])}, Held in Dispute: ${cents_to_dollars(invoice['disputed_amount_cents'])})"

        try:
            payout_result = paypal_adapter.create_payout(
                idempotency_key=idempotency_key,
                sender_batch_id=sender_batch_id,
                receiver_email=carr_email,
                amount_cents=invoice["approved_payable_cents"],
                currency=invoice["currency"],
                note=note
            )
        except PayPalAdapterException as e:
            raise HTTPException(status_code=502, detail=str(e))

        payout_id = f"pay_{uuid.uuid4().hex[:10]}"
        cur.execute("""
            INSERT INTO payout_records 
            (id, settlement_intent_id, invoice_id, idempotency_key, paypal_batch_id, paypal_item_id,
             amount_cents, currency, receiver_email, batch_status, item_status, paypal_fee_cents,
             raw_paypal_response_json, is_simulated, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payout_id, intent_id, req.invoice_id, idempotency_key,
            payout_result["batch_id"], payout_result["item_id"],
            invoice["approved_payable_cents"], invoice["currency"],
            carr_email, payout_result["batch_status"], payout_result["item_status"],
            payout_result.get("fee_cents", 25),
            json.dumps(payout_result["raw_response"]),
            1 if payout_result["is_simulated"] else 0,
            now_str, now_str
        ))

        held_cents = invoice["disputed_amount_cents"]
        cur.execute("""
            UPDATE invoices 
            SET settlement_status = 'PARTIALLY_SETTLED_HELD',
                held_amount_cents = ?,
                disputed_amount_cents = 0,
                updated_at = ?
            WHERE id = ?
        """, (held_cents, now_str, req.invoice_id))

        record_audit_event(
            conn, "SETTLEMENT", req.invoice_id, "PARTIAL_PAYOUT_EXECUTED_DISPUTE_HELD",
            user_dict.get("email", "FINANCE_OPERATIONS") if user_dict else "FINANCE_OPERATIONS",
            {
                "paid_cents": invoice["approved_payable_cents"],
                "paid_formatted": cents_to_dollars(invoice["approved_payable_cents"]),
                "held_cents": held_cents,
                "held_formatted": cents_to_dollars(held_cents),
                "paypal_item_id": payout_result["item_id"],
                "idempotency_key": idempotency_key
            }
        )

        return {
            "status": "SUCCESS",
            "settlement_status": "PARTIALLY_SETTLED_HELD",
            "paid_amount_cents": invoice["approved_payable_cents"],
            "paid_amount_formatted": cents_to_dollars(invoice["approved_payable_cents"]),
            "held_amount_cents": held_cents,
            "held_amount_formatted": cents_to_dollars(held_cents),
            "paypal_item_id": payout_result["item_id"],
            "paypal_batch_id": payout_result["batch_id"],
            "message": f"Paid ${cents_to_dollars(invoice['approved_payable_cents'])} to carrier. Held ${cents_to_dollars(held_cents)} in dispute reserve."
        }

@app.post("/api/disputes/{dispute_id}/resolve")
def resolve_dispute(dispute_id: str, payload: Dict[str, Any] = {}):
    """Resolves dispute upon carrier agreement/credit note, releases held reserve,
    and transitions invoice to RECONCILED."""
    credit_ref = payload.get("credit_note_ref", f"CN-{uuid.uuid4().hex[:8].upper()}")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM disputes WHERE id = ?", (dispute_id,))
        disp = cur.fetchone()
        if not disp:
            raise HTTPException(status_code=404, detail="Dispute not found.")

        dispute = dict(disp)
        now_str = datetime.now(timezone.utc).isoformat()

        cur.execute("""
            UPDATE disputes
            SET status = 'RESOLVED_CREDITED', credit_note_ref = ?, updated_at = ?
            WHERE id = ?
        """, (credit_ref, now_str, dispute_id))

        cur.execute("""
            UPDATE invoices
            SET settlement_status = 'RECONCILED',
                held_amount_cents = 0,
                updated_at = ?
            WHERE id = ?
        """, (now_str, dispute["invoice_id"]))

        record_audit_event(
            conn, "DISPUTE", dispute_id, "DISPUTE_RESOLVED_CREDIT_ACCEPTED",
            "CARRIER_OPERATIONS",
            {
                "credit_note_ref": credit_ref,
                "recovered_cents": dispute["disputed_amount_cents"],
                "recovered_formatted": cents_to_dollars(dispute["disputed_amount_cents"])
            }
        )

        return {
            "status": "SUCCESS",
            "dispute_id": dispute_id,
            "new_status": "RESOLVED_CREDITED",
            "credit_note_ref": credit_ref,
            "message": f"Dispute resolved. Credit note {credit_ref} recorded. Held funds released; invoice reconciled."
        }

@app.get("/api/audit-events/verify-integrity")
def verify_audit_trail_integrity():
    """Cryptographically verifies the SHA-256 hash chain of the immutable audit trail."""
    with get_db() as conn:
        from backend.database import verify_audit_chain_integrity
        return verify_audit_chain_integrity(conn)

@app.get("/api/carriers/scorecards")
def get_carrier_scorecards():
    """Calculates carrier overcharge rates, recurring error patterns, and renewal negotiation talking points."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                c.id, c.name, c.scac, c.paypal_email,
                COUNT(i.id) as invoice_count,
                COALESCE(SUM(i.total_billed_cents), 0) as total_billed_cents,
                COALESCE(SUM(i.approved_payable_cents), 0) as approved_payable_cents,
                COALESCE(SUM(i.disputed_amount_cents), 0) as disputed_cents,
                COALESCE(SUM(i.held_amount_cents), 0) as held_cents
            FROM carriers c
            LEFT JOIN invoices i ON c.id = i.carrier_id
            GROUP BY c.id
        """)
        rows = cur.fetchall()

        scorecards = []
        for r in rows:
            carr = dict(r)
            billed = carr["total_billed_cents"]
            disputed = carr["disputed_cents"] + carr["held_cents"]
            overcharge_pct = round((disputed / billed * 100), 1) if billed > 0 else 0.0

            cur.execute("""
                SELECT f.finding_type, COUNT(*) as cnt, SUM(f.variance_cents) as total_var
                FROM audit_findings f
                JOIN invoices i ON f.invoice_id = i.id
                WHERE i.carrier_id = ?
                GROUP BY f.finding_type
                ORDER BY total_var DESC
            """, (carr["id"],))
            recurring = [dict(f) for f in cur.fetchall()]
            projected_annual_leakage = disputed * 12

            talking_points = []
            if overcharge_pct > 10.0:
                talking_points.append(f"Carrier exhibits an elevated {overcharge_pct}% discrepancy rate on billed freight.")
            for rec in recurring:
                ft = rec["finding_type"]
                amt = cents_to_dollars(rec["total_var"])
                if ft == "RATE_MISMATCH":
                    talking_points.append(f"Repeated linehaul rate creep totaling ${amt} above agreed lane tariffs.")
                elif ft == "FUEL_OVERCHARGE":
                    talking_points.append(f"Fuel index surcharge inflation (${amt}) failing EIA/DOE peg formula.")
                elif ft == "UNAUTHORIZED_ACCESSORIAL":
                    talking_points.append(f"Unapproved accessorial and liftgate billings without dispatch authorization.")
                elif ft == "DUPLICATE_CHARGE":
                    talking_points.append(f"Prohibited duplicate dwell and secondary congestion surcharges.")

            if not talking_points:
                talking_points.append("Carrier demonstrates high billing accuracy with near-zero contractual discrepancies.")

            scorecards.append({
                "carrier_id": carr["id"],
                "name": carr["name"],
                "scac": carr["scac"],
                "total_invoices": carr["invoice_count"],
                "total_billed_formatted": cents_to_dollars(billed),
                "approved_payable_formatted": cents_to_dollars(carr["approved_payable_cents"]),
                "disputed_formatted": cents_to_dollars(disputed),
                "overcharge_rate_pct": overcharge_pct,
                "projected_annual_leakage_formatted": cents_to_dollars(projected_annual_leakage),
                "recurring_findings": recurring,
                "talking_points": talking_points
            })

        return scorecards

@app.post("/api/chat/ask")
def chat_ask_freightguard(payload: Dict[str, Any]):
    """Ask FreightGuard Assistant: Grounded question answering over contracts, invoices, and rates."""
    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    with get_db() as conn:
        stats = get_dashboard_stats()
        scorecards = get_carrier_scorecards()
        cur = conn.cursor()
        cur.execute("SELECT * FROM audit_findings ORDER BY variance_cents DESC LIMIT 10")
        findings = [
            {
                "finding_type": f["finding_type"],
                "charge_code": f["charge_code"],
                "explanation": f["explanation"],
                "clause_citation": f["clause_citation"],
                "variance_formatted": cents_to_dollars(f["variance_cents"])
            }
            for f in cur.fetchall()
        ]

        db_context = {
            **stats,
            "carrier_stats": scorecards,
            "findings": findings
        }

        answer_data = ai_service.answer_freight_question(question, db_context)
        record_audit_event(
            conn, "AI_ASSISTANT", "CHAT", "ASK_FREIGHTGUARD_QUERY", "OPERATOR",
            {"question": question, "provider": answer_data.get("_ai")}
        )
        return answer_data

@app.get("/api/disputes/{dispute_id}/export-pdf")
def export_dispute_package_pdf(dispute_id: str):
    """Exports formal commercial dispute notice as a clean, downloadable PDF."""
    from backend.pdf_utils import generate_dispute_pdf
    from fastapi.responses import Response

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT d.*, i.invoice_number, i.total_billed_cents, i.approved_payable_cents, c.name as carrier_name, c.scac
            FROM disputes d
            JOIN invoices i ON d.invoice_id = i.id
            JOIN carriers c ON d.carrier_id = c.id
            WHERE d.id = ?
        """, (dispute_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Dispute record not found.")

        disp = dict(row)
        cur.execute("SELECT * FROM audit_findings WHERE invoice_id = ?", (disp["invoice_id"],))
        findings = [dict(f) for f in cur.fetchall()]

        pdf_bytes = generate_dispute_pdf(disp, findings)
        filename = f"Dispute-{disp['invoice_number']}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

@app.get("/api/anomalies")
def get_system_anomalies():
    """Detects cross-invoice anomalies such as duplicate shipments and lane rate drift."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id as shipment_id, s.bol_number, COUNT(i.id) as billed_count,
                   GROUP_CONCAT(i.invoice_number, ', ') as invoices_list
            FROM shipments s
            JOIN invoices i ON s.id = i.shipment_id
            GROUP BY s.id
            HAVING COUNT(i.id) > 1
        """)
        dup_shipments = [
            {
                "type": "DUPLICATE_SHIPMENT_BILLED",
                "severity": "CRITICAL",
                "title": f"Shipment {r['bol_number']} billed multiple times",
                "description": f"Shipment ID {r['shipment_id']} (BOL {r['bol_number']}) was submitted across multiple invoices: {r['invoices_list']}.",
                "evidence": "Duplicate billing attempt blocked by cross-invoice validation."
            }
            for r in cur.fetchall()
        ]

        cur.execute("""
            SELECT i.invoice_number, c.name as carrier_name, f.explanation, f.variance_cents
            FROM audit_findings f
            JOIN invoices i ON f.invoice_id = i.id
            JOIN carriers c ON i.carrier_id = c.id
            WHERE f.finding_type = 'RATE_MISMATCH'
        """)
        rate_drifts = [
            {
                "type": "RATE_DRIFT_VARIANCE",
                "severity": "WARNING",
                "title": f"Off-tariff rate drift on {r['invoice_number']}",
                "description": f"{r['carrier_name']}: {r['explanation']}",
                "evidence": f"Flagged variance: ${cents_to_dollars(r['variance_cents'])}"
            }
            for r in cur.fetchall()
        ]

        return {
            "total_anomalies": len(dup_shipments) + len(rate_drifts),
            "anomalies": dup_shipments + rate_drifts
        }

# -----------------------------------------------------------------------------
# 6. WEBHOOKS & SIMULATION
# -----------------------------------------------------------------------------
@app.post("/api/webhooks/paypal")
async def receive_paypal_webhook(request: Request):
    """Authoritative PayPal Webhook listener endpoint with signature check and deduplication."""
    raw_body = await request.body()
    headers = dict(request.headers)

    with get_db() as conn:
        svc = WebhookService(conn)
        if not svc.verify_signature(headers, raw_body, paypal_adapter):
            record_audit_event(
                conn, "SECURITY", "WEBHOOK", "UNAUTHENTICATED_WEBHOOK_REJECTED", "GATEWAY",
                {"reason": "Invalid or missing webhook signature"}
            )
            raise HTTPException(status_code=401, detail="Webhook signature verification failed.")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON in webhook payload.")

        is_simulated = 1 if paypal_adapter.mode() != "LIVE_SANDBOX" else 0
        success, msg, data = svc.process_webhook_event(payload, is_simulated=is_simulated)
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

        payload_bytes = json.dumps(simulated_payload).encode("utf-8")
        sim_sig = generate_local_webhook_signature(payload_bytes)

        svc = WebhookService(conn)
        success, msg, data = svc.process_webhook_event(simulated_payload, is_simulated=1)
        return {
            "simulated": True,
            "event_id": event_id,
            "event_type": req.event_type,
            "signature": sim_sig,
            "message": msg,
            "reconciled_data": data
        }

# -----------------------------------------------------------------------------
# 7. AUTH & ROLES
# -----------------------------------------------------------------------------
@app.get("/api/auth/demo-users")
def get_demo_users():
    """Returns available demo user accounts with pre-signed session tokens."""
    users = []
    for email, profile in DEMO_USERS.items():
        token = create_token_for_user(profile["email"], profile["role"], profile["name"])
        users.append({**profile, "token": token})
    return users

@app.post("/api/auth/login")
def login_user(payload: Dict[str, Any]):
    email = payload.get("email", "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    if email in DEMO_USERS:
        profile = DEMO_USERS[email]
    else:
        role = payload.get("role", "CLERK").upper()
        name = payload.get("name", email.split("@")[0].title())
        profile = {
            "email": email,
            "name": name,
            "role": role,
            "title": f"Custom {role}",
            "can_approve": role in ("APPROVER_1", "APPROVER_2", "ADMIN")
        }
    token = create_token_for_user(profile["email"], profile["role"], profile["name"])
    return {"token": token, "user": profile}

@app.get("/api/auth/me")
def get_current_user_profile(user: Dict[str, Any] = Depends(get_current_user)):
    return user

# -----------------------------------------------------------------------------
# 8. AUDIT TRAIL & AGENT ACTIVITY
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
# 9. SETTINGS & SYSTEM DIAGNOSTICS
# -----------------------------------------------------------------------------
@app.get("/api/settings")
def get_settings():
    """Returns safe connection states and system diagnostics."""
    paypal_diag = paypal_adapter.get_mode_diagnostics()
    return {
        "app_mode": paypal_adapter.mode(),
        "paypal_mode": paypal_adapter.mode(),
        "paypal_client_id_masked": paypal_diag.get("client_id_masked", ""),
        "paypal": paypal_diag,
        "database": {
            "engine": "SQLite 3",
            "wal_mode": True,
            "foreign_keys": True,
            "status": "HEALTHY"
        },
        "ai_engine": {
            "active_provider": ai_service.active_provider(),
            "confidence_model": "EXACT_DECIMAL_RULE_EVALUATOR",
            "status": "OPERATIONAL"
        }
    }

@app.post("/api/settings")
def update_settings(req: SettingsUpdateSchema):
    """Updates in-memory runtime credentials without disk persistence."""
    from backend.paypal_adapter import set_runtime_paypal_credentials
    from backend.ai_service import set_runtime_keys

    set_runtime_paypal_credentials(
        client_id=req.paypal_client_id,
        client_secret=req.paypal_client_secret,
        webhook_id=req.paypal_webhook_id,
        failure_mode=req.simulate_failure_mode,
        forced_mode=req.mode,
    )
    set_runtime_keys(
        provider=req.ai_provider,
        groq_key=req.groq_api_key,
        gemini_key=req.gemini_api_key,
        openai_key=req.openai_api_key,
    )
    return {
        "status": "SUCCESS",
        "message": "Settings successfully updated in memory.",
        "settings": get_settings()
    }

@app.post("/api/settings/test-connection")
def test_connection():
    """Tests gateway connectivity for PayPal Sandbox."""
    return paypal_adapter.test_connection()

@app.get("/healthz")
def health_check():
    """Application health check endpoint for cloud and Docker deployments."""
    with get_db() as conn:
        conn.execute("SELECT 1").fetchone()
    return {
        "status": "HEALTHY",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paypal_mode": paypal_adapter.mode(),
        "ai_provider": ai_service.active_provider(),
    }

@app.post("/api/settings/reset-demo")
def reset_demo_data():
    """Resets all data back to the clean initial state."""
    populate_seed_data(reset=True)
    return {"status": "SUCCESS", "message": "Sample data reset successfully."}

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
