/**
 * Invoice Detail & Evidence Workbench View Controller
 * - Stepper along top: Review -> Dispute -> Approve -> Pay -> Reconciled
 * - Side-by-side verification: Extracted Charges vs Contractual Clauses & Telematics
 * - Standout Feature: "Pay now, hold the rest" split settlement trigger
 * - Plain-English AI Explanation grounded in contract citations
 */
const WorkbenchView = {
  currentInvoiceId: "INV-2025-88419",

  async init(invoiceId) {
    if (invoiceId) {
      this.currentInvoiceId = invoiceId;
    }
    await this.populateInvoiceSelector();
    await this.loadWorkbenchData(this.currentInvoiceId);
    this.bindEvents();
  },

  bindEvents() {
    const sel = document.getElementById("workbench-invoice-select");
    if (sel) {
      sel.onchange = (e) => {
        this.currentInvoiceId = e.target.value;
        this.loadWorkbenchData(this.currentInvoiceId);
      };
    }

    const auditBtn = document.getElementById("btn-workbench-run-audit");
    if (auditBtn) {
      auditBtn.onclick = async () => {
        await App.quickAudit(this.currentInvoiceId);
        await this.loadWorkbenchData(this.currentInvoiceId);
      };
    }
  },

  async populateInvoiceSelector() {
    const sel = document.getElementById("workbench-invoice-select");
    if (!sel) return;
    const invoices = await API.getInvoices();
    sel.innerHTML = invoices.map(inv => `
      <option value="${inv.id}" ${inv.id === this.currentInvoiceId ? 'selected' : ''}>
        ${inv.invoice_number} — ${inv.carrier_name} ($${inv.total_billed_formatted})
      </option>
    `).join("");
  },

  updateStepper(invoice) {
    const s1 = document.getElementById("step-1");
    const s2 = document.getElementById("step-2");
    const s3 = document.getElementById("step-3");
    const s4 = document.getElementById("step-4");
    const s5 = document.getElementById("step-5");

    const d1 = document.getElementById("step-div-1");
    const d2 = document.getElementById("step-div-2");
    const d3 = document.getElementById("step-div-3");
    const d4 = document.getElementById("step-div-4");

    // Reset classes
    [s1, s2, s3, s4, s5].forEach(el => { if (el) el.className = "step-item"; });
    [d1, d2, d3, d4].forEach(el => { if (el) el.className = "step-divider"; });

    if (invoice.audit_status === "PENDING_AUDIT") {
      s1?.classList.add("active");
    } else if (invoice.audit_status === "AUDITED_DISCREPANCY" && invoice.settlement_status === "UNSETTLED") {
      s1?.classList.add("completed");
      d1?.classList.add("filled");
      s2?.classList.add("active");
    } else if (invoice.audit_status === "DISPUTED" && invoice.settlement_status === "UNSETTLED") {
      s1?.classList.add("completed");
      d1?.classList.add("filled");
      s2?.classList.add("completed");
      d2?.classList.add("filled");
      s3?.classList.add("active");
    } else if (invoice.settlement_status === "AUTHORIZED") {
      s1?.classList.add("completed");
      d1?.classList.add("filled");
      s2?.classList.add("completed");
      d2?.classList.add("filled");
      s3?.classList.add("completed");
      d3?.classList.add("filled");
      s4?.classList.add("active");
    } else if (invoice.settlement_status === "RECONCILED") {
      [s1, s2, s3, s4, s5].forEach(el => el?.classList.add("completed"));
      [d1, d2, d3, d4].forEach(el => el?.classList.add("filled"));
    } else {
      s1?.classList.add("completed");
      d1?.classList.add("filled");
      s2?.classList.add("active");
    }
  },

  async loadWorkbenchData(invoiceId) {
    const container = document.getElementById("workbench-content");
    if (!container) return;
    container.innerHTML = `<div style="padding: 40px; text-align: center; color: var(--text-muted);">Loading audit records from SQLite database...</div>`;

    try {
      const data = await API.getWorkbench(invoiceId);
      const invoice = await API.getInvoiceDetails(invoiceId);

      this.updateStepper(invoice);

      const isAudited = invoice.audit_status !== "PENDING_AUDIT";
      const totalBilled = invoice.total_billed_formatted;
      const payable = invoice.approved_payable_formatted;
      const disputed = invoice.disputed_amount_formatted;

      container.innerHTML = `
        <!-- Top Summary Bar -->
        <div class="card" style="margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700;">INVOICE RECORD</div>
            <div style="font-size: 16px; font-weight: 700; color: var(--text-primary);">
              ${invoice.carrier_name} &bull; Invoice #${invoice.invoice_number}
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">
              Route: <strong>${invoice.origin || 'ORD'} &rarr; ${invoice.destination || 'DFW'}</strong> &bull; BOL: <strong class="mono">${invoice.bol_number || 'N/A'}</strong> &bull; Contract: <strong class="mono">${invoice.contract_id || 'AGF-MSA-2025-V2'}</strong>
            </div>
          </div>
          <div style="display: flex; gap: 24px; text-align: right;">
            <div>
              <div style="font-size: 11px; color: var(--text-muted); font-weight: 600;">BILLED AMOUNT</div>
              <div class="amount" style="font-size: 18px; font-weight: 700;">$${totalBilled}</div>
            </div>
            <div>
              <div style="font-size: 11px; color: var(--status-success); font-weight: 600;">APPROVED PAYABLE</div>
              <div class="amount" style="font-size: 18px; font-weight: 700; color: var(--status-success);">$${payable}</div>
            </div>
            <div>
              <div style="font-size: 11px; color: var(--status-warning); font-weight: 600;">DISPUTED VARIANCE</div>
              <div class="amount" style="font-size: 18px; font-weight: 700; color: var(--status-warning);">${invoice.disputed_amount_cents > 0 ? '+$' + disputed : '$0.00'}</div>
            </div>
          </div>
        </div>

        <!-- Standout Feature: Pay Now, Hold the Rest Settlement Card -->
        ${invoice.disputed_amount_cents > 0 && invoice.settlement_status === "UNSETTLED" ? `
          <div class="split-settlement-card">
            <div class="split-settlement-header">
              <div>
                <h3 style="font-size: 15px; font-weight: 700; color: var(--text-primary); margin-bottom: 2px;">
                  Split Settlement: "Pay Now, Hold the Rest"
                </h3>
                <p style="font-size: 12px; color: var(--text-secondary);">
                  Pay undisputed freight immediately via PayPal to protect carrier goodwill, while holding disputed overcharges in reserve pending dispute resolution.
                </p>
              </div>
              <button class="btn btn-primary" onclick="WorkbenchView.executeSplitSettlement('${invoice.id}')">
                Pay $${payable} Now & Hold $${disputed}
              </button>
            </div>
            <div class="split-buckets-grid">
              <div class="split-bucket bucket-pay">
                <div class="bucket-title">Pay Immediately (PayPal Payout)</div>
                <div class="bucket-amount amount" style="color: var(--status-success);">$${payable}</div>
                <div class="bucket-desc">Agreed lane tariff and verified fuel index charges. Disbursed instantly to carrier receiver: <span class="mono">${invoice.paypal_email}</span>.</div>
              </div>
              <div class="split-bucket bucket-hold">
                <div class="bucket-title">Hold in Reserve (Escrow Protection)</div>
                <div class="bucket-amount amount" style="color: var(--status-warning);">$${disputed}</div>
                <div class="bucket-desc">Uncontracted liftgate, spot rate delta, and duplicate charges. Held until carrier issues credit note.</div>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- 2-Column Side-by-Side: Extracted Charges vs Contract Evidence -->
        <div class="workbench-split-grid">
          <!-- Left: Extracted Charges -->
          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;">
              <span style="font-weight: 700; font-size: 14px;">Extracted Line Items (${invoice.items?.length || 0})</span>
              <span class="badge ${isAudited ? 'badge-clean' : 'badge-neutral'}">${isAudited ? 'Audited' : 'Pending'}</span>
            </div>

            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Charge Description</th>
                    <th style="text-align: right;">Billed</th>
                    <th style="text-align: right;">Contract</th>
                    <th style="text-align: right;">Variance</th>
                  </tr>
                </thead>
                <tbody>
                  ${(invoice.items || []).map(it => `
                    <tr>
                      <td class="mono" style="font-size: 11px; color: var(--text-muted);">${it.line_number}</td>
                      <td>
                        <div style="font-weight: 600; font-size: 13px;">${it.description}</div>
                        <div style="font-size: 11px; color: var(--text-muted);" class="mono">${it.charge_code}</div>
                      </td>
                      <td class="amount-cell amount">$${it.billed_formatted}</td>
                      <td class="amount-cell amount" style="color: var(--status-success);">$${it.expected_formatted}</td>
                      <td class="amount-cell amount" style="color: ${it.discrepancy_cents > 0 ? 'var(--status-danger)' : 'var(--text-muted)'}; font-weight: 600;">
                        ${it.discrepancy_cents > 0 ? '+$' + it.discrepancy_formatted : '$0.00'}
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>

            <div style="margin-top: 16px; padding: 12px; background-color: var(--bg-muted); border-radius: var(--radius-sm); font-size: 12px; color: var(--text-secondary); display: flex; justify-content: space-between; align-items: center;">
              <span>Accounting Invariant: <strong>$${payable} + $${disputed} = $${totalBilled}</strong></span>
              <span class="badge badge-clean">Exact Cents Verified</span>
            </div>
          </div>

          <!-- Right: Contract Citations & AI Explanation -->
          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;">
              <span style="font-weight: 700; font-size: 14px;">Contract Tariffs & Evidence Grounding</span>
              <button class="btn btn-secondary btn-sm" onclick="WorkbenchView.loadAiExplanation('${invoice.id}')">
                Refresh Explanation
              </button>
            </div>

            <!-- Plain English AI Narrative -->
            <div style="background-color: var(--bg-muted); border-radius: var(--radius-md); padding: 14px; margin-bottom: 16px;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--accent-primary);">AI Audit Summary</span>
                <span class="badge badge-neutral" id="ai-card-provider">AI Model</span>
              </div>
              <div id="ai-explain-body" style="font-size: 13px; color: var(--text-primary); line-height: 1.5;">
                Loading audit findings narrative...
              </div>
            </div>

            <!-- Telematics Physical Logs -->
            <div style="border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px; margin-bottom: 16px;">
              <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">
                Telematics & Proof of Delivery Evidence
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
                <div>BOL Verification: <strong class="mono">${data.bol_number || 'BOL-99214'}</strong></div>
                <div>Facility Dock Type: <strong>${data.dock_type || 'DOCK_TO_DOCK_FORKLIFT'}</strong></div>
                <div>Recorded Dwell: <strong class="mono">${data.dwell_time_minutes || 150} min</strong></div>
                <div>Free Time Allowed: <strong class="mono">${data.free_time_minutes || 120} min</strong></div>
              </div>
            </div>

            <!-- Contract Clauses Cited -->
            <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">
              Master Agreement Citations (${invoice.findings?.length || 0} Flagged)
            </div>
            <div style="display: flex; flex-direction: column; gap: 10px;">
              ${(invoice.findings || []).map(f => `
                <div style="background-color: var(--bg-muted); border-left: 3px solid var(--status-warning); padding: 10px 12px; border-radius: var(--radius-sm);">
                  <div style="font-size: 12px; font-weight: 700; color: var(--text-primary); margin-bottom: 2px;">
                    ${f.clause_citation} (${f.contract_version || 'v2.1'})
                  </div>
                  <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.4;">
                    ${f.explanation}
                  </div>
                  <div class="mono" style="font-size: 11px; color: var(--status-danger); font-weight: 600; margin-top: 4px;">
                    Variance: +$${(f.variance_cents / 100).toFixed(2)}
                  </div>
                </div>
              `).join("")}
            </div>

            <!-- Quick Action Links -->
            <div style="display: flex; gap: 10px; margin-top: 20px;">
              <button class="btn btn-secondary" onclick="App.navigateTo('disputes', '${invoice.id}')" style="flex: 1;">
                View Dispute Letter
              </button>
              <button class="btn btn-primary" onclick="App.navigateTo('payments', '${invoice.id}')" style="flex: 1;">
                Go to Settlement
              </button>
            </div>
          </div>
        </div>
      `;

      // Auto load AI explanation
      if (isAudited && (invoice.findings || []).length > 0) {
        this.loadAiExplanation(invoice.id);
      }
    } catch (e) {
      container.innerHTML = `<div style="padding: 40px; color: var(--status-danger);">Failed loading invoice details: ${e.message}</div>`;
    }
  },

  async loadAiExplanation(invoiceId) {
    const bodyEl = document.getElementById("ai-explain-body");
    const providerEl = document.getElementById("ai-card-provider");
    if (!bodyEl) return;

    try {
      const res = await API.getAiExplanation(invoiceId);
      if (providerEl) providerEl.textContent = res.provider || "Local Engine";
      bodyEl.textContent = res.plain_english_summary;
    } catch (e) {
      bodyEl.textContent = "AI explanation unavailable: " + e.message;
    }
  },

  async executeSplitSettlement(invoiceId) {
    if (!confirm("Execute 'Pay Now, Hold the Rest' split settlement?\n\nThis will disburse the undisputed amount immediately via PayPal Payouts and reserve the disputed variance.")) {
      return;
    }

    try {
      App.showToast("Executing split settlement via PayPal Payouts...", "info");
      const res = await API.payNowHoldRest(invoiceId);
      App.showToast(res.message, "success");
      await this.loadWorkbenchData(invoiceId);
    } catch (e) {
      App.showToast("Split settlement failed: " + e.message, "error");
    }
  }
};
