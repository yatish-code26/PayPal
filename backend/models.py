"""FreightGuard Pydantic Models & Request/Response Schemas
Provides strict validation for financial payloads and API endpoints.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class InvoiceItemSchema(BaseModel):
    id: str
    line_number: int
    charge_code: str
    description: str
    billed_cents: int
    expected_cents: int
    discrepancy_cents: int
    finding_status: str
    rule_reference: Optional[str] = None
    explanation: Optional[str] = None

class InvoiceSchema(BaseModel):
    id: str
    carrier_id: str
    carrier_name: Optional[str] = None
    shipment_id: Optional[str] = None
    invoice_number: str
    invoice_date: str
    due_date: str
    currency: str = "USD"
    total_billed_cents: int
    expected_amount_cents: int
    disputed_amount_cents: int
    approved_payable_cents: int
    held_amount_cents: int
    audit_status: str
    settlement_status: str
    created_at: str
    items: Optional[List[InvoiceItemSchema]] = None

class AuditFindingSchema(BaseModel):
    id: str
    invoice_id: str
    item_id: Optional[str] = None
    severity: str
    finding_type: str
    billed_cents: int
    permitted_cents: int
    variance_cents: int
    clause_citation: str
    contract_version: str
    telematics_evidence: str
    calculation_steps: List[str]
    ai_confidence_score: float

class AuditExecutionResult(BaseModel):
    invoice_id: str
    invoice_number: str
    carrier_name: str
    total_billed_cents: int
    approved_payable_cents: int
    disputed_amount_cents: int
    held_amount_cents: int
    audit_status: str
    findings_count: int
    findings: List[AuditFindingSchema]
    reconciliation_valid: bool
    summary_message: str

class DisputeGenerateRequest(BaseModel):
    invoice_id: str
    custom_message_notes: Optional[str] = None

class DisputeSchema(BaseModel):
    id: str
    invoice_id: str
    dispute_reference: str
    carrier_id: str
    carrier_name: Optional[str] = None
    status: str
    disputed_amount_cents: int
    carrier_contact_email: str
    formal_letter_text: str
    evidence_summary: str
    response_deadline: str
    credit_note_ref: Optional[str] = None
    created_at: str

class SettlementAuthorizeRequest(BaseModel):
    invoice_id: str
    first_approver: str = Field(..., min_length=2)
    second_approver: Optional[str] = None
    notes: Optional[str] = None

class SettlementPayoutRequest(BaseModel):
    invoice_id: str
    idempotency_key: str = Field(..., min_length=8)
    first_approver: str
    second_approver: Optional[str] = None
    simulate_failure: bool = False # For testing negative failure recovery

class WebhookSimulateRequest(BaseModel):
    event_type: str
    payout_item_id: Optional[str] = None
    payout_batch_id: Optional[str] = None
    event_id: Optional[str] = None

class SettingsUpdateSchema(BaseModel):
    mode: str = "LOCAL_DEMO" # LOCAL_DEMO | LIVE_SANDBOX
    paypal_client_id: Optional[str] = None
    paypal_client_secret: Optional[str] = None
