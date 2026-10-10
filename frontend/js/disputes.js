/**
 * Dispute Center View Controller
 * Manages evidence-grounded carrier dispute letters, simulated submission,
 * and credit note reconciliation.
 */
const DisputesView = {
  currentInvoiceId: "INV-2025-88419",

  async init(invoiceId) {
    if (invoiceId) {
      this.currentInvoiceId = invoiceId;
    }
    await this.loadDisputeView(this.currentInvoiceId);
    this.bindEvents();
  },

  bindEvents() {
    const genBtn = document.getElementById("btn-generate-dispute-active");
    if (genBtn) {
      genBtn.onclick = async () => {
        try {
          await API.generateDispute(this.currentInvoiceId);
          App.showToast("Formal carrier dispute package generated successfully!", "success");
          await this.loadDisputeView(this.currentInvoiceId);
        } catch (e) {
          App.showToast(`Cannot generate dispute: ${e.message}`, "error");
        }
      };
    }
  },

  async loadDisputeView(invoiceId) {
    const container = document.getElementById("disputes-content");
    if (!container) return;
    container.innerHTML = `<div style="padding: 40px; text-align: center; color: var(--text-muted);">Loading dispute records...</div>`;

    try {
      const invoice = await API.getInvoiceDetails(invoiceId);
      const allDisputes = await API.getDisputes();
      const activeDispute = invoice.dispute;

      container.innerHTML = `
        <!-- Top Summary Banner -->
        <div class="settlement-reconciliation-bar" style="margin-bottom: 24px; border-left: 4px solid var(--status-warning);">
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700;">DISPUTE TARGET</div>
            <div style="font-size: 16px; font-weight: 700; color: var(--text-primary);">
              Carrier: ${invoice.carrier_name} &bull; Invoice #${invoice.invoice_number}
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">
              Carrier Billing Email: <strong class="mono">${invoice.paypal_email}</strong> &bull; Total Disputed: <strong class="mono" style="color: var(--status-warning);">$${invoice.disputed_amount_formatted}</strong>
            </div>
          </div>
          <div>
            ${activeDispute ? `
              <span class="badge ${activeDispute.status === 'ACCEPTED_CREDIT' ? 'badge-clean' : 'badge-discrepancy'}" style="font-size: 13px; padding: 6px 12px;">
                Status: ${activeDispute.status.replace('_', ' ')}
              </span>
            ` : `
              <span class="badge badge-pending">No Dispute Drafted</span>
            `}
          </div>
        </div>

        <div class="workbench-grid">
          <!-- Left: Formal Dispute Package Letter -->
          <div class="panel-card">
            <div class="panel-header">
              <span class="panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                Formal Carrier Dispute Notice (${activeDispute ? activeDispute.dispute_reference : 'Not Drafted'})
              </span>
              ${activeDispute ? `
                <button class="btn btn-secondary btn-sm" onclick="DisputesView.copyLetterText()">Copy Notice</button>
              ` : ''}
            </div>

            ${activeDispute ? `
              <div class="dispute-letter" id="dispute-letter-text">${activeDispute.formal_letter_text}</div>
              
              <div style="display: flex; gap: 10px; margin-top: 16px;">
                <button class="btn btn-primary btn-sm" onclick="DisputesView.simulateSubmission('${activeDispute.id}')" style="flex: 1;">
                  Simulate Carrier Delivery
                </button>
                <button class="btn btn-success btn-sm" onclick="DisputesView.promptCreditNote('${activeDispute.id}')" style="flex: 1;">
                  Record Accepted Credit Note
                </button>
              </div>
            ` : `
              <div style="padding: 40px; text-align: center; color: var(--text-muted); background-color: var(--bg-primary); border-radius: var(--radius-sm);">
                <p style="margin-bottom: 16px;">No dispute package exists yet for this invoice.</p>
                <button class="btn btn-primary" onclick="API.generateDispute('${invoice.id}').then(() => DisputesView.loadDisputeView('${invoice.id}'))">
                  Generate Formal Dispute Notice
                </button>
              </div>
            `}
          </div>

          <!-- Right: Dispute History & Credit Notes -->
          <div class="panel-card">
            <div class="panel-header">
              <span class="panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 14 14"></polyline></svg>
                Dispute Registry & Credit Notes (${allDisputes.length})
              </span>
              <span class="badge badge-clean">Active Portfolio</span>
            </div>

            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Ref</th>
                    <th>Invoice</th>
                    <th>Carrier</th>
                    <th>Disputed</th>
                    <th>Status</th>
                    <th>Credit Note</th>
                  </tr>
                </thead>
                <tbody>
                  ${allDisputes.map(d => `
                    <tr>
                      <td class="mono" style="font-size: 11px; font-weight: 700;">${d.dispute_reference}</td>
                      <td class="mono">${d.invoice_number}</td>
                      <td>${d.carrier_name}</td>
                      <td class="amount-cell mono" style="color: var(--status-warning); font-weight: 600;">
                        $${(d.disputed_amount_cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </td>
                      <td>
                        <span class="badge ${d.status === 'ACCEPTED_CREDIT' ? 'badge-clean' : 'badge-discrepancy'}">
                          ${d.status}
                        </span>
                      </td>
                      <td class="mono" style="font-size: 11px; color: var(--accent-cyan);">
                        ${d.credit_note_ref || '&mdash;'}
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>

            <div style="margin-top: 20px; padding: 14px; background-color: var(--bg-primary); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); font-size: 12px; color: var(--text-secondary);">
              <strong>Regulatory Integrity Policy:</strong> Carrier dispute communications are generated with strict contractual citations. Simulated carrier deliveries are clearly labeled to prevent false claims of external email transmission.
            </div>
          </div>
        </div>
      `;
    } catch (e) {
      container.innerHTML = `<div style="padding: 40px; color: var(--status-danger);">Failed loading dispute center: ${e.message}</div>`;
    }
  },

  copyLetterText() {
    const el = document.getElementById("dispute-letter-text");
    if (el) {
      navigator.clipboard.writeText(el.innerText);
      App.showToast("Dispute notice copied to clipboard!", "success");
    }
  },

  async simulateSubmission(disputeId) {
    try {
      await API.updateDisputeStatus(disputeId, "SUBMITTED_SIMULATED");
      App.showToast("Dispute marked as SUBMITTED_SIMULATED (Deterministic Local Mode).", "info");
      await this.loadDisputeView(this.currentInvoiceId);
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  promptCreditNote(disputeId) {
    const ref = prompt("Enter Carrier Credit Memorandum Reference:", "CN-2025-08-APX");
    if (ref) {
      API.updateDisputeStatus(disputeId, "ACCEPTED_CREDIT", ref).then(() => {
        App.showToast(`Carrier credit note ${ref} recorded! Discrepancy successfully resolved.`, "success");
        DisputesView.loadDisputeView(this.currentInvoiceId);
        ControlTowerView.loadStats();
      }).catch(err => {
        App.showToast(err.message, "error");
      });
    }
  }
};
