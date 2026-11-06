/**
 * Home View Controller (Formerly Control Tower)
 * Renders:
 * - "Needs your attention" operational triage queue
 * - 4 core KPI metrics reconciling to the exact cent
 * - Financial reconciliation proportion visualizer
 * - Recent priority freight invoices with one-click actions
 */
const ControlTowerView = {
  async init() {
    await this.loadStats();
    await this.loadRecentInvoices();
  },

  async loadStats() {
    try {
      const stats = await API.getStats();

      // 4 Main KPI Cards
      const billedEl = document.getElementById("kpi-billed");
      const approvedEl = document.getElementById("kpi-approved");
      const disputedEl = document.getElementById("kpi-disputed");
      const savedEl = document.getElementById("kpi-saved");
      const countEl = document.getElementById("kpi-total-invoices");
      const rateEl = document.getElementById("kpi-exception-rate");

      if (billedEl) billedEl.textContent = `$${stats.total_billed_formatted}`;
      if (approvedEl) approvedEl.textContent = `$${stats.approved_payable_formatted}`;
      if (disputedEl) disputedEl.textContent = `$${stats.disputed_amount_formatted}`;
      if (savedEl) savedEl.textContent = `$${stats.held_amount_formatted}`;
      if (countEl) countEl.textContent = `${stats.total_invoices} Invoices`;
      if (rateEl) rateEl.textContent = `${stats.exception_rate_pct}% Variance`;

      // Financial Reconciliation Proportion Bar
      const total = stats.total_billed_cents || 1;
      const pctApproved = ((stats.approved_payable_cents / total) * 100).toFixed(1);
      const pctDisputed = ((stats.disputed_amount_cents / total) * 100).toFixed(1);
      const pctHeld = ((stats.held_amount_cents / total) * 100).toFixed(1);

      const barContainer = document.getElementById("proportion-bar");
      if (barContainer) {
        barContainer.innerHTML = `
          <div class="proportion-segment approved" style="width: ${pctApproved}%;" title="Approved Payable: $${stats.approved_payable_formatted} (${pctApproved}%)"></div>
          <div class="proportion-segment disputed" style="width: ${pctDisputed}%;" title="Disputed Overcharges: $${stats.disputed_amount_formatted} (${pctDisputed}%)"></div>
          <div class="proportion-segment held" style="width: ${pctHeld}%;" title="Held in Reserve: $${stats.held_amount_formatted} (${pctHeld}%)"></div>
        `;
      }

      const legApp = document.getElementById("legend-approved");
      const legDisp = document.getElementById("legend-disputed");
      const legHeld = document.getElementById("legend-held");
      if (legApp) legApp.textContent = `$${stats.approved_payable_formatted} (${pctApproved}%)`;
      if (legDisp) legDisp.textContent = `$${stats.disputed_amount_formatted} (${pctDisputed}%)`;
      if (legHeld) legHeld.textContent = `$${stats.held_amount_formatted} (${pctHeld}%)`;

      // Render Attention Queue
      this.renderAttentionQueue(stats);
    } catch (e) {
      console.error("Failed loading statistics:", e);
      App.showToast("Could not load dashboard metrics.", "error");
    }
  },

  renderAttentionQueue(stats) {
    const listReview = document.getElementById("list-invoices-review");
    const listDisputes = document.getElementById("list-disputes-reply");
    const listPayments = document.getElementById("list-payments-approval");
    const totalBadge = document.getElementById("attention-total-badge");

    const countReview = document.getElementById("count-invoices-review");
    const countDisputes = document.getElementById("count-disputes-reply");
    const countPayments = document.getElementById("count-payments-approval");

    const invItems = stats.invoices_to_review || [];
    const dispItems = stats.disputes_awaiting_reply || [];
    const payItems = stats.payments_awaiting_approval || [];

    const totalTasks = invItems.length + dispItems.length + payItems.length;
    if (totalBadge) totalBadge.textContent = `${totalTasks} Tasks`;

    if (countReview) countReview.textContent = invItems.length;
    if (countDisputes) countDisputes.textContent = dispItems.length;
    if (countPayments) countPayments.textContent = payItems.length;

    if (listReview) {
      if (invItems.length === 0) {
        listReview.innerHTML = `<div style="padding: 12px; font-size: 12px; color: var(--text-muted); text-align: center;">All invoices audited</div>`;
      } else {
        listReview.innerHTML = invItems.map(inv => `
          <div class="attention-item">
            <div class="attention-item-info">
              <span class="attention-item-name">${inv.invoice_number}</span>
              <span class="attention-item-sub">${inv.carrier_name} &bull; $${inv.total_billed_formatted}</span>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="App.navigateTo('workbench', '${inv.id}')">Audit</button>
          </div>
        `).join("");
      }
    }

    if (listDisputes) {
      if (dispItems.length === 0) {
        listDisputes.innerHTML = `<div style="padding: 12px; font-size: 12px; color: var(--text-muted); text-align: center;">No disputes pending</div>`;
      } else {
        listDisputes.innerHTML = dispItems.map(d => `
          <div class="attention-item">
            <div class="attention-item-info">
              <span class="attention-item-name">${d.invoice_number}</span>
              <span class="attention-item-sub">${d.carrier_name} &bull; $${d.disputed_formatted}</span>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="App.navigateTo('disputes', '${d.invoice_id}')">Reply</button>
          </div>
        `).join("");
      }
    }

    if (listPayments) {
      if (payItems.length === 0) {
        listPayments.innerHTML = `<div style="padding: 12px; font-size: 12px; color: var(--text-muted); text-align: center;">No payments queued</div>`;
      } else {
        listPayments.innerHTML = payItems.map(p => `
          <div class="attention-item">
            <div class="attention-item-info">
              <span class="attention-item-name">${p.invoice_number}</span>
              <span class="attention-item-sub">${p.carrier_name} &bull; $${p.approved_payable_formatted}</span>
            </div>
            <button class="btn btn-primary btn-sm" onclick="App.navigateTo('payments', '${p.id}')">Approve</button>
          </div>
        `).join("");
      }
    }
  },

  async loadRecentInvoices() {
    try {
      const invoices = await API.getInvoices();
      const tbody = document.getElementById("home-invoices-tbody");
      if (!tbody) return;
      tbody.innerHTML = "";

      invoices.forEach(inv => {
        const tr = document.createElement("tr");
        const auditBadge = App.getAuditStatusBadge(inv.audit_status);
        const settleBadge = App.getSettlementStatusBadge(inv.settlement_status);

        tr.innerHTML = `
          <td><strong class="mono">${inv.invoice_number}</strong></td>
          <td>${inv.carrier_name} <span class="mono" style="color: var(--text-muted); font-size: 11px;">(${inv.carrier_scac || 'CARRIER'})</span></td>
          <td style="color: var(--text-secondary); font-size: 12px;">${inv.invoice_date}</td>
          <td class="amount-cell amount">$${inv.total_billed_formatted}</td>
          <td class="amount-cell amount" style="color: var(--status-success); font-weight: 600;">$${inv.approved_payable_formatted}</td>
          <td class="amount-cell amount" style="color: ${inv.disputed_amount_cents > 0 ? 'var(--status-warning)' : 'var(--text-muted)'}; font-weight: 600;">
            ${inv.disputed_amount_cents > 0 ? '+$' + inv.disputed_amount_formatted : '$0.00'}
          </td>
          <td>${auditBadge}</td>
          <td>${settleBadge}</td>
          <td style="text-align: right;">
            <button class="btn btn-secondary btn-sm" onclick="App.navigateTo('workbench', '${inv.id}')">Review</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error("Failed loading recent invoices:", e);
    }
  }
};
