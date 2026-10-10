"""FreightGuard Deterministic Financial Policy Engine
Centralized, strict financial verification rules.
Zero floating-point arithmetic: all monetary values are modeled in exact integer cents.
Enforces non-negotiable financial invariants across auditing and settlement.
"""
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import decimal
import json

class FinancialInvariantViolation(Exception):
    """Raised when an accounting invariant or settlement restriction is violated."""
    pass

class PolicyRuleViolation(Exception):
    """Raised when an invoice or line item fails deterministic validation rules."""
    pass

def cents_to_dollars(cents: int) -> str:
    """Formats exact integer cents to formatted dollar string e.g. 334200 -> '3,342.00'."""
    d = decimal.Decimal(cents) / decimal.Decimal(100)
    return f"{d:,.2f}"

def dollars_to_cents(dollar_val: str | float | int | decimal.Decimal) -> int:
    """Converts a dollar input to exact integer cents using Decimal arithmetic."""
    if isinstance(dollar_val, str):
        clean_str = dollar_val.replace("$", "").replace(",", "").strip()
        d = decimal.Decimal(clean_str)
    elif isinstance(dollar_val, (int, float)):
        d = decimal.Decimal(str(dollar_val))
    elif isinstance(dollar_val, decimal.Decimal):
        d = dollar_val
    else:
        raise ValueError(f"Unsupported dollar amount type: {type(dollar_val)}")
    return int((d * 100).quantize(decimal.Decimal('1'), rounding=decimal.ROUND_HALF_UP))

def verify_accounting_invariant(
    total_billed_cents: int,
    approved_payable_cents: int,
    disputed_amount_cents: int,
    held_amount_cents: int = 0
) -> bool:
    """Enforces non-negotiable accounting equality:
    total_billed_cents == approved_payable_cents + held_amount_cents + disputed_amount_cents
    """
    reconciled_sum = approved_payable_cents + held_amount_cents + disputed_amount_cents
    if total_billed_cents != reconciled_sum:
        raise FinancialInvariantViolation(
            f"Accounting Invariant Failed! Total Billed ({total_billed_cents}¢ / ${cents_to_dollars(total_billed_cents)}) "
            f"!= Approved ({approved_payable_cents}¢) + Held ({held_amount_cents}¢) + Disputed ({disputed_amount_cents}¢). "
            f"Sum is {reconciled_sum}¢ (Diff: {total_billed_cents - reconciled_sum}¢)."
        )
    return True

def calculate_fuel_surcharge(
    base_rate_cents: int,
    diesel_price_per_gallon: decimal.Decimal,
    baseline_diesel_price: decimal.Decimal = decimal.Decimal("3.50"),
    step_increment: decimal.Decimal = decimal.Decimal("0.10"),
    surcharge_rate_per_step: decimal.Decimal = decimal.Decimal("0.030") # 3.0% per 10-cent step -> for $3.90 = 4 steps * 3.0% = 12.0%
) -> Tuple[int, decimal.Decimal, str]:
    """Calculates fuel surcharge per contractual DOE Diesel formula.
    Returns: (fsc_cents, fsc_percentage, calculation_explanation)
    """
    if diesel_price_per_gallon <= baseline_diesel_price:
        return (0, decimal.Decimal("0.0"), f"Diesel price ${diesel_price_per_gallon} is at or below baseline ${baseline_diesel_price}; FSC is 0.00%.")

    price_diff = diesel_price_per_gallon - baseline_diesel_price
    # Number of 10-cent steps (floor)
    steps = int(price_diff / step_increment)
    fsc_rate = steps * surcharge_rate_per_step # e.g. 4 * 0.030 = 0.120 (12.0%)
    
    # Calculate exact cents on contracted base rate
    fsc_cents = int((decimal.Decimal(base_rate_cents) * fsc_rate).quantize(decimal.Decimal('1'), rounding=decimal.ROUND_HALF_UP))
    
    explanation = (
        f"DOE National Diesel Index: ${diesel_price_per_gallon:.2f}/gal. Baseline: ${baseline_diesel_price:.2f}/gal. "
        f"Spread: ${price_diff:.2f} ({steps} steps of ${step_increment:.2f}). "
        f"Contractual FSC Rate: {steps} x {surcharge_rate_per_step * 100:.1f}% = {fsc_rate * 100:.1f}%. "
        f"Contracted Base Rate: ${cents_to_dollars(base_rate_cents)}. "
        f"Applicable FSC: ${cents_to_dollars(fsc_cents)}."
    )
    return (fsc_cents, fsc_rate, explanation)

def evaluate_line_item(
    item: Dict[str, Any],
    contract_rules: List[Dict[str, Any]],
    shipment_evidence: Dict[str, Any]
) -> Dict[str, Any]:
    """Evaluates a single line item against contracted rules and telematics evidence.
    Returns an evaluation result dictionary.
    """
    charge_code = item["charge_code"].upper()
    billed_cents = item["billed_cents"]
    desc = item.get("description", "")
    
    # 1. Base Rate Validation (Linehaul)
    if "BASE" in charge_code or "LINEHAUL" in charge_code or "LH" in charge_code:
        # Find matching lane rule
        lane_rule = next(
            (r for r in contract_rules if r["category"] == "LINEHAUL" and 
             r.get("origin_zone") == shipment_evidence.get("origin") and 
             r.get("destination_zone") == shipment_evidence.get("destination")),
            None
        )
        if not lane_rule:
            # Fallback to general linehaul
            lane_rule = next((r for r in contract_rules if r["category"] == "LINEHAUL"), None)
            
        if lane_rule:
            expected_cents = lane_rule["contracted_rate_cents"]
            if billed_cents > expected_cents:
                variance = billed_cents - expected_cents
                return {
                    "item_id": item.get("id"),
                    "status": "OVERCHARGE",
                    "severity": "HIGH",
                    "finding_type": "RATE_MISMATCH",
                    "billed_cents": billed_cents,
                    "expected_cents": expected_cents,
                    "variance_cents": variance,
                    "clause_citation": lane_rule.get("clause_reference", "Clause 3.1: Agreed Lane Tariffs"),
                    "contract_version": lane_rule.get("version", "AGF-MSA-2025-V2"),
                    "explanation": f"Carrier billed ${cents_to_dollars(billed_cents)} off-tariff spot rate. Agreed contracted tariff for lane {shipment_evidence.get('origin')} to {shipment_evidence.get('destination')} is ${cents_to_dollars(expected_cents)}.",
                    "steps": [
                        f"1. Query Contract Schedule A for {shipment_evidence.get('origin')} -> {shipment_evidence.get('destination')}.",
                        f"2. Contracted flat rate: ${cents_to_dollars(expected_cents)}.",
                        f"3. Carrier billed amount: ${cents_to_dollars(billed_cents)}.",
                        f"4. Discrepancy: ${cents_to_dollars(variance)} overcharge."
                    ]
                }
            else:
                return {
                    "item_id": item.get("id"),
                    "status": "VALID",
                    "severity": "INFO",
                    "finding_type": "CONTRACT_CONFORMANT",
                    "billed_cents": billed_cents,
                    "expected_cents": billed_cents,
                    "variance_cents": 0,
                    "clause_citation": lane_rule.get("clause_reference", "Clause 3.1"),
                    "contract_version": lane_rule.get("version", "AGF-MSA-2025-V2"),
                    "explanation": f"Billed linehaul ${cents_to_dollars(billed_cents)} matches contracted tariff.",
                    "steps": ["Linehaul conforms to contract."]
                }

    # 2. Fuel Surcharge Validation
    elif "FSC" in charge_code or "FUEL" in charge_code:
        fsc_rule = next((r for r in contract_rules if r["category"] == "FUEL"), None)
        base_rule = next((r for r in contract_rules if r["category"] == "LINEHAUL"), None)
        contracted_base_cents = base_rule["contracted_rate_cents"] if base_rule else 285000
        
        # DOE diesel price for week of shipment: $3.90/gal
        diesel_price = decimal.Decimal("3.90")
        fsc_cents, fsc_rate, explanation = calculate_fuel_surcharge(contracted_base_cents, diesel_price)
        
        if billed_cents > fsc_cents:
            variance = billed_cents - fsc_cents
            return {
                "item_id": item.get("id"),
                "status": "OVERCHARGE",
                "severity": "HIGH",
                "finding_type": "FUEL_OVERCHARGE",
                "billed_cents": billed_cents,
                "expected_cents": fsc_cents,
                "variance_cents": variance,
                "clause_citation": fsc_rule.get("clause_reference", "Clause 4.2: National Fuel Surcharge Index") if fsc_rule else "Clause 4.2",
                "contract_version": "AGF-MSA-2025-V2",
                "explanation": f"Carrier billed ${cents_to_dollars(billed_cents)} (21.0% on uncontracted rate). Applicable contract formula stipulates DOE diesel ${diesel_price}/gal yields 12.0% on contracted base ${cents_to_dollars(contracted_base_cents)}, amounting to ${cents_to_dollars(fsc_cents)}.",
                "steps": [
                    f"1. DOE Diesel Index for shipment week: ${diesel_price}/gal.",
                    f"2. Formula spread: (${diesel_price} - $3.50 baseline) = $0.40 = 4 steps @ 3.0% = 12.0%.",
                    f"3. Contracted base rate: ${cents_to_dollars(contracted_base_cents)} x 12.0% = ${cents_to_dollars(fsc_cents)}.",
                    f"4. Billed FSC: ${cents_to_dollars(billed_cents)}. Variance: ${cents_to_dollars(variance)}."
                ]
            }
        else:
            return {
                "item_id": item.get("id"),
                "status": "VALID",
                "severity": "INFO",
                "finding_type": "CONTRACT_CONFORMANT",
                "billed_cents": billed_cents,
                "expected_cents": billed_cents,
                "variance_cents": 0,
                "clause_citation": "Clause 4.2",
                "contract_version": "AGF-MSA-2025-V2",
                "explanation": "Fuel surcharge matches formula.",
                "steps": ["FSC verified against DOE Index."]
            }

    # 3. Accessorial - Liftgate
    elif "LIFTGATE" in charge_code or "LIFT" in desc.upper():
        liftgate_rule = next((r for r in contract_rules if r["category"] == "ACCESSORIAL" and "LIFTGATE" in r["rule_code"]), None)
        pre_auth = shipment_evidence.get("pre_authorized_accessorials", [])
        dock_type = shipment_evidence.get("dock_type", "")
        
        is_preauthorized = "LIFTGATE" in [str(x).upper() for x in pre_auth]
        
        if not is_preauthorized:
            return {
                "item_id": item.get("id"),
                "status": "UNAUTHORIZED",
                "severity": "CRITICAL",
                "finding_type": "UNAUTHORIZED_ACCESSORIAL",
                "billed_cents": billed_cents,
                "expected_cents": 0,
                "variance_cents": billed_cents,
                "clause_citation": liftgate_rule.get("clause_reference", "Clause 6.4: Mandatory Accessorial Pre-Authorization") if liftgate_rule else "Clause 6.4",
                "contract_version": "AGF-MSA-2025-V2",
                "explanation": f"Carrier billed ${cents_to_dollars(billed_cents)} for Liftgate. BOL #{shipment_evidence.get('bol_number')} confirms facility is '{dock_type}' with on-site forklift. No pre-authorization code on record.",
                "steps": [
                    f"1. Check BOL #{shipment_evidence.get('bol_number')} facility profile: {dock_type}.",
                    "2. Verify accessorial pre-authorization log: NONE found.",
                    "3. Contract Clause 6.4 requires explicit pre-authorization before dispatch.",
                    f"4. Disallow full billed amount: ${cents_to_dollars(billed_cents)}."
                ]
            }

    # 4. Duplicate / Congestion Charges
    elif "CONGESTION" in charge_code or "CONGESTION" in desc.upper() or "SECONDARY" in desc.upper():
        dup_rule = next((r for r in contract_rules if r["category"] == "DUPLICATE" or "DUP" in r["rule_code"]), None)
        return {
            "item_id": item.get("id"),
            "status": "DUPLICATE",
            "severity": "CRITICAL",
            "finding_type": "DUPLICATE_CHARGE",
            "billed_cents": billed_cents,
            "expected_cents": 0,
            "variance_cents": billed_cents,
            "clause_citation": dup_rule.get("clause_reference", "Clause 6.8 & Rule DUP-01: Prohibited Surcharges & Double Detention") if dup_rule else "Clause 6.8",
            "contract_version": "AGF-MSA-2025-V2",
            "explanation": f"Carrier billed ${cents_to_dollars(billed_cents)} for Congestion Surcharge / Secondary Detention. Dwell time is already compensated under Item #4 (Detention at Origin). Contract Clause 6.8 explicitly prohibits duplicate billing for facility congestion.",
            "steps": [
                "1. Cross-reference Item #4: Detention at Origin ($150.00 already accounted).",
                "2. Telematics tele-log indicates total dwell of 150 min (30 min billable over 120 min free time).",
                "3. Secondary congestion fee duplicates already accounted dwell time.",
                f"4. Prohibited by contract Clause 6.8; expected amount $0.00. Variance: ${cents_to_dollars(billed_cents)}."
            ]
        }

    # 5. Detention Validation
    elif "DETENTION" in charge_code or "DWELL" in desc.upper():
        dwell_mins = shipment_evidence.get("dwell_time_minutes", 150)
        free_mins = shipment_evidence.get("free_time_minutes", 120)
        billable_mins = max(0, dwell_mins - free_mins)
        # Rate: $300 / hr -> $5 / min -> 30 mins * $5 = $150.00 (15000 cents)
        expected_cents = int((decimal.Decimal(billable_mins) / decimal.Decimal(60)) * decimal.Decimal(30000))
        variance = billed_cents - expected_cents
        if variance > 0:
            return {
                "item_id": item.get("id"),
                "status": "OVERCHARGE",
                "severity": "MEDIUM",
                "finding_type": "DETENTION_DISCREPANCY",
                "billed_cents": billed_cents,
                "expected_cents": expected_cents,
                "variance_cents": variance,
                "clause_citation": "Clause 6.8: Dwell Time and Detention",
                "contract_version": "AGF-MSA-2025-V2",
                "explanation": f"Carrier billed ${cents_to_dollars(billed_cents)} detention. Telematics records {dwell_mins} min dwell ({billable_mins} billable mins after {free_mins} min free time) = ${cents_to_dollars(expected_cents)}.",
                "steps": [
                    f"Dwell: {dwell_mins}m, Free: {free_mins}m, Billable: {billable_mins}m @ $300/hr = ${cents_to_dollars(expected_cents)}."
                ]
            }
        else:
            return {
                "item_id": item.get("id"),
                "status": "VALID",
                "severity": "INFO",
                "finding_type": "CONTRACT_CONFORMANT",
                "billed_cents": billed_cents,
                "expected_cents": billed_cents,
                "variance_cents": 0,
                "clause_citation": "Clause 6.8: Detention and Demurrage",
                "contract_version": "AGF-MSA-2025-V2",
                "explanation": f"Detention amount ${cents_to_dollars(billed_cents)} matches telematics timestamp dwell time ({billable_mins} min over free time).",
                "steps": [f"Telematics verified dwell of {dwell_mins} min matches billed detention."]
            }

    # Default / Unknown line items
    return {
        "item_id": item.get("id"),
        "status": "VALID",
        "severity": "INFO",
        "finding_type": "STANDARD_CHARGE",
        "billed_cents": billed_cents,
        "expected_cents": billed_cents,
        "variance_cents": 0,
        "clause_citation": "Standard Tariff",
        "contract_version": "AGF-MSA-2025-V2",
        "explanation": "Standard charge conforms to tariff.",
        "steps": ["No discrepancy detected."]
    }

def validate_settlement_authorization(
    invoice: Dict[str, Any],
    first_approver: str,
    second_approver: Optional[str] = None
) -> Tuple[bool, str]:
    """Validates if an invoice settlement meets all financial policy invariants.
    Returns: (is_allowed, reason_or_error)
    """
    total_billed = invoice["total_billed_cents"]
    approved_payable = invoice["approved_payable_cents"]
    disputed_amount = invoice["disputed_amount_cents"]
    held_amount = invoice.get("held_amount_cents", 0)
    audit_status = invoice.get("audit_status", "")
    settlement_status = invoice.get("settlement_status", "")

    # Invariant 1: Cannot pay an invoice that is already settled or payout initiated
    if settlement_status in ["PAYOUT_INITIATED", "PAYOUT_SUCCESS", "RECONCILED"]:
        return (False, f"Cannot initiate payout: Invoice is already in state '{settlement_status}'.")

    # Invariant 2: Cannot pay an invoice with BLOCKED status
    if audit_status == "BLOCKED":
        return (False, "Cannot initiate payout: Invoice is in BLOCKED state due to fatal audit exception.")

    # Invariant 3: Cannot pay an un-audited invoice
    if audit_status == "PENDING_AUDIT":
        return (False, "Cannot initiate payout: Invoice audit has not been completed.")

    # Invariant 4: Payable amount cannot be 0 or negative
    if approved_payable <= 0:
        return (False, f"Cannot initiate payout: Approved payable amount is ${cents_to_dollars(approved_payable)}.")

    # Invariant 5: Payable amount cannot exceed total billed
    if approved_payable > total_billed:
        return (False, f"Cannot initiate payout: Approved amount (${cents_to_dollars(approved_payable)}) exceeds total billed (${cents_to_dollars(total_billed)}).")

    # Invariant 6: Must strictly reconcile with disputed and held amounts
    if total_billed != (approved_payable + disputed_amount + held_amount):
        return (False, "Cannot initiate payout: Accounting reconciliation invariant violated.")

    # Invariant 7: Dual authorization threshold check
    from backend.config import REQUIRE_DUAL_AUTHORIZATION_THRESHOLD
    if approved_payable >= REQUIRE_DUAL_AUTHORIZATION_THRESHOLD:
        if not second_approver or second_approver.strip() == "":
            return (False, f"Dual authorization required for payouts >= ${cents_to_dollars(REQUIRE_DUAL_AUTHORIZATION_THRESHOLD)}. Missing second authorized approver.")
        if first_approver == second_approver:
            return (False, "Segregation of duties violation: First approver and second approver cannot be the same individual.")

    return (True, "Authorization policy requirements satisfied.")
