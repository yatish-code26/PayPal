# FreightGuard
### Autonomous Freight Invoice Audit, Evidence Intelligence & PayPal Settlement
*Built for the PayPal AI Hackathon*

---

## 1. Executive Summary & Product Vision

**FreightGuard** is an evidence-driven freight financial control tower engineered for third-party logistics providers (3PLs), freight brokers, enterprise shippers, and accounts-payable departments. Freight logistics is plagued by widespread invoice leakage—industry studies show 15–20% of all freight bills contain discrepancies ranging from unauthorized accessorial surcharges and off-tariff spot rates to duplicate dwell penalties.

The central product guarantee:
> *"Every freight charge must be explainable, every discrepancy must be evidenced, and every payout must pass deterministic financial controls."*

FreightGuard replaces manual, error-prone spot-checking with an end-to-end **Evidence-to-Settlement Control Loop**:
1. **Invoice Ingestion & Extraction**: Line-item breakdown of linehauls, fuel surcharges, detention, and accessorials.
2. **Contract Intelligence (Tariff RAG)**: Indexed retrieval of Master Service Agreement (MSA) clauses, lane tariffs, and fuel index formulas.
3. **Telematics & Dock Verification**: Proof of delivery, bill of lading (BOL) profiles, and GPS geofence dwell logs.
4. **Deterministic Policy Validation**: Exact decimal cents arithmetic isolating verified payable balances from uncontracted charges.
5. **Carrier Dispute Intelligence**: Automated drafting of formal commercial dispute letters grounded in contract citations.
6. **Controlled PayPal Payout**: Two-man segregation of duties authorization and execution via PayPal Developer Platform Payouts (`POST /v1/payments/payouts`).
7. **Webhook-Driven Reconciliation**: Asynchronous state synchronization, idempotent replay protection, and audit logging.

---

## 2. Signature Demonstration Scenario: The $2,180 Overcharge

Carrier: **Apex Global Freight Logistics** (Fictional Carrier)  
Invoice: `#INV-2025-88419` | Shipment: `#SH-884192` (BOL `#BOL-99214`)  
Contract: `AGF-MSA-2025-V2` | Lane: Chicago, IL (ORD) &rarr; Dallas, TX (DFW), 53ft Dry Van

| # | Line Item Description | Billed Amount | Contracted / Expected | Flagged Variance | Contract Clause & Evidence Authority |
|---|---|---|---|---|---|
| **1** | Linehaul Base Rate | $3,450.00 | $2,850.00 | **+$600.00** | **Clause 3.1**: Agreed lane tariff violated; carrier billed off-tariff spot rate. |
| **2** | Fuel Surcharge (FSC) | $722.00 | $342.00 | **+$380.00** | **Clause 4.2**: DOE Diesel Index $3.90/gal yields 12.0% on contracted base ($2,850); carrier billed 21.0% on uncontracted base. |
| **3** | Destination Liftgate Service | $350.00 | $0.00 | **+$350.00** | **Clause 6.4**: Unauthorized accessorial. BOL verifies dock-to-dock forklift facility; no pre-auth dispatch code on record. |
| **4** | Origin Facility Detention | $150.00 | $150.00 | **$0.00** | **Clause 6.8**: Telematics records 150 min dwell (30 billable min over 120 min free time) @ $300/hr = $150.00. Conforms. |
| **5** | Secondary Congestion Surcharge | $850.00 | $0.00 | **+$850.00** | **Rule DUP-01 & Clause 6.8**: Prohibited duplicate fee. Congestion already accounted for under Detention. |
| | **TOTALS** | **$5,522.00** | **$3,342.00** | **+$2,180.00** | **Accounting Invariant: $3,342.00 Approved + $2,180.00 Disputed = $5,522.00 Total Billed** |

Every dollar, cent, and calculation step is verified with zero floating-point arithmetic.

---

## 3. System Architecture & Tech Stack

```
                          ┌─────────────────────────────────────┐
                          │     FreightGuard Executive UI       │
                          │   (Vanilla ES6, HTML5, Modern CSS)   │
                          └──────────────────┬──────────────────┘
                                             │ REST / JSON
                                             ▼
                          ┌─────────────────────────────────────┐
                          │      FastAPI Application Server     │
                          │        (Python 3.14.2 / Uvicorn)    │
                          └──────┬───────────┬────────────┬─────┘
                                 │           │            │
            ┌────────────────────┘           │            └───────────────────┐
            ▼                                ▼                                ▼
┌───────────────────────┐        ┌───────────────────────┐        ┌───────────────────────┐
│ Tariff RAG & Evidence │        │ Deterministic Policy  │        │ PayPal Payout Adapter │
│  - Contract Clauses   │        │  - Cents Arithmetic   │        │  - POST /v1/payments/ │
│  - Telematics & BOL   │        │  - Invariant Checks   │        │    payouts            │
│  - DOE Fuel Formulas  │        │  - Dual Signoff Guard │        │  - Webhook Listener   │
└───────────┬───────────┘        └───────────┬───────────┘        └───────────┬───────────┘
            │                                │                                │
            └────────────────────────────────┼────────────────────────────────┘
                                             ▼
                          ┌─────────────────────────────────────┐
                          │           SQLite Database           │
                          │   (WAL Mode + Foreign Key Enforce)  │
                          └─────────────────────────────────────┘
```

- **Backend**: Python 3.14.2, FastAPI 0.136.1, Uvicorn 0.47.0, Pydantic 2.13.4.
- **Database**: SQLite 3 with Write-Ahead Logging (WAL) and strict foreign keys.
- **Frontend**: Vanilla ES6, Semantic HTML5, and CSS3. Dark graphite fintech palette (`#0a0d14`), electric-cyan accents (`#00e5ff`), monospace financial numbers, and interactive SVG visualizers. Zero external CDN dependencies; 100% self-contained.
- **PayPal Integration**: Official PayPal Payouts API client (`POST /v1/payments/payouts`), idempotency key management (`PayPal-Request-Id`), and webhook state reconciler.

---

## 4. Deterministic Financial Invariants

The financial policy engine enforces strict system invariants:
1. **Accounting Equality**: `total_billed_cents == approved_payable_cents + disputed_amount_cents + held_amount_cents`.
2. **No Over-Payment**: Approved payable amount cannot exceed verified contractual tariff.
3. **No Unapproved Payments**: An un-audited or pending invoice cannot be staged for payment.
4. **Prohibition of Blocked Invoices**: Invoices flagged with fatal anomalies (such as duplicate shipments) are permanently frozen.
5. **Idempotency Guarantee**: Submitting identical idempotency keys returns the existing payout record without re-charging.
6. **Two-Man Authorization**: Payouts require distinct primary and secondary approvers to satisfy segregation of duties.

---

## 5. Quickstart & Installation

### Requirements
- Python 3.10+ (Verified on Python 3.14.2)
- Modern Web Browser (Chrome, Edge, Firefox, Safari)

### Step 1: Start the Local Application
```powershell
python run_server.py
```
The server will start at: **`http://127.0.0.1:8000`**

### Step 2: Open in Browser
Open `http://127.0.0.1:8000` in your web browser.

### Step 3: Run Automated Test Suite
```powershell
python -m pytest -v
```
All 10 test cases run in under 1 second, verifying cents arithmetic, fuel surcharge formulas, signature audit reconciliation, settlement authorization rules, PayPal idempotency, and webhook deduplication.

---

## 6. Three-Minute Judge Demonstration Walkthrough

1. **0:00 - 0:30: The Business Problem & Control Tower**
   - Open `http://127.0.0.1:8000`. Show the Executive Control Tower metrics ($19,734.00 total billed, $11,392.00 verified payable).
   - Point out invoice `#INV-2025-88419` from Apex Global Freight Logistics billed at $5,522.00.
2. **0:30 - 1:00: Autonomous Audit**
   - Click **"Execute $2,180 Signature Audit"** in the top header.
   - The audit engine flags 4 uncontracted charges totaling **$2,180.00**, isolating the legitimate payable balance of **$3,342.00**.
3. **1:00 - 1:45: Deep Evidence Traceability**
   - Click **"Workbench"** to enter the Evidence Workbench.
   - Inspect the side-by-side comparison:
     - Item 1: Off-tariff spot rate vs Clause 3.1 contracted flat lane rate ($600 overcharge).
     - Item 2: EIA/DOE Diesel fuel surcharge formula (12% contracted vs 21% billed = $380 overcharge).
     - Item 3: Unauthorized Liftgate vs BOL proof of dock-to-dock forklift facility ($350 overcharge).
     - Item 5: Prohibited secondary congestion fee duplicating dwell time ($850 duplicate).
4. **1:45 - 2:15: Dispute Generation**
   - Navigate to **"Dispute Center"**.
   - Review the generated formal commercial dispute letter citing contract references, calculation steps, and carrier response deadline.
   - Click **"Simulate Carrier Delivery"**.
5. **2:15 - 2:45: Financial Invariant Defense & Settlement**
   - Navigate to **"Settlement Center"**.
   - Click **"Test Pay Blocked Duplicate"** to demonstrate that the policy engine blocks unauthorized or corrupt payouts (HTTP 403 Forbidden).
   - Enter Dual Approvers (`sarah.chen@shipper.internal` and `david.ross@shipper.internal`) and click **"Authorize Settlement Intent"**.
   - Click **"Execute PayPal Sandbox Payout ($3,342.00)"**.
   - Inspect the returned PayPal Batch ID (`PAYPAL-SBX-BATCH-...`) and item status.
6. **2:45 - 3:00: Webhook Reconciliation**
   - Under the Webhook Simulator, click **"Simulate Item Succeeded"**.
   - Observe the final state transition: Invoice status becomes **RECONCILED**, and audit trail records the event.

---

## 7. Operational Modes & Honesty Statement

FreightGuard distinguishes between operational modes:
- **`LOCAL_DEMO` (Default)**: 100% offline, deterministic local simulation. Generates realistic PayPal batch/item IDs and response payloads labeled as `Local Sandbox Adapter (Simulation - No External Network)`. Requires zero external internet or credentials.
- **`LIVE_SANDBOX`**: Connects to `https://api-m.sandbox.paypal.com` using server-side OAuth (`client_id` and `client_secret`). Only activated when explicitly configured with user authorization.

---

## 8. License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
