/**
 * Dispute Center View Controller
 * - Cites exact Master Service Agreement clauses
 * - One-click PDF notice export (/api/disputes/{id}/export-pdf)
 * - Standout Feature: Dispute resolution with carrier credit note and held reserve release
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
          App.showToast("Formal carrier dispute notice generated with contract citations!", "success");
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
        <!-- Top Summary Bar -->
        <div class="card" style="margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700;">ACTIVE DISPUTE TARGET</div>
            <div style="font-size: 16px; font-weight: 700; color: var(--text-primary);">
              Carrier: ${invoice.carrier_name} &bull; Invoice #${invoice.invoice_number}
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">
              Carrier Billing Email: <strong class="mono">${invoice.paypal_email}</strong> &bull; Total Disputed: <strong class="amount" style="color: var(--status-warning);">$${invoice.disputed_amount_formatted}</strong>
            </div>
          </div>
          <div>
            ${activeDispute ? `
              <span class="badge ${activeDispute.status === 'ACCEPTED_CREDIT' || activeDispute.status === 'RESOLVED_CREDITED' ? 'badge-clean' : 'badge-discrepancy'}" style="font-size: 13px; padding: 6px 14px;">
                Status: ${activeDispute.status.replace(/_/g, ' ')}
              </span>
            ` : `
              <span class="badge badge-neutral" style="font-size: 13px; padding: 6px 14px;">No Dispute Drafted</span>
            `}
          </div>
        </div>

        <div class="workbench-split-grid">
          <!-- Left: Formal Dispute Package Letter & PDF Export -->
          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;">
              <span style="font-weight: 700; font-size: 14px;">
                Formal Dispute Notice ${activeDispute ? `(${activeDispute.dispute_reference})` : ''}
              </span>
              <div style="display: flex; gap: 8px;">
                ${activeDispute ? `
                  <a href="/api/disputes/${encodeURIComponent(activeDispute.id)}/export-pdf" download class="btn btn-secondary btn-sm" title="Download official PDF Notice">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    Download PDF
                  </a>
                  <button class="btn btn-secondary btn-sm" onclick="DisputesView.copyLetterText()">Copy Text</button>
                ` : ''}
              </div>
            </div>

            ${activeDispute ? `
              <div class="dispute-letter-box" id="dispute-letter-text">${activeDispute.formal_letter_text}</div>
              
              <div style="display: flex; gap: 10px; margin-top: 16px;">
                <button class="btn btn-secondary btn-sm" onclick="DisputesView.simulateCarrierReview('${activeDispute.id}')" style="flex: 1;">
                  Send to Carrier
                </button>
                <button class="btn btn-success btn-sm" onclick="DisputesView.resolveWithCreditNote('${activeDispute.id}')" style="flex: 1;">
                  Accept Credit Note & Reconcile
                </button>
              </div>
            ` : `
              <div style="padding: 40px; text-align: center; color: var(--text-muted); background-color: var(--bg-muted); border-radius: var(--radius-sm);">
                <p style="margin-bottom: 16px; font-size: 13px;">No formal dispute notice has been drafted yet for this invoice.</p>
                <button class="btn btn-primary" onclick="API.generateDispute('${invoice.id}').then(() => DisputesView.loadDisputeView('${invoice.id}'))">
                  Generate Formal Dispute Notice
                </button>
              </div>
            `}
          </div>

          <!-- Right: Dispute Registry & Credit Notes -->
          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;">
              <span style="font-weight: 700; font-size: 14px;">Dispute Registry (${allDisputes.length})</span>
              <span class="badge badge-clean">Active Portfolio</span>
            </div>

            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Ref</th>
                    <th>Invoice</th>
                    <th>Carrier</th>
                    <th style="text-align: right;">Disputed</th>
                    <th>Status</th>
                    <th>PDF</th>
                  </tr>
                </thead>
                <tbody>
                  ${allDisputes.map(d => `
                    <tr>
                      <td><strong class="mono">${d.dispute_reference}</strong></td>
                      <td class="mono">${d.invoice_number}</td>
                      <td>${d.carrier_name}</td>
                      <td class="amount-cell amount" style="color: var(--status-warning); font-weight: 600;">
                        $${(d.disputed_amount_cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </td>
                      <td>
                        <span class="badge ${d.status === 'ACCEPTED_CREDIT' || d.status === 'RESOLVED_CREDITED' ? 'badge-clean' : 'badge-discrepancy'}">
                          ${d.status.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td>
                        <a href="/api/disputes/${encodeURIComponent(d.id)}/export-pdf" download class="btn btn-secondary btn-sm" style="padding: 2px 8px; font-size: 11px;">PDF</a>
                      </td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>

            <div style="margin-top: 16px; padding: 12px; background-color: var(--bg-muted); border-radius: var(--radius-sm); font-size: 12px; color: var(--text-secondary);">
              <strong>Regulatory Integrity Policy:</strong> All carrier dispute communications cite exact contract clauses from Master Service Agreements. When a carrier issues a credit memo, accepting it releases the held reserve and moves the invoice to RECONCILED.
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

  async simulateCarrierReview(disputeId) {
    try {
      await API.updateDisputeStatus(disputeId, "PENDING_CARRIER_REVIEW");
      App.showToast("Dispute marked as SENT / PENDING_CARRIER_REVIEW.", "info");
      await this.loadDisputeView(this.currentInvoiceId);
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  async resolveWithCreditNote(disputeId) {
    const ref = prompt("Enter Carrier Credit Memorandum Reference number:", "CN-2025-08-APX");
    if (!ref) return;

    try {
      App.showToast("Recording credit note and releasing held reserve...", "info");
      const res = await API.resolveDispute(disputeId, ref);
      App.showToast(res.message, "success");
      await this.loadDisputeView(this.currentInvoiceId);
      await ControlTowerView.loadStats();
    } catch (e) {
      App.showToast(e.message, "error");
    }
  }
};
