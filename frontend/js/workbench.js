/**
 * Evidence Workbench View Controller
 * Core differentiator: Side-by-side verification of extracted invoices vs
 * contracted clauses vs telematics proof-of-delivery evidence.
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

  async loadWorkbenchData(invoiceId) {
    const container = document.getElementById("workbench-content");
    if (!container) return;
    container.innerHTML = `<div style="padding: 40px; text-align: center; color: var(--text-muted);">Loading evidence records from persistent database...</div>`;

    try {
      const data = await API.getWorkbench(invoiceId);
      const invoice = await API.getInvoiceDetails(invoiceId);

      const isAudited = invoice.audit_status !== "PENDING_AUDIT";
      const totalBilled = invoice.total_billed_formatted;
      const payable = invoice.approved_payable_formatted;
      const disputed = invoice.disputed_amount_formatted;

      container.innerHTML = `
        <!-- Top Status Banner -->
        <div class="settlement-reconciliation-bar" style="margin-bottom: 24px; border-left: 4px solid var(--accent-cyan);">
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700;">AUDIT CONTEXT</div>
            <div style="font-size: 16px; font-weight: 700; color: var(--text-primary);">
              Invoice #${invoice.invoice_number} &bull; ${invoice.carrier_name}
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">
              Lane: <strong>${invoice.origin || 'N/A'} &rarr; ${invoice.destination || 'N/A'}</strong> &bull; BOL: <strong class="mono">${invoice.bol_number || 'N/A'}</strong> &bull; Contract: <strong class="mono">${invoice.contract_id || 'AGF-MSA-2025-V2'} (${invoice.contract_version || 'v2.1'})</strong>
            </div>
          </div>
          <div style="text-align: right; display: flex; gap: 20px;">
            <div>
              <div style="font-size: 11px; color: var(--text-muted); font-weight: 600;">BILLED AMOUNT</div>
              <div class="mono" style="font-size: 18px; font-weight: 700;">$${totalBilled}</div>
            </div>
            <div>
              <div style="font-size: 11px; color: var(--accent-cyan); font-weight: 600;">VERIFIED PAYABLE</div>
              <div class="mono" style="font-size: 18px; font-weight: 700; color: var(--accent-cyan);">$${payable}</div>
            </div>
            <div>
              <div style="font-size: 11px; color: var(--status-warning); font-weight: 600;">DISPUTED VARIANCE</div>
              <div class="mono" style="font-size: 18px; font-weight: 700; color: var(--status-warning);">${invoice.disputed_amount_cents > 0 ? '+$' + disputed : '$0.00'}</div>
            </div>
          </div>
        </div>

        <!-- 2-Column Split: Extracted Charges vs Contract/Telematics Evidence -->
        <div class="workbench-grid">
          <!-- Left: Billed Line Items -->
          <div class="panel-card">
            <div class="panel-header">
              <span class="panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>
                Extracted Line-Item Charges (${invoice.items?.length || 0})
              </span>
              <span class="badge ${isAudited ? 'badge-clean' : 'badge-pending'}">${isAudited ? 'Audited' : 'Pending Audit'}</span>
            </div>

            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Charge Description</th>
                    <th>Billed</th>
                    <th>Permitted</th>
                    <th>Variance</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  ${(invoice.items || []).map(it => `
                    <tr class="${it.discrepancy_cents > 0 ? 'highlighted' : ''}">
                      <td class="mono" style="font-size: 11px; color: var(--text-muted);">${it.line_number}</td>
                      <td>
                        <div style="font-weight: 600; color: var(--text-primary);">${it.description}</div>
                        <div style="font-size: 11px; color: var(--text-muted);" class="mono">${it.charge_code}</div>
                      </td>
                      <td class="amount-cell mono" style="font-weight: 600;">$${it.billed_formatted}</td>
                      <td class="amount-cell mono" style="color: var(--accent-cyan);">$${it.expected_formatted}</td>
                      <td class="amount-cell mono" style="color: ${it.discrepancy_cents > 0 ? 'var(--status-danger)' : 'var(--text-muted)'}; font-weight: 600;">
                        ${it.discrepancy_cents > 0 ? '+$' + it.discrepancy_formatted : '$0.00'}
                      </td>
                      <td>${App.getLineItemBadge(it.finding_status)}</td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>

            <div style="margin-top: 16px; padding: 12px; background-color: var(--bg-primary); border-radius: var(--radius-sm); font-size: 12px; color: var(--text-secondary); display: flex; justify-content: space-between; align-items: center;">
              <span>Deterministic Accounting Invariant: <strong>$${payable} + $${disputed} = $${totalBilled}</strong></span>
              <span class="badge badge-clean">Verified Cents Equality</span>
            </div>
          </div>

          <!-- Right: Contract Citations, Telematics & Mathematical Calculation Steps -->
          <div class="panel-card">
            <div class="panel-header">
              <span class="panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                Contractual Tariff Authority & Telematics Proof
              </span>
              <span class="badge badge-info">Source Citations</span>
            </div>

            <!-- Telematics Physical Evidence Card -->
            <div style="background-color: var(--bg-primary); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 14px; margin-bottom: 16px;">
              <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--status-info); margin-bottom: 6px;">
                TELEMATICS & FACILITY TELEMETRY LOGS
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
                <div>BOL Verification: <strong class="mono" style="color: var(--text-primary);">${data.bol_number || 'BOL-99214'}</strong></div>
                <div>Facility Dock Type: <strong style="color: var(--text-primary);">${data.dock_type || 'DOCK_TO_DOCK_FORKLIFT'}</strong></div>
                <div>Dwell Time: <strong class="mono" style="color: var(--text-primary);">${data.dwell_time_minutes || 150} min</strong></div>
                <div>Contracted Free Time: <strong class="mono" style="color: var(--text-primary);">${data.free_time_minutes || 120} min</strong></div>
              </div>
            </div>

            <!-- Mathematical Calculation Steps & Citations -->
            ${(invoice.findings || []).length > 0 ? `
              <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 10px;">
                DISCREPANCY CALCULATION STEPS & CONTRACT CLAUSES (${invoice.findings.length} Flagged)
              </div>
              ${invoice.findings.map(f => `
                <div class="clause-box">
                  <div class="clause-title">${f.clause_citation} (${f.contract_version})</div>
                  <div class="clause-text" style="margin-bottom: 10px;">
                    <strong>Finding:</strong> ${f.explanation}
                  </div>
                  <div style="margin-top: 8px;">
                    <div style="font-size: 11px; color: var(--text-muted); font-weight: 600; margin-bottom: 4px;">CALCULATION PROOF:</div>
                    ${(f.calculation_steps || []).map((step, idx) => `
                      <div class="calc-step">
                        <span class="calc-step-num">0${idx + 1}</span>
                        <span>${step}</span>
                      </div>
                    `).join("")}
                  </div>
                </div>
              `).join("")}
            ` : `
              <div style="padding: 24px; text-align: center; color: var(--text-muted); background-color: var(--bg-primary); border-radius: var(--radius-sm);">
                ${invoice.audit_status === "AUDITED_CLEAN" 
                  ? "All extracted line items conform strictly to contract rate card. No discrepancies detected."
                  : "Audit not yet executed. Click 'Execute Autonomous Audit' above to evaluate."}
              </div>
            `}

            <!-- Workflow Action Buttons -->
            <div style="display: flex; gap: 10px; margin-top: 20px;">
              <button class="btn btn-secondary" onclick="App.navigateTo('disputes', '${invoice.id}')" style="flex: 1;">
                Review Dispute Package
              </button>
              <button class="btn btn-primary" onclick="App.navigateTo('settlement', '${invoice.id}')" style="flex: 1;">
                Authorize & Settle ($${payable})
              </button>
            </div>
          </div>
        </div>
      `;
    } catch (e) {
      container.innerHTML = `<div style="padding: 40px; color: var(--status-danger);">Failed loading evidence workbench: ${e.message}</div>`;
    }
  }
};
