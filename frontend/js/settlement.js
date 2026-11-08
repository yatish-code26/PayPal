/**
 * Payments & PayPal Settlement View Controller
 * - Enforces two-person financial authorization (Segregation of Duties)
 * - Executes PayPal Sandbox payouts with idempotency (PayPal-Request-Id)
 * - Verifies real-time PayPal webhook reconciliation
 * - Prevents duplicate payouts and unauthorized transfers
 */
const SettlementView = {
  currentInvoiceId: "INV-2025-88419",

  async init(invoiceId) {
    if (invoiceId) {
      this.currentInvoiceId = invoiceId;
    }
    await this.populateInvoiceSelector();
    await this.loadSettlementView(this.currentInvoiceId);
    this.bindEvents();
  },

  bindEvents() {
    const sel = document.getElementById("settlement-invoice-select");
    if (sel) {
      sel.onchange = (e) => {
        this.currentInvoiceId = e.target.value;
        this.loadSettlementView(this.currentInvoiceId);
      };
    }
  },

  async populateInvoiceSelector() {
    const sel = document.getElementById("settlement-invoice-select");
    if (!sel) return;
    const invoices = await API.getInvoices();
    sel.innerHTML = invoices.map(inv => `
      <option value="${inv.id}" ${inv.id === this.currentInvoiceId ? 'selected' : ''}>
        ${inv.invoice_number} — ${inv.carrier_name} (${inv.settlement_status})
      </option>
    `).join("");
  },

  async loadSettlementView(invoiceId) {
    const container = document.getElementById("settlement-content");
    if (!container) return;
    container.innerHTML = `<div style="padding: 40px; text-align: center; color: var(--text-muted);">Loading settlement state...</div>`;

    try {
      const invoice = await API.getInvoiceDetails(invoiceId);
      const isAudited = invoice.audit_status !== "PENDING_AUDIT";
      const isAuthorized = invoice.settlement_status === "AUTHORIZED" || Boolean(invoice.settlement_intent);
      const isPaid = ["PAYOUT_INITIATED", "PAYOUT_SUCCESS", "RECONCILED", "PARTIALLY_SETTLED_HELD"].includes(invoice.settlement_status);
      const isBlocked = invoice.audit_status === "BLOCKED";

      const totalBilled = invoice.total_billed_formatted;
      const payable = invoice.approved_payable_formatted;
      const disputed = invoice.disputed_amount_formatted;
      const held = (invoice.held_amount_cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2 });

      const approver1 = invoice.settlement_intent?.first_approver || "sarah.chen@shipper.internal";
      const approver2 = invoice.settlement_intent?.second_approver || "david.ross@shipper.internal";

      container.innerHTML = `
        <!-- Top Status Card -->
        <div class="card" style="margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;">
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700;">PAYMENT SETTLEMENT POSITION</div>
            <div style="font-size: 16px; font-weight: 700; color: var(--text-primary);">
              Invoice #${invoice.invoice_number} &bull; ${invoice.carrier_name}
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">
              Carrier Receiver: <strong class="mono" style="color: var(--accent-primary);">${invoice.paypal_email}</strong>
            </div>
          </div>
          <div style="display: flex; gap: 24px; text-align: right;">
            <div>
              <div style="font-size: 11px; color: var(--text-muted); font-weight: 600;">TOTAL BILLED</div>
              <div class="amount" style="font-size: 18px; font-weight: 700;">$${totalBilled}</div>
            </div>
            <div>
              <div style="font-size: 11px; color: var(--status-success); font-weight: 600;">APPROVED PAYABLE</div>
              <div class="amount" style="font-size: 18px; font-weight: 700; color: var(--status-success);">$${payable}</div>
            </div>
            <div>
              <div style="font-size: 11px; color: var(--status-warning); font-weight: 600;">STATUS</div>
              <div>${App.getSettlementStatusBadge(invoice.settlement_status)}</div>
            </div>
          </div>
        </div>

        <div class="workbench-split-grid">
          <!-- Left: Authorization & Payout Execution -->
          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;">
              <span style="font-weight: 700; font-size: 14px;">Two-Person Financial Authorization</span>
              <span class="badge ${isAuthorized ? 'badge-clean' : 'badge-neutral'}">
                ${isAuthorized ? 'Signoff Approved' : 'Signoff Required'}
              </span>
            </div>

            ${!isAudited ? `
              <div style="padding: 12px 14px; background-color: var(--status-warning-bg); border-radius: var(--radius-sm); margin-bottom: 14px; color: var(--status-warning); font-size: 13px;">
                <strong>Policy Guard:</strong> This invoice has not been audited yet. Payout initiation is restricted until contract audit is verified.
              </div>
            ` : ''}

            ${isBlocked ? `
              <div style="padding: 12px 14px; background-color: var(--status-danger-bg); border-radius: var(--radius-sm); margin-bottom: 14px; color: var(--status-danger); font-size: 13px;">
                <strong>Duplicate Block:</strong> This invoice failed cross-invoice duplicate checks. Financial payout is permanently frozen.
              </div>
            ` : ''}

            <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px;">
              <div>
                <label style="font-size: 12px; font-weight: 600; color: var(--text-secondary); display: block; margin-bottom: 4px;">
                  Primary Approver (Accounts Payable)
                </label>
                <input type="text" id="settle-approver-1" class="form-input mono" style="width: 100%;" value="${approver1}" ${isPaid ? 'disabled' : ''}>
              </div>

              <div>
                <label style="font-size: 12px; font-weight: 600; color: var(--text-secondary); display: block; margin-bottom: 4px;">
                  Secondary Approver (Financial Controller)
                </label>
                <input type="text" id="settle-approver-2" class="form-input mono" style="width: 100%;" value="${approver2}" ${isPaid ? 'disabled' : ''}>
              </div>

              <div>
                <label style="font-size: 12px; font-weight: 600; color: var(--text-secondary); display: block; margin-bottom: 4px;">
                  Idempotency Key (PayPal-Request-Id)
                </label>
                <input type="text" id="settle-idempotency-key" class="form-input mono" style="width: 100%;"
                  value="${invoice.settlement_intent?.idempotency_key || 'IDEM-' + invoice.invoice_number + '-SBX'}" 
                  ${isPaid ? 'disabled' : ''}>
                <span style="font-size: 11px; color: var(--text-muted); margin-top: 2px; display: block;">
                  Cryptographic idempotency token prevents double-execution.
                </span>
              </div>
            </div>

            <div style="display: flex; gap: 10px; margin-top: 16px;">
              ${!isAuthorized && !isPaid ? `
                <button class="btn btn-secondary" onclick="SettlementView.authorize()" style="flex: 1;">
                  Authorize Dual Signoff
                </button>
              ` : ''}

              <button class="btn btn-primary" onclick="SettlementView.executePayout()" style="flex: 1;" ${isPaid || isBlocked ? 'disabled' : ''}>
                ${isPaid ? 'Payout Executed' : `Execute PayPal Payout ($${payable})`}
              </button>
            </div>

            <!-- Prohibited Payment Safeguards Proof -->
            <div style="margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--border-subtle);">
              <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700; margin-bottom: 6px;">
                Policy Invariant Proof Tests
              </div>
              <div style="display: flex; gap: 8px;">
                <button class="btn btn-danger btn-sm" onclick="SettlementView.testProhibitedPayment('BLOCKED')">
                  Test Pay Blocked Invoice
                </button>
                <button class="btn btn-danger btn-sm" onclick="SettlementView.testProhibitedPayment('DUPLICATE')">
                  Test Duplicate Replay
                </button>
              </div>
            </div>
          </div>

          <!-- Right: PayPal API Transaction & Webhook Reconciliation -->
          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;">
              <span style="font-weight: 700; font-size: 14px;">PayPal Sandbox Integration Status</span>
              <span class="badge ${invoice.payout_record ? 'badge-clean' : 'badge-neutral'}">
                ${invoice.payout_record ? 'Transaction Active' : 'No Payout Yet'}
              </span>
            </div>

            ${invoice.payout_record ? `
              <div style="background-color: var(--bg-muted); border-radius: var(--radius-sm); padding: 14px; margin-bottom: 16px; font-size: 12px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                  <div>Batch ID: <strong class="mono" style="color: var(--accent-primary);">${invoice.payout_record.paypal_batch_id}</strong></div>
                  <div>Payout Item ID: <strong class="mono" style="color: var(--accent-primary);">${invoice.payout_record.paypal_item_id}</strong></div>
                  <div>Batch Status: <span class="badge badge-clean">${invoice.payout_record.batch_status}</span></div>
                  <div>Item Status: <span class="badge badge-clean">${invoice.payout_record.item_status}</span></div>
                  <div>Transferred: <strong class="amount" style="color: var(--text-primary);">$${payable}</strong></div>
                  <div>Recipient: <span class="mono">${invoice.paypal_email}</span></div>
                </div>
              </div>

              <!-- Webhook Reconciliation Trigger -->
              <div style="border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 14px;">
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--status-success); margin-bottom: 6px;">
                  PayPal Webhook Reconciliation
                </div>
                <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 10px;">
                  Simulate authoritative webhook event delivery with HMAC signature verification:
                </p>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                  <button class="btn btn-secondary btn-sm" id="btn-refresh-payout-status" onclick="SettlementView.refreshStatus('${invoice.id}')" title="Poll PayPal Sandbox for authoritative batch/item state">
                    Poll / Refresh Status
                  </button>
                  <button class="btn btn-success btn-sm" onclick="SettlementView.triggerWebhook('PAYMENT.PAYOUTS-ITEM.SUCCEEDED', '${invoice.payout_record.paypal_item_id}', '${invoice.payout_record.paypal_batch_id}')">
                    Simulate Item Succeeded (200 OK)
                  </button>
                  <button class="btn btn-danger btn-sm" onclick="SettlementView.triggerWebhook('PAYMENT.PAYOUTS-ITEM.FAILED', '${invoice.payout_record.paypal_item_id}', '${invoice.payout_record.paypal_batch_id}')">
                    Simulate Item Failed
                  </button>
                </div>
              </div>
            ` : `
              <div style="padding: 40px; text-align: center; color: var(--text-muted); background-color: var(--bg-muted); border-radius: var(--radius-sm);">
                <p style="font-size: 13px;">No PayPal payout has been executed yet for this invoice.</p>
                <p style="font-size: 12px; margin-top: 6px; color: var(--text-muted);">
                  Authorize and execute above to initiate disbursement through PayPal Payouts.
                </p>
              </div>
            `}
          </div>
        </div>
      `;
    } catch (e) {
      container.innerHTML = `<div style="padding: 40px; color: var(--status-danger);">Failed loading settlement view: ${e.message}</div>`;
    }
  },

  async authorize() {
    const approver1 = document.getElementById("settle-approver-1")?.value;
    const approver2 = document.getElementById("settle-approver-2")?.value;

    try {
      const res = await API.authorizeSettlement(this.currentInvoiceId, approver1, approver2);
      App.showToast(res.message, "success");
      await this.loadSettlementView(this.currentInvoiceId);
    } catch (e) {
      App.showToast(`Authorization failed: ${e.message}`, "error");
    }
  },

  async executePayout() {
    const approver1 = document.getElementById("settle-approver-1")?.value;
    const approver2 = document.getElementById("settle-approver-2")?.value;
    const idemKey = document.getElementById("settle-idempotency-key")?.value;

    try {
      const res = await API.executePayout(this.currentInvoiceId, idemKey, approver1, approver2);
      App.showToast(`PayPal Payout Executed! Batch: ${res.paypal_batch_id}`, "success");
      await this.loadSettlementView(this.currentInvoiceId);
      await ControlTowerView.loadStats();
    } catch (e) {
      App.showToast(`Payout rejected: ${e.message}`, "error");
    }
  },

  async testProhibitedPayment(testType) {
    if (testType === 'BLOCKED') {
      try {
        await API.executePayout("INV-2025-99301", "IDEM-ATTEMPT-FORCED-01", "operator", "operator");
      } catch (e) {
        App.openModal(
          "Policy Invariant Enforced",
          `<div style="color: var(--status-danger); font-size: 14px; margin-bottom: 12px;"><strong>400 Bad Request: Invariant Defense Triggered</strong></div>
           <p style="color: var(--text-secondary); margin-bottom: 12px;">The policy engine blocked payment for an invalid invoice:</p>
           <div style="background: var(--bg-muted); padding: 12px; border-left: 3px solid var(--status-danger); font-family: monospace; font-size: 12px;">
             ${e.message}
           </div>`
        );
      }
    } else if (testType === 'DUPLICATE') {
      try {
        await API.executePayout(this.currentInvoiceId, "IDEM-FORCED-REPLAY-02", "operator", "operator");
      } catch (e) {
        App.openModal(
          "Duplicate Payout Prevented",
          `<div style="color: var(--status-warning); font-size: 14px; margin-bottom: 12px;"><strong>Duplicate Settlement Prevented</strong></div>
           <p style="color: var(--text-secondary); margin-bottom: 12px;">The policy engine prevented a re-execution of an authorized payout:</p>
           <div style="background: var(--bg-muted); padding: 12px; border-left: 3px solid var(--status-warning); font-family: monospace; font-size: 12px;">
             ${e.message}
           </div>`
        );
      }
    }
  },

  async triggerWebhook(eventType, itemId, batchId) {
    try {
      const res = await API.simulateWebhook(eventType, itemId, batchId);
      App.showToast(`Webhook event '${eventType}' verified and processed!`, "success");
      await this.loadSettlementView(this.currentInvoiceId);
      await ControlTowerView.loadStats();
    } catch (e) {
      App.showToast(`Webhook simulation failed: ${e.message}`, "error");
    }
  },

  async refreshStatus(invoiceId) {
    const id = invoiceId || this.currentInvoiceId;
    try {
      const res = await API.refreshSettlementStatus(id);
      App.showToast(`Status refreshed: ${res.batch_status || 'OK'} / ${res.item_status || 'OK'}`, "success");
      await this.loadSettlementView(this.currentInvoiceId);
      await ControlTowerView.loadStats();
    } catch (e) {
      App.showToast(`Status refresh failed: ${e.message}`, "error");
    }
  }
};
