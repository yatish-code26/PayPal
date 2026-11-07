# FreightGuard — Official 120-Second Demo Video Script & Presentation Guide

**Target Video Duration:** Exactly 2:00 (120 seconds)  
**Tone:** Confident, professional, clear, evidence-driven fintech presentation  
**Subtitles:** Embedded live in the app walkthrough and exported in `docs/demo-video-subtitles.srt`  
**Video Resolution:** 1080p (1920x1080) or 720p 60fps  

---

## Shot-by-Shot Video Script & Visual Actions

### Act 1: The Executive Problem & Home Dashboard (0:00 – 0:30)
| Timestamp | Visual Action on Screen | Voiceover / Narration |
|:---|:---|:---|
| **0:00 – 0:08** | Open on FreightGuard Home screen. Show clean fintech interface in light mode. Highlight the header and brand: *"Freight invoice audit and safe payments"*. | *"Welcome to FreightGuard: autonomous freight invoice audit, evidence intelligence, and safe PayPal settlement."* |
| **0:08 – 0:18** | Zoom/highlight the **"Needs Your Attention"** triage queue: 1 invoice to review, 1 dispute awaiting reply, 1 payment awaiting approval. | *"In enterprise logistics, 15 to 20 percent of freight bills contain off-tariff rates, fuel overcharges, or duplicate fees, leading to massive financial leakage."* |
| **0:18 – 0:30** | Mouse over the 4 big KPI cards and the horizontal reconciliation bar. Highlight the invariant badge: *"All figures reconciled in integer cents"*. | *"FreightGuard unifies every number into one source of truth. Notice our core invariant: $19,734 billed reconciles to the exact cent across approved payable, disputed overcharges, and held reserves."* |

---

### Act 2: Deep Invoice Audit & The $2,180 Signature Overcharge (0:30 – 0:50)
| Timestamp | Visual Action on Screen | Voiceover / Narration |
|:---|:---|:---|
| **0:30 – 0:40** | Click on **Invoice Detail (Workbench)** for `#INV-2025-88419` (Apex Global Freight). Point out the 5-step stepper: *Review $\to$ Dispute $\to$ Approve $\to$ Pay $\to$ Reconciled*. | *"Let’s inspect invoice 88419 from Apex Global Freight, which billed $5,522 for a 53-foot dry-van lane from Chicago to Dallas."* |
| **0:40 – 0:50** | Scroll down the line items table. Highlight the flagged variances: Base rate (+$600 off-tariff), Fuel surcharge (+$380 above DOE peg), Liftgate (+$350 unauthorized dock-to-dock), and Congestion (+$850 duplicate fee). | *"Our deterministic policy engine audits each line item against the Master Service Agreement and telematics dwell logs, isolating $2,180 in unauthorized overcharges while validating $3,342 in legitimate payable freight."* |

---

### Act 3: Policy Guard: AI Never Decides Money & Split Settlement (0:50 – 1:15)
| Timestamp | Visual Action on Screen | Voiceover / Narration |
|:---|:---|:---|
| **0:50 – 1:00** | Highlight the **Policy Guard Active** banner: *"AI drafts letters and explains findings, but all dollar calculations are deterministic in exact cents."* Show the plain-English AI narrative citing Clause 3.1 & 4.2. | *"Here is our core principle: AI Never Decides Money. LLMs explain findings and draft commercial correspondence, but all financial arithmetic is evaluated in integer cents by deterministic policy rules."* |
| **1:00 – 1:15** | Click the primary action button: **"Pay $3,342 Now & Hold $2,180"** on the Split Settlement card. Toast notification pops up: *"Split settlement executed! Status: PARTIALLY_SETTLED_HELD"*. | *"This enables our standout feature: 'Pay Now, Hold the Rest'. Instead of holding up the entire bill, we disburse the verified $3,342 immediately via PayPal Payouts to preserve carrier goodwill, holding the disputed $2,180 in reserve pending resolution."* |

---

### Act 4: AI Commercial Dispute Intelligence & PDF Export (1:15 – 1:30)
| Timestamp | Visual Action on Screen | Voiceover / Narration |
|:---|:---|:---|
| **1:15 – 1:23** | Navigate to **Disputes**. Show the formal commercial dispute letter citing Master Service Agreement Clauses 3.1, 4.2, and 6.4. | *"Next, FreightGuard’s AI synthesizes a formal commercial dispute notice citing exact contract clauses, DOE diesel index formulas, and facility dock records."* |
| **1:23 – 1:30** | Click **"Download PDF"**. Show the browser downloading `Dispute-INV-2025-88419.pdf`, generated on-the-fly with our pure-Python zero-dependency engine. | *"With one click, we export an official, audit-ready dispute notice PDF ready to send to the carrier’s billing department."* |

---

### Act 5: Controlled PayPal Payouts & Webhook Reconciliation (1:30 – 1:45)
| Timestamp | Visual Action on Screen | Voiceover / Narration |
|:---|:---|:---|
| **1:30 – 1:38** | Navigate to **Payments**. Show the Two-Person Financial Authorization panel (Sarah Chen, AP Lead & David Ross, Controller) with idempotency key (`PayPal-Request-Id`). | *"In the Payments Center, we enforce strict segregation of duties. High-value disbursements require two distinct signoffs with durable idempotency keys preventing duplicate transfers."* |
| **1:38 – 1:45** | Click **"Simulate Item Succeeded (200 OK)"** on the Webhook panel. Show the HMAC signature verification, event deduplication, and the invoice transitioning to `RECONCILED`. | *"PayPal webhooks verify cryptographic signatures, deduplicate event IDs, and automatically transition the settlement position to RECONCILED."* |

---

### Act 6: Carrier Scorecards & Tamper-Evident SHA-256 Audit Trail (1:45 – 2:00)
| Timestamp | Visual Action on Screen | Voiceover / Narration |
|:---|:---|:---|
| **1:45 – 1:53** | Navigate to **Carrier Scorecards**. Show Apex Global Freight’s 19.8% discrepancy rate, projected annual leakage ($26,160), and automated contract renewal talking points. | *"Carrier Scorecards track error frequencies across carriers, projecting annual financial leakage and providing automated negotiation talking points for contract renewals."* |
| **1:53 – 2:00** | Navigate to **Activity**. Click **"Verify Log Integrity"**. The green cryptographic shield badge appears: *"All audit events validated. SHA-256 links intact."* | *"Finally, our append-only audit trail uses SHA-256 hash chaining. One click verifies the entire cryptographic chain, providing tamper-proof evidence for corporate auditors. That is FreightGuard."* |

---

## Video Production & Presentation Tips
1. **Resolution:** 1080p (1920x1080) at 60 fps for smooth presentation.
2. **Audio:** High-quality microphone with voiceover matching the script above.
3. **Subtitles:** You can upload the included `docs/demo-video-subtitles.srt` directly as closed captions.
4. **Standalone Video:** You can stream or download `freightguard-demo.mp4` directly generated via `python generate_demo_video.py`.

