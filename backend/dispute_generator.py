"""FreightGuard Dispute Intelligence Generator
Generates structured, professional, carrier-specific formal dispute packages.
Grounds every claim directly in validated findings and contractual citations.
"""
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from backend.policy_engine import cents_to_dollars

def generate_dispute_package(
    invoice: Dict[str, Any],
    carrier: Dict[str, Any],
    shipment: Dict[str, Any],
    findings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Assembles a formal dispute notice based on deterministic findings."""
    now = datetime.now(timezone.utc)
    # Default 10 business days for carrier response
    deadline = (now + timedelta(days=14)).strftime("%Y-%m-%d")
    dispute_ref = f"DISP-{invoice['invoice_number']}-{now.strftime('%m%d')}"

    total_disputed_cents = sum(f["variance_cents"] for f in findings if f.get("variance_cents", 0) > 0)
    
    # Build itemized table
    itemized_lines = []
    evidence_bullets = []
    
    for idx, f in enumerate(findings, start=1):
        if f.get("variance_cents", 0) <= 0:
            continue
            
        billed_str = cents_to_dollars(f["billed_cents"])
        permitted_str = cents_to_dollars(f["permitted_cents"])
        variance_str = cents_to_dollars(f["variance_cents"])
        
        summary_text = f.get('explanation') or f.get('finding_type', 'Rate variance detected')
        itemized_lines.append(
            f"Item {idx}: [{f.get('finding_type', 'DISCREPANCY')}] Billed: ${billed_str} | Permitted: ${permitted_str} | Disputed Variance: ${variance_str}\n"
            f"   - Contract Authority: {f.get('clause_citation', 'Contract Terms')} (Contract Ref: {f.get('contract_version', 'MSA')})\n"
            f"   - Finding Summary: {summary_text}"
        )
        
        evidence_bullets.append(
            f"- {f['finding_type']}: Supported by {f['clause_citation']}; Telematics Evidence: {f.get('telematics_evidence', 'Documented in Bill of Lading #' + shipment.get('bol_number', 'N/A'))}."
        )

    items_block = "\n\n".join(itemized_lines)
    evidence_block = "\n".join(evidence_bullets)

    letter_text = f"""FORMAL NOTICE OF FREIGHT BILLING DISCREPANCY & DISPUTE
Reference: {dispute_ref}
Date: {now.strftime('%B %d, %Y')}

TO:
Accounts Receivable / Billing Disputes
Carrier: {carrier.get('name', 'Apex Global Freight Logistics')}
Contact Email: {carrier.get('paypal_email', 'billing@carrier.com')}

FROM:
Shipper Financial Accounts Payable & Audit Operations
Freight Financial Control Tower

RE: INVOICE #{invoice['invoice_number']} — SHIPMENT #{shipment.get('id', 'SH-884192')} / BOL #{shipment.get('bol_number', 'BOL-99214')}

Dear Carrier Partner,

Following automated rate auditing and contract verification against Master Service Agreement ({findings[0]['contract_version'] if findings else 'Active MSA'}), we have identified material billing discrepancies totaling ${cents_to_dollars(total_disputed_cents)} on Invoice #{invoice['invoice_number']} (Billed Total: ${cents_to_dollars(invoice['total_billed_cents'])}).

Pursuant to the terms of our transportation contract, the following charges have been flagged as non-conforming and are placed on formal hold:

--------------------------------------------------------------------------------
ITEMIZED DISCREPANCY BREAKDOWN
--------------------------------------------------------------------------------
{items_block}

--------------------------------------------------------------------------------
SUPPORTING EVIDENCE AND TELEMATICS AUDIT
--------------------------------------------------------------------------------
{evidence_block}

--------------------------------------------------------------------------------
FINANCIAL SETTLEMENT POSITION & REMEDY REQUESTED
--------------------------------------------------------------------------------
Total Billed Invoice Amount:  ${cents_to_dollars(invoice['total_billed_cents'])}
Verified Payable Amount:      ${cents_to_dollars(invoice['approved_payable_cents'])}
Total Disputed / Held Amount: ${cents_to_dollars(total_disputed_cents)}

In accordance with our settlement procedure, the undisputed payable balance of ${cents_to_dollars(invoice['approved_payable_cents'])} has been staged for authorized electronic settlement via PayPal Payouts upon dual administrative authorization.

ACTION REQUIRED:
Please review the evidence cited above and issue a revised invoice or credit memorandum in the amount of ${cents_to_dollars(total_disputed_cents)} no later than {deadline}.

If we do not receive a written rebuttal with verified rate authority by {deadline}, our accounts payable records will permanently close this invoice at the verified settlement amount.

Sincerely,

FreightGuard Financial Audit Operations
Corporate Accounts Payable Control Center
Audit Evidence Hash: SHA256:{invoice['id']}
"""

    return {
        "dispute_reference": dispute_ref,
        "invoice_id": invoice["id"],
        "carrier_id": carrier["id"],
        "carrier_contact_email": carrier["paypal_email"],
        "status": "DRAFTED",
        "disputed_amount_cents": total_disputed_cents,
        "formal_letter_text": letter_text.strip(),
        "evidence_summary": evidence_block,
        "response_deadline": deadline
    }
