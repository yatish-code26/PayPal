"""FreightGuard Seed Data Module
Populates the SQLite database with rich, realistic, reproducible freight logistics data.
Includes the headline signature scenario ($2,180 discrepancy), clean audits, duplicate blocks,
and credit reconciliations.
"""
import json
from datetime import datetime, timezone
import sqlite3
from backend.database import get_db, init_db, record_audit_event

def populate_seed_data(reset: bool = True) -> None:
    """Populates initial records. If reset=True, wipes and recreates tables."""
    init_db()
    with get_db() as conn:
        if reset:
            # Clean all tables in safe order
            conn.executescript("""
                DELETE FROM audit_events;
                DELETE FROM webhook_events;
                DELETE FROM payout_records;
                DELETE FROM settlement_intents;
                DELETE FROM disputes;
                DELETE FROM audit_findings;
                DELETE FROM invoice_items;
                DELETE FROM invoices;
                DELETE FROM shipments;
                DELETE FROM tariff_rules;
                DELETE FROM contracts;
                DELETE FROM carriers;
            """)

        now_str = datetime.now(timezone.utc).isoformat()

        # 1. CARRIERS
        carriers = [
            ("carr_apex_01", "Apex Global Freight Logistics", "AGFL", "apex-settlement@sandbox.carrier.com", "REC-APXG-01", 1, now_str),
            ("carr_swift_02", "SwiftLine Freight Systems", "SWFT", "settlement@swiftline.example.com", "REC-SWFT-02", 1, now_str),
            ("carr_horizon_03", "Horizon Intermodal Express", "HZNM", "ap@horizon-intermodal.example.com", "REC-HZNM-03", 1, now_str),
            ("carr_titan_04", "Titan Specialized Freight", "TTAN", "billing@titan-freight.example.com", "REC-TTAN-04", 1, now_str),
        ]
        conn.executemany(
            "INSERT INTO carriers (id, name, scac, paypal_email, paypal_receiver_id, active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            carriers
        )

        # 2. CONTRACTS
        contracts = [
            (
                "AGF-MSA-2025-V2", "carr_apex_01", "Master Transportation Agreement 2025",
                "2025-01-01", "2025-12-31", "v2.1", "ACTIVE",
                "Master Service Agreement between Shipper AP and Apex Global Freight Logistics. Covers Midwest-Southwest dedicated dry van lanes.",
                now_str
            ),
            (
                "SLF-MSA-2025-V1", "carr_swift_02", "Southeast Regional Freight Agreement",
                "2025-01-01", "2025-12-31", "v1.0", "ACTIVE",
                "Covers dedicated Southeast lanes including Atlanta-Charlotte corridor.",
                now_str
            ),
            (
                "HZM-MSA-2025-V3", "carr_horizon_03", "Transcontinental Intermodal Service Agreement",
                "2025-01-01", "2025-12-31", "v3.2", "ACTIVE",
                "Intermodal rail and road drayage contract covering Chicago-Pacific Northwest corridor.",
                now_str
            ),
            (
                "TTN-MSA-2025-V1", "carr_titan_04", "Heavy Haul & Flatbed Transportation Contract",
                "2025-01-01", "2025-12-31", "v1.4", "ACTIVE",
                "Specialized freight contract with certified scale weight requirements.",
                now_str
            )
        ]
        conn.executemany(
            "INSERT INTO contracts (id, carrier_id, title, effective_start, effective_end, version, status, document_text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            contracts
        )

        # 3. TARIFF RULES FOR APEX (AGF-MSA-2025-V2)
        tariff_rules = [
            (
                "rule_apex_lh_01", "AGF-MSA-2025-V2", "RATE-ORD-DFW-01", "LINEHAUL",
                "Clause 3.1: Agreed Lane Tariffs",
                "Agreed flat linehaul rate for Chicago, IL (ORD) to Dallas, TX (DFW) 53ft Dry Van.",
                "Chicago, IL (ORD)", "Dallas, TX (DFW)", "53ft Dry Van", 285000, "FLAT_LANE",
                json.dumps({"lane": "ORD-DFW", "equipment": "53DV", "rate_dollars": 2850.00})
            ),
            (
                "rule_apex_fuel_01", "AGF-MSA-2025-V2", "FSC-DOE-INDEX-01", "FUEL",
                "Clause 4.2: National Fuel Surcharge Index",
                "Fuel surcharge pegged to EIA/DOE National Average Diesel Index. Baseline: $3.50/gal. Step: $0.10 increments @ 3.0% per step applied to contracted linehaul base.",
                None, None, None, 0, "DOE_FORMULA",
                json.dumps({"baseline": 3.50, "step": 0.10, "percent_per_step": 0.03})
            ),
            (
                "rule_apex_acc_01", "AGF-MSA-2025-V2", "ACC-LIFTGATE-AUTH-01", "ACCESSORIAL",
                "Clause 6.4: Mandatory Accessorial Pre-Authorization",
                "Liftgate and specialized handling charges must be pre-authorized with dispatch code and indicated on BOL prior to tender.",
                None, None, None, 0, "PRE_AUTH_REQUIRED",
                json.dumps({"requires_bol_annotation": True, "requires_code": True})
            ),
            (
                "rule_apex_det_01", "AGF-MSA-2025-V2", "ACC-DETENTION-01", "ACCESSORIAL",
                "Clause 6.8: Dwell Time and Detention",
                "Origin/destination dwell free time: 2 hours (120 minutes). Excess billable in 15-minute increments at $300.00/hr ($5.00/min).",
                None, None, None, 30000, "HOURLY_PRORATED",
                json.dumps({"free_minutes": 120, "hourly_cents": 30000})
            ),
            (
                "rule_apex_dup_01", "AGF-MSA-2025-V2", "DUP-SURCHARGE-PROHIBIT-01", "DUPLICATE",
                "Clause 6.8 & Rule DUP-01: Prohibited Surcharges & Double Detention",
                "Carriers may not bill secondary congestion fees, terminal delays, or separate dwell surcharges when standard detention is claimed.",
                None, None, None, 0, "PROHIBITED",
                json.dumps({"prohibited_charges": ["CONGESTION", "SECONDARY_DETENTION", "TERMINAL_DELAY"]})
            ),
            # SwiftLine rule
            (
                "rule_swift_lh_01", "SLF-MSA-2025-V1", "RATE-ATL-CLT-01", "LINEHAUL",
                "Clause 2.1: Southeast Core Lanes",
                "Flat linehaul for Atlanta, GA (ATL) to Charlotte, NC (CLT).",
                "Atlanta, GA (ATL)", "Charlotte, NC (CLT)", "53ft Dry Van", 185000, "FLAT_LANE",
                json.dumps({"rate_dollars": 1850.00})
            ),
            # Horizon rule
            (
                "rule_horizon_lh_01", "HZM-MSA-2025-V3", "RATE-ORD-SEA-01", "LINEHAUL",
                "Clause 4.1: Transcon Rail/Road Corridor",
                "Agreed tariff for Chicago, IL (ORD) to Seattle, WA (SEA).",
                "Chicago, IL (ORD)", "Seattle, WA (SEA)", "Intermodal Container", 375000, "FLAT_LANE",
                json.dumps({"rate_dollars": 3750.00})
            ),
            # Titan rule
            (
                "rule_titan_lh_01", "TTN-MSA-2025-V1", "RATE-LAX-DEN-01", "LINEHAUL",
                "Clause 5.1: Mountain Corridor Heavy Haul",
                "Flat rate for Los Angeles, CA (LAX) to Denver, CO (DEN) up to 10,000 lbs.",
                "Los Angeles, CA (LAX)", "Denver, CO (DEN)", "Flatbed", 210000, "FLAT_LANE",
                json.dumps({"rate_dollars": 2100.00, "max_weight_lbs": 10000})
            )
        ]
        conn.executemany(
            """INSERT INTO tariff_rules 
               (id, contract_id, rule_code, category, clause_reference, rule_description, origin_zone, destination_zone, equipment_type, contracted_rate_cents, formula_type, parameters_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            tariff_rules
        )

        # 4. SHIPMENTS & TELEMATICS EVIDENCE
        shipments = [
            (
                "SH-884192", "carr_apex_01", "BOL-99214",
                "Chicago, IL (ORD)", "Dallas, TX (DFW)",
                "2025-05-10T08:00:00Z", "2025-05-12T14:30:00Z",
                150, 120, 42500, "DOCK_TO_DOCK_FORKLIFT",
                json.dumps([]), 1
            ),
            (
                "SH-771020", "carr_swift_02", "BOL-77102",
                "Atlanta, GA (ATL)", "Charlotte, NC (CLT)",
                "2025-05-08T09:00:00Z", "2025-05-08T17:15:00Z",
                90, 120, 24000, "STANDARD_DOCK",
                json.dumps([]), 1
            ),
            (
                "SH-660140", "carr_horizon_03", "BOL-66014",
                "Chicago, IL (ORD)", "Seattle, WA (SEA)",
                "2025-05-02T10:00:00Z", "2025-05-06T16:00:00Z",
                110, 120, 38000, "RAIL_INTERMODAL",
                json.dumps([]), 1
            ),
            (
                "SH-551180", "carr_titan_04", "BOL-55118",
                "Los Angeles, CA (LAX)", "Denver, CO (DEN)",
                "2025-05-05T07:30:00Z", "2025-05-07T18:00:00Z",
                85, 120, 8500, "FLATBED_HEAVY",
                json.dumps([]), 1
            )
        ]
        conn.executemany(
            """INSERT INTO shipments 
               (id, carrier_id, bol_number, origin, destination, pickup_time, delivery_time, dwell_time_minutes, free_time_minutes, weight_lbs, dock_type, pre_authorized_accessorials_json, telematics_verified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            shipments
        )

        # 5. INVOICES
        # Signature Demo: INV-2025-88419 ($5,522.00 billed, $2,180.00 discrepancy, $3,342.00 payable)
        invoices = [
            (
                "INV-2025-88419", "carr_apex_01", "SH-884192", "INV-2025-88419",
                "2025-05-12", "2025-06-12", "USD",
                552200, 334200, 218000, 334200, 0,
                "PENDING_AUDIT", "UNSETTLED", now_str, now_str
            ),
            (
                "INV-2025-77102", "carr_swift_02", "SH-771020", "INV-2025-77102",
                "2025-05-08", "2025-06-08", "USD",
                185000, 185000, 0, 185000, 0,
                "AUDITED_CLEAN", "RECONCILED", now_str, now_str
            ),
            (
                "INV-2025-66014", "carr_horizon_03", "SH-660140", "INV-2025-66014",
                "2025-05-06", "2025-06-06", "USD",
                420000, 375000, 45000, 375000, 0,
                "AUDITED_DISCREPANCY", "RECONCILED", now_str, now_str
            ),
            (
                "INV-2025-99301", "carr_apex_01", "SH-884192", "INV-2025-99301", # Duplicate of SH-884192
                "2025-05-14", "2025-06-14", "USD",
                552200, 0, 0, 0, 552200,
                "BLOCKED", "UNSETTLED", now_str, now_str
            ),
            (
                "INV-2025-55118", "carr_titan_04", "SH-551180", "INV-2025-55118",
                "2025-05-07", "2025-06-07", "USD",
                264000, 210000, 54000, 210000, 0,
                "AUDITED_DISCREPANCY", "UNSETTLED", now_str, now_str
            )
        ]
        conn.executemany(
            """INSERT INTO invoices 
               (id, carrier_id, shipment_id, invoice_number, invoice_date, due_date, currency, total_billed_cents, expected_amount_cents, disputed_amount_cents, approved_payable_cents, held_amount_cents, audit_status, settlement_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            invoices
        )

        # 6. INVOICE LINE ITEMS FOR SIGNATURE DEMO (INV-2025-88419)
        # Sums to 552,200 cents ($5,522.00)
        signature_items = [
            (
                "item_88419_1", "INV-2025-88419", 1, "LINEHAUL",
                "Standard Dry Van Linehaul (ORD -> DFW)", 345000, 285000, 60000,
                "OVERCHARGE", "Clause 3.1", "Billed off-tariff spot rate. Contracted lane rate is $2,850.00."
            ),
            (
                "item_88419_2", "INV-2025-88419", 2, "FUEL_SURCHARGE",
                "Fuel Surcharge (DOE Diesel Index $3.90)", 72200, 34200, 38000,
                "OVERCHARGE", "Clause 4.2", "Calculated 21% on inflated base. Contract formula yields 12% on $2,850.00 ($342.00)."
            ),
            (
                "item_88419_3", "INV-2025-88419", 3, "ACC_LIFTGATE",
                "Destination Liftgate Service", 35000, 0, 35000,
                "UNAUTHORIZED", "Clause 6.4", "Facility has forklift docks; no liftgate authorization on BOL."
            ),
            (
                "item_88419_4", "INV-2025-88419", 4, "ACC_DETENTION",
                "Origin Facility Detention (30 min billable)", 15000, 15000, 0,
                "VALID", "Clause 6.8", "Dwell 150 min (30 min billable over 120 min free time) @ $300/hr = $150.00. Valid."
            ),
            (
                "item_88419_5", "INV-2025-88419", 5, "SURCHARGE_CONGESTION",
                "Secondary Congestion & Facility Delay Fee", 85000, 0, 85000,
                "DUPLICATE", "Clause 6.8 & Rule DUP-01", "Dwell time already compensated under Detention. Prohibited duplicate."
            )
        ]
        conn.executemany(
            """INSERT INTO invoice_items 
               (id, invoice_id, line_number, charge_code, description, billed_cents, expected_cents, discrepancy_cents, finding_status, rule_reference, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            signature_items
        )

        # Line items for Clean SwiftLine Invoice (INV-2025-77102)
        swift_items = [
            ("item_77102_1", "INV-2025-77102", 1, "LINEHAUL", "Dedicated Lanehaul (ATL -> CLT)", 185000, 185000, 0, "VALID", "Clause 2.1", "Matches contracted rate card.")
        ]
        conn.executemany(
            """INSERT INTO invoice_items 
               (id, invoice_id, line_number, charge_code, description, billed_cents, expected_cents, discrepancy_cents, finding_status, rule_reference, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            swift_items
        )

        # Line items for Titan Invoice (INV-2025-55118)
        titan_items = [
            ("item_55118_1", "INV-2025-55118", 1, "LINEHAUL", "Mountain Heavy Haul Flatbed", 210000, 210000, 0, "VALID", "Clause 5.1", "Standard flatbed base."),
            ("item_55118_2", "INV-2025-55118", 2, "OVERWEIGHT_SURCHARGE", "Dimensional Heavy Weight (12,000 lbs billed)", 54000, 0, 54000, "OVERCHARGE", "Clause 5.1", "Certified scale ticket #SC-9902 shows 8,500 lbs (under 10,000 lbs threshold).")
        ]
        conn.executemany(
            """INSERT INTO invoice_items 
               (id, invoice_id, line_number, charge_code, description, billed_cents, expected_cents, discrepancy_cents, finding_status, rule_reference, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            titan_items
        )

        # 7. SEED HISTORICAL SETTLEMENT & PAYOUT FOR SWIFT (CLEAN INVOICE)
        conn.execute(
            """INSERT INTO settlement_intents 
               (id, invoice_id, idempotency_key, carrier_id, approved_amount_cents, held_amount_cents, currency, receiver_email, first_approver, first_approved_at, second_approver, second_approved_at, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "si_swift_77102", "INV-2025-77102", "IDEM-SWIFT-77102-SETTLED", "carr_swift_02",
                185000, 0, "USD", "settlement@swiftline.example.com",
                "sarah.chen@shipper.internal", "2025-05-09T10:00:00Z",
                "david.ross@shipper.internal", "2025-05-09T11:15:00Z",
                "COMPLETED", "2025-05-09T11:15:00Z"
            )
        )
        conn.execute(
            """INSERT INTO payout_records 
               (id, settlement_intent_id, invoice_id, idempotency_key, paypal_batch_id, paypal_item_id, amount_cents, currency, receiver_email, batch_status, item_status, paypal_fee_cents, raw_paypal_response_json, is_simulated, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "pay_swift_01", "si_swift_77102", "INV-2025-77102", "IDEM-SWIFT-77102-SETTLED",
                "PAYPAL-SBX-BATCH-991A4F", "PAYPAL-SBX-ITEM-881B2C", 185000, "USD",
                "settlement@swiftline.example.com", "SUCCESS", "SUCCESS", 25,
                json.dumps({"batch_status": "SUCCESS", "item_status": "SUCCESS"}),
                1, "2025-05-09T11:20:00Z", "2025-05-09T11:20:00Z"
            )
        )

        # 7.5 SEED HISTORICAL DISPUTE
        conn.execute(
            """INSERT INTO disputes 
               (id, invoice_id, dispute_reference, carrier_id, status, disputed_amount_cents, carrier_contact_email, formal_letter_text, evidence_summary, response_deadline, credit_note_ref, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "disp_titan_55118", "INV-2025-55118", "DISP-2025-55118", "carr_titan_04",
                "PENDING_CARRIER_REVIEW", 54000, "billing@titan-freight.example.com",
                "Formal Notice of Contractual Freight Rate Discrepancy for Invoice #INV-2025-55118.\nDisputed amount: $540.00.\nEvidence: Scale ticket indicates gross weight 8,500 lbs, within contractual allowance per Clause 5.1.",
                "Overweight surcharge of $540.00 billed without scale ticket verification.",
                "2025-06-15T00:00:00Z", None, "2025-05-08T14:30:00Z", "2025-05-08T14:30:00Z"
            )
        )

        # 8. SEED AUDIT TRAIL LOGS
        record_audit_event(conn, "SYSTEM", "SYS-INIT", "DATABASE_SEEDED", "SYSTEM_ENGINE", {"status": "SUCCESS", "invoices_count": 5})
        record_audit_event(conn, "INVOICE", "INV-2025-88419", "INVOICE_INGESTED", "DOCUMENT_PARSER", {"carrier": "AGFL", "billed": 552200, "currency": "USD"})
        record_audit_event(conn, "INVOICE", "INV-2025-77102", "SETTLEMENT_RECONCILED", "PAYPAL_SANDBOX", {"paypal_batch_id": "PAYPAL-SBX-BATCH-991A4F", "amount": 185000})

        print("Database seeded successfully with 5 invoices, contracts, telematics, and audit trails!")

if __name__ == "__main__":
    populate_seed_data(reset=True)
