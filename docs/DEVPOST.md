# FreightGuard — Devpost Submission & Technical Dossier

**Autonomous Freight Invoice Audit, Evidence Intelligence & PayPal Sandbox Settlement**

- **Project Title:** FreightGuard
- **Tagline:** Every freight charge must be explainable, every discrepancy must be evidenced, and every payout must pass deterministic financial controls.
- **Repository:** [https://github.com/yatish-code26/PayPal.git](https://github.com/yatish-code26/PayPal.git)
- **Primary Domain:** Enterprise Logistics Fintech & Autonomous AP Operations

---

## 1. Inspiration
In North American and global logistics, freight spend exceeds **$800 Billion annually**, yet between **7% and 15% of all freight bills contain billing errors**, uncontracted accessorial charges, inflated fuel formulas, or duplicate billings. 

Traditional freight audit workflows rely on manual spreadsheets or clunky legacy third-party bureaus taking weeks to review bills. Carriers are either stiffed or shippers bleed millions of dollars in financial leakage. When disputes arise, AP clerks lack contractual proof, leading to protracted disputes and strained carrier relations.

We built **FreightGuard** to turn freight audit and settlement into an autonomous, evidence-driven financial control loop:
1. Ingest freight invoices (PDF or raw data).
2. Retrieve contractual rate card rules and telematics proof via local BM25 ranking.
3. Apply deterministic financial policy engines (cents-level exactness).
4. Synthesize natural-language explanations and formal dispute packets with AI.
5. Settle verified payable amounts automatically through the **PayPal Developer Platform Payouts API**.

---

## 2. What It Does
FreightGuard is an enterprise financial control tower that bridges invoice intelligence and automated payouts:

- **Evidence-to-Settlement Control Loop:** Automatically ingests bills, cross-references contracted Master Service Agreements (MSAs), validates Department of Energy (DOE) fuel peg rates, and audits against telematics physical evidence (dock types, dwell times, BOL matching).
- **The Core Differentiator ($2,180 Signature Demo):** On an ingested $5,522.00 bill from *Apex Global Freight*, FreightGuard autonomously flags:
  1. Base Freight Rate Mismatch (Billed $3,200.00 vs Contracted $2,800.00 = **$400.00** discrepancy).
  2. Diesel Fuel Surcharge Calculation Violation (Billed $740.00 vs DOE contracted 14% peg $392.00 = **$348.00** overcharge).
  3. Unauthorized Accessorial: Liftgate Delivery (Billed $182.00, but telematics proof confirmed delivery occurred at a commercial forklift dock = **$182.00** rejected).
  4. Duplicate Congestion Surcharge (Billed twice = **$1,250.00** discrepancy).
  - **Total Flagged:** Exactly **$2,180.00**.
  - **Net Verified Legitimate Payable:** Exactly **$3,342.00**.
- **AI-Grounded Dispute Generation:** Uses LLMs (Groq / Gemini / OpenAI) with BM25 contract clause citations to generate formal, audit-ready dispute letters with line-item mathematical calculation proof.
- **Deterministic PayPal Sandbox Settlement:** Executes verified payouts to carrier PayPal accounts with `PayPal-Request-Id` idempotency.
- **Real-Time Webhook Reconciliation:** Listens to PayPal sandbox webhook notifications (`PAYMENT.PAYOUTS-ITEM.SUCCEEDED`), verifies cryptographic signatures, deduplicates replay attempts, and transitions invoices to `RECONCILED`.

---

## 3. Core Architectural Philosophy: "AI Never Decides Money"
A central architectural tenet distinguishes FreightGuard from generic AI wrappers:

> **Financial invariant:** Large Language Models (LLMs) hallucinate, round floats, and exhibit probabilistic drift. Therefore, in FreightGuard, **AI NEVER DECIDES MONEY**.

- The AI layer is strictly confined to unstructured text extraction, semantic clause ranking, and drafting natural-language dispute letters.
- All monetary arithmetic is evaluated in **integer cents** by a deterministic Python policy engine.
- If an AI output attempts to modify an approved payable amount or variance figure, the backend policy gate intercepts, rejects, and logs the invariant violation to an immutable audit ledger.

---

## 4. PayPal Integration Architecture
FreightGuard integrates deeply with the **PayPal Developer Platform**:

1. **OAuth 2.0 Client Credentials Authentication:** Server-side acquisition and automatic caching of bearer tokens with proactive expiry refresh.
2. **Payouts API (`POST /v1/payments/payouts`):** Batch payout orchestration transferring verified net payable amounts directly to carrier email endpoints.
3. **Strict Idempotency Protection:** Generates durable `PayPal-Request-Id` keys tied to invoice numbers; duplicate payment attempts are returned as idempotent matches without re-executing transfers.
4. **Item-Level Querying (`GET /v1/payments/payouts-item/{id}`):** Granular tracking of individual payout status (`SUCCESS`, `UNCLAIMED`, `FAILED`, `BLOCKED`).
5. **Cryptographic Webhook Signature Verification:**
   - In `LIVE_SANDBOX` mode: calls PayPal's `POST /v1/notifications/verify-webhook-signature` using `PAYPAL_WEBHOOK_ID`.
   - In `LOCAL_DEMO` mode: validates local HMAC-SHA256 signatures to ensure 100% offline security testing.
   - Any unsigned or forged webhook is rejected with **HTTP 401 Unauthorized**.

---

## 5. Security & Governance Hardening
- **Role-Based Access Control (RBAC):** Cryptographically signed session tokens (`itsdangerous.URLSafeTimedSerializer`) for three distinct roles:
  - `AP Accounts Payable Specialist (Alex Mercer)`: Ingestion and audit only; financial authorization prohibited (HTTP 403).
  - `Finance Operations Lead (Sarah Chen)`: Approver 1 signoff authority.
  - `Corporate Controller (David Ross)`: Approver 2 signoff authority.
- **Segregation of Duties (Two-Man Rule):** Payouts exceeding dual-authorization thresholds require two distinct human approvers; the same individual cannot act as both Approver 1 and Approver 2.
- **Sliding-Window Rate Limiting:** In-memory rate limiting on settlement and payout endpoints to protect against brute-force replay or denial-of-service.
- **Restricted CORS Policy:** Strict origin whitelisting (`CORS_ALLOWED_ORIGINS`).
- **Append-Only Immutable Audit Trail:** Every audit event, state transition, authorization signoff, and payout is written to SQLite `audit_events`.

---

## 6. Zero API Key "Golden Rule"
Judges can run FreightGuard immediately with **zero external API keys**:
- Default `LOCAL_DEMO` mode executes realistic, high-fidelity offline simulations for both AI extraction and PayPal sandbox payouts.
- When credentials are provided (either in `.env` or dynamically via the Settings UI in memory), FreightGuard automatically activates live sandbox calls without requiring a server restart or persisting secrets to disk.

---

## 7. How We Built It
- **Backend:** FastAPI, Python 3.12+, Pydantic v2 schemas, SQLite 3 (WAL mode with foreign key enforcement), `pypdf` extraction, `itsdangerous` token signing.
- **Information Retrieval:** Dependency-free BM25 contract ranking algorithm (`tariff_engine.py`).
- **AI Service:** Unified OpenAI-compatible chat completion client supporting Groq (`llama-3.3-70b-versatile`), Google Gemini (`gemini-2.0-flash`), and OpenAI (`gpt-4o-mini`).
- **Frontend:** Responsive, zero-dependency ES6 vanilla architecture, custom CSS variables supporting Dark and Light theme toggle, SVG analytics charts, variance waterfall visualizer, and settlement stepper.
- **Testing:** 21 automated tests (`pytest`) covering invariants, DOE surcharge formulas, webhook deduplication, signature checks, and RBAC permissions.

---

## 8. 3-Minute Video Presentation Script (Second-by-Second)

| Time | Scene / Action | Spoken Narration |
| :--- | :--- | :--- |
| **0:00 - 0:25** | **Control Tower Dashboard** | "Over $800 Billion is spent on freight annually, and up to 15% of all bills contain billing discrepancies, uncontracted surcharges, or duplicate charges. Accounts payable teams either spend weeks manually cross-referencing contracts or bleed millions. Welcome to **FreightGuard**—an evidence-driven freight financial control tower powered by AI intelligence and the PayPal Developer Platform." |
| **0:25 - 0:55** | **Invoice Intelligence & Upload** | "Let's inspect our incoming freight stream. We can upload any carrier freight bill in PDF or text. Behind the scenes, our hybrid extraction engine parses line items while our local BM25 search engine matches the exact Master Service Agreement clauses. Notice our system principle: *AI never decides money*. All financial calculations are deterministically computed in integer cents." |
| **0:55 - 1:30** | **Evidence Workbench & AI Explanation** | "Here is our signature scenario: Apex Global Freight submitted Invoice 88419 for $5,522.00. FreightGuard runs an autonomous audit in milliseconds: it flags a $400 base rate inflation, a $348 DOE diesel fuel overcharge, an unauthorized $182 liftgate fee because telematics proved a forklift dock was used, and a $1,250 duplicate charge. Exactly $2,180.00 is flagged! Look at our Variance Waterfall: Net verified payable is exactly $3,342.00." |
| **1:30 - 2:05** | **Dispute Center with BM25 Citations** | "Instead of delaying payment or entering a shouting match with the carrier, FreightGuard prepares an evidence-grounded dispute packet. The LLM synthesizes a professional dispute notice citing exact contract sections like MSA Section 4.2 and Section 7.1, complete with line-item mathematical proof. We approve the dispute notice and hold back the disputed $2,180.00." |
| **2:05 - 2:35** | **Settlement Center & Two-Man Approval** | "Now to settlement. FreightGuard strictly enforces financial segregation of duties: AP clerks cannot authorize money. Our Operations Lead, Sarah Chen, signs off on Step 1, and our Corporate Controller, David Ross, authorizes Step 2. With our durable idempotency key locked, we click 'Execute PayPal Sandbox Payout'. In seconds, the PayPal Developer Payouts API executes the verified $3,342.00 transfer to Apex Global's PayPal account." |
| **2:35 - 3:00** | **Webhook Reconciliation & Wrap-Up** | "Instantly, a signed PayPal webhook event arrives. FreightGuard validates the cryptographic signature, deduplicates the event ID, and reconciles the invoice to RECONCILED. Every action is recorded in our append-only immutable audit trail. FreightGuard delivers total explainability, verifiable evidence, and automated PayPal settlement. Thank you!" |

---

## 9. Tools & API Disclosure
- **PayPal Developer Platform:** Payouts API (`/v1/payments/payouts`), OAuth 2.0 client credentials, webhook signature verification.
- **AI Models:** Groq (`llama-3.3-70b-versatile`), Google Gemini (`gemini-2.0-flash`), OpenAI (`gpt-4o-mini`).
- **Open-Source Software:** FastAPI, Uvicorn, Pydantic, PyPDF, PyTest, ItsDangerous.

