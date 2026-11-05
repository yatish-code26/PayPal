/**
 * Settlement Center View Controller
 * Enforces two-man authorization, idempotency, PayPal sandbox payout execution,
 * prohibited payout prevention tests, and webhook reconciliation.
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
      const isPaid = ["PAYOUT_INITIATED", "PAYOUT_SUCCESS", "RECONCILED"].includes(invoice.settlement_status);
      const isBlocked = invoice.audit_status === "BLOCKED";

      const totalBilled = invoice.total_billed_formatted;
      const payable = invoice.approved_payable_formatted;
      const disputed = invoice.disputed_amount_formatted;
      const held = (invoice.held_amount_cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2 });

      container.innerHTML = `
        <!-- Reconciliation Invariant Bar -->
        <div class="settlement-reconciliation-bar" style="margin-bottom: 24px; border-left: 4px solid var(--accent-cyan);">
          <div>
            <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700;">PAYMENT SETTLEMENT POSITION</div>
            <div style="font-size: 16px; font-weight: 700; color: var(--text-primary);">
              Invoice #${invoice.invoice_number} &bull; ${invoice.carrier_name}
            </div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 2px;">
              Carrier PayPal Receiver: <strong class="mono" style="color: var(--accent-cyan);">${invoice.paypal_email}</strong>
            </div>
          </div>
          <div style="display: flex; gap: 24px; text-align: right;">
            <div>
              <div style="font-size: 11px; color: var(--text-muted); font-weight: 600;">TOTAL BILLED</div>
              <div class="mono" style="font-size: 17px; font-weight: 700;">$${totalBilled}</div>
            </div>
            <div>
              <div style="font-size: 11px; color: var(--accent-cyan); font-weight: 600;">APPROVED PAYABLE</div>
              <div class="mono" style="font-size: 17px; font-weight: 700; color: var(--accent-cyan);">$${payable}</div>
            </div>
            <div>
              <div style="font-size: 11px; color: var(--status-warning); font-weight: 600;">DISPUTED / HELD</div>
              <div class="mono" style="font-size: 17px; font-weight: 700; color: var(--status-warning);">$${disputed}</div>
            </div>
            <div>
              <div style="font-size: 11px; color: var(--text-muted); font-weight: 600;">STATUS</div>
              <div>${App.getSettlementStatusBadge(invoice.settlement_status)}</div>
            </div>
          </div>
        </div>

        <!-- 5-Step Deterministic Financial Settlement Stepper -->
        <div class="settlement-stepper">
          <div class="step-item ${isAudited ? 'completed' : 'active'}">
            <div class="step-circle">${isAudited ? '✓' : '1'}</div>
            <div class="step-label">1. Audit Validated</div>
          </div>
          <div class="step-item ${isAuthorized || isPaid ? 'completed' : (isAudited ? 'active' : '')}">
            <div class="step-circle">${isAuthorized || isPaid ? '✓' : '2'}</div>
            <div class="step-label">2. Signoff 1 (Sarah)</div>
          </div>
          <div class="step-item ${isAuthorized || isPaid ? 'completed' : ''}">
            <div class="step-circle">${isAuthorized || isPaid ? '✓' : '3'}</div>
            <div class="step-label">3. Signoff 2 (David)</div>
          </div>
          <div class="step-item ${isPaid ? 'completed' : (isAuthorized ? 'active' : '')}">
            <div class="step-circle">${isPaid ? '✓' : '4'}</div>
            <div class="step-label">4. PayPal Sandbox Payout</div>
          </div>
          <div class="step-item ${invoice.settlement_status === 'RECONCILED' ? 'completed' : (isPaid ? 'active' : '')}">
            <div class="step-circle">${invoice.settlement_status === 'RECONCILED' ? '✓' : '5'}</div>
            <div class="step-label">5. Webhook Reconciled</div>
          </div>
        </div>

        <div class="workbench-grid">
          <!-- Left: Authorization & Payout Trigger -->
          <div class="panel-card">
            <div class="panel-header">
              <span class="panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                Two-Man Financial Authorization & Payout
              </span>
              <span class="badge ${isAuthorized ? 'badge-clean' : 'badge-pending'}">
                ${isAuthorized ? 'Authorization Valid' : 'Requires Signoff'}
              </span>
            </div>

            <!-- Warning if not audited -->
            ${!isAudited ? `
              <div style="padding: 14px; background-color: var(--status-warning-bg); border: 1px solid rgba(245,158,11,0.3); border-radius: var(--radius-sm); margin-bottom: 16px; color: var(--status-warning); font-size: 13px;">
                <strong>Audit Invariant:</strong> This invoice has not been audited yet. Payout initiation is strictly prohibited by policy engine.
              </div>
            ` : ''}

            <!-- Warning if blocked -->
            ${isBlocked ? `
              <div style="padding: 14px; background-color: var(--status-danger-bg); border: 1px solid rgba(239,68,68,0.3); border-radius: var(--radius-sm); margin-bottom: 16px; color: var(--status-danger); font-size: 13px;">
                <strong>Fatal Policy Block:</strong> This invoice failed critical duplicate shipment validation. All settlement actions are permanently frozen.
              </div>
            ` : ''}

            <!-- Authorization Form -->
            <div class="form-group">
              <label class="form-label">Primary Accounts Payable Approver</label>
              <input type="text" id="settle-approver-1" class="form-input mono" value="sarah.chen@shipper.internal" ${isPaid ? 'disabled' : ''}>
            </div>

            <div class="form-group">
              <label class="form-label">Secondary Financial Officer (Dual Signoff)</label>
              <input type="text" id="settle-approver-2" class="form-input mono" value="david.ross@shipper.internal" ${isPaid ? 'disabled' : ''}>
            </div>

            <div class="form-group">
              <label class="form-label">Durable Idempotency Key</label>
              <input type="text" id="settle-idempotency-key" class="form-input mono" 
                value="${invoice.settlement_intent?.idempotency_key || 'IDEM-' + invoice.invoice_number + '-SBX01'}" 
                ${isPaid ? 'disabled' : ''}>
              <small style="color: var(--text-muted); font-size: 11px;">PayPal-Request-Id header token ensures exactly-once execution.</small>
            </div>

            <div style="display: flex; gap: 10px; margin-top: 20px;">
              ${!isAuthorized && !isPaid ? `
                <button class="btn btn-secondary" onclick="SettlementView.authorize()" style="flex: 1;">
                  Authorize Settlement Intent
                </button>
              ` : ''}

              <button class="btn btn-primary" onclick="SettlementView.executePayout()" style="flex: 1;" ${isPaid || isBlocked ? 'disabled' : ''}>
                ${isPaid ? 'Payout Already Executed' : `Execute PayPal Sandbox Payout ($${payable})`}
              </button>
            </div>

            <!-- Prohibited Payout Demonstration Button -->
            <div style="margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--border-subtle);">
              <div style="font-size: 11px; text-transform: uppercase; color: var(--status-danger); font-weight: 700; margin-bottom: 6px;">
                SECURITY & POLICY INVARIANT PROOF TEST
              </div>
              <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 10px;">
                Demonstrate system defenses against unauthorized payments, duplicate settlement attempts, or client tampering:
              </p>
              <div style="display: flex; gap: 8px;">
                <button class="btn btn-danger btn-sm" onclick="SettlementView.testProhibitedPayment('BLOCKED')">
                  Test Pay Blocked Duplicate
                </button>
                <button class="btn btn-danger btn-sm" onclick="SettlementView.testProhibitedPayment('DUPLICATE')">
                  Test Duplicate Payout Replay
                </button>
              </div>
            </div>
          </div>

          <!-- Right: PayPal Sandbox API Response & Webhook Simulator -->
          <div class="panel-card">
            <div class="panel-header">
              <span class="panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
                PayPal Sandbox Gateway Inspector
              </span>
              <span class="badge ${invoice.payout_record ? 'badge-clean' : 'badge-pending'}">
                ${invoice.payout_record ? (invoice.payout_record.is_simulated ? 'Sandbox Simulator' : 'Live Gateway') : 'No Active Payout'}
              </span>
            </div>

            ${invoice.payout_record ? `
              <div style="background-color: var(--bg-primary); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 14px; margin-bottom: 16px; font-size: 12px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                  <div>PayPal Batch ID: <strong class="mono" style="color: var(--accent-cyan);">${invoice.payout_record.paypal_batch_id}</strong></div>
                  <div>PayPal Item ID: <strong class="mono" style="color: var(--accent-cyan);">${invoice.payout_record.paypal_item_id}</strong></div>
                  <div>Batch Status: <span class="badge badge-clean">${invoice.payout_record.batch_status}</span></div>
                  <div>Item Status: <span class="badge badge-clean">${invoice.payout_record.item_status}</span></div>
                  <div>Amount Transferred: <strong class="mono" style="color: var(--text-primary);">$${payable} ${invoice.currency}</strong></div>
                  <div>PayPal Fee: <strong class="mono">$0.25</strong></div>
                </div>
              </div>

              <!-- Raw JSON Inspector -->
              <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px;">
                AUTHORITATIVE PAYPAL API RESPONSE PAYLOAD
              </div>
              <pre class="raw-json-inspector">${JSON.stringify(JSON.parse(invoice.payout_record.raw_paypal_response_json || '{}'), null, 2)}</pre>

              <!-- Webhook Reconciliation Simulator -->
              <div style="margin-top: 16px; padding: 14px; background-color: var(--bg-primary); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm);">
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--status-success); margin-bottom: 6px;">
                  WEBHOOK-DRIVEN RECONCILIATION SIMULATOR
                </div>
                <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 10px;">
                  Simulate asynchronous delivery of PayPal webhook events for item settlement:
                </p>
                <div style="display: flex; gap: 8px;">
                  <button class="btn btn-success btn-sm" onclick="SettlementView.triggerWebhook('PAYMENT.PAYOUTS-ITEM.SUCCEEDED', '${invoice.payout_record.paypal_item_id}')">
                    Simulate Item Succeeded (200 OK)
                  </button>
                  <button class="btn btn-danger btn-sm" onclick="SettlementView.triggerWebhook('PAYMENT.PAYOUTS-ITEM.FAILED', '${invoice.payout_record.paypal_item_id}')">
                    Simulate Item Failed
                  </button>
                </div>
              </div>
            ` : `
              <div style="padding: 40px; text-align: center; color: var(--text-muted); background-color: var(--bg-primary); border-radius: var(--radius-sm);">
                <p>No PayPal payout has been executed yet for this invoice.</p>
                <p style="font-size: 12px; margin-top: 6px;">Authorize settlement intent on the left to initiate the payout sequence.</p>
              </div>
            `}
          </div>
        </div>
      `;
    } catch (e) {
      container.innerHTML = `<div style="padding: 40px; color: var(--status-danger);">Failed loading settlement center: ${e.message}</div>`;
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
      App.showToast(`PayPal Payout Executed! Batch: ${res.paypal_batch_id} (${res.mode_label})`, "success");
      await this.loadSettlementView(this.currentInvoiceId);
      ControlTowerView.loadStats();
    } catch (e) {
      App.showToast(`Payout rejected: ${e.message}`, "error");
    }
  },

  async testProhibitedPayment(testType) {
    if (testType === 'BLOCKED') {
      // Attempt to force payout on blocked duplicate invoice (INV-2025-99301)
      try {
        await API.executePayout("INV-2025-99301", "IDEM-ATTEMPT-FORCED-01", "operator", "operator");
      } catch (e) {
        App.openModal(
          "Deterministic Policy Invariant Enforced",
          `<div style="color: var(--status-danger); font-size: 14px; margin-bottom: 12px;"><strong>403 FORBIDDEN: Fatal Settlement Invariant Triggered</strong></div>
           <p style="color: var(--text-secondary); margin-bottom: 12px;">The system successfully rejected the unauthorized settlement attempt:</p>
           <div style="background: var(--bg-primary); padding: 12px; border-left: 3px solid var(--status-danger); font-family: monospace; font-size: 12px;">
             ${e.message}
           </div>
           <p style="margin-top: 12px; font-size: 12px; color: var(--text-muted);">
             Invariants enforced: Never pay an un-audited, held, or blocked duplicate freight invoice.
           </p>`
        );
      }
    } else if (testType === 'DUPLICATE') {
      // Attempt duplicate payout for current invoice
      try {
        await API.executePayout(this.currentInvoiceId, "IDEM-FORCED-NEW-KEY-02", "operator", "operator");
      } catch (e) {
        App.openModal(
          "Duplicate Payout Prevention Enforced",
          `<div style="color: var(--status-warning); font-size: 14px; margin-bottom: 12px;"><strong>409 CONFLICT: Duplicate Settlement Prevented</strong></div>
           <p style="color: var(--text-secondary); margin-bottom: 12px;">The backend policy engine prevented a duplicate transfer:</p>
           <div style="background: var(--bg-primary); padding: 12px; border-left: 3px solid var(--status-warning); font-family: monospace; font-size: 12px;">
             ${e.message}
           </div>`
        );
      }
    }
  },

  async triggerWebhook(eventType, itemId) {
    try {
      const res = await API.simulateWebhook(eventType, itemId);
      App.showToast(`Webhook event '${eventType}' processed! Invoice status reconciled.`, "success");
      await this.loadSettlementView(this.currentInvoiceId);
      ControlTowerView.loadStats();
    } catch (e) {
      App.showToast(`Webhook simulation failed: ${e.message}`, "error");
    }
  }
};
