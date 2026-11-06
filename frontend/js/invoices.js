/**
 * Invoices View Controller
 * Filters, searches, and provides line-item breakdown with one-click audit actions.
 */
const InvoicesView = {
  invoicesData: [],

  async init() {
    this.bindEvents();
    await this.loadInvoices();
  },

  bindEvents() {
    const searchInput = document.getElementById("invoice-search-input");
    const statusFilter = document.getElementById("invoice-status-filter");

    if (searchInput) {
      searchInput.oninput = () => this.filterAndRender();
    }
    if (statusFilter) {
      statusFilter.onchange = () => this.filterAndRender();
    }
  },

  async loadInvoices() {
    try {
      this.invoicesData = await API.getInvoices();
      this.renderTable(this.invoicesData);
    } catch (e) {
      App.showToast("Failed loading invoices.", "error");
    }
  },

  filterAndRender() {
    const q = document.getElementById("invoice-search-input")?.value.toLowerCase().trim() || "";
    const status = document.getElementById("invoice-status-filter")?.value || "";

    const filtered = this.invoicesData.filter(inv => {
      const matchStatus = !status || inv.audit_status === status;
      const matchText = !q || 
        inv.invoice_number.toLowerCase().includes(q) || 
        inv.carrier_name.toLowerCase().includes(q) || 
        (inv.bol_number && inv.bol_number.toLowerCase().includes(q));
      return matchStatus && matchText;
    });

    this.renderTable(filtered);
  },

  renderTable(invoices) {
    const tbody = document.getElementById("invoices-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (invoices.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 32px; color: var(--text-muted);">No invoices match selected criteria.</td></tr>`;
      return;
    }

    invoices.forEach(inv => {
      const tr = document.createElement("tr");
      const auditBadge = App.getAuditStatusBadge(inv.audit_status);
      const settleBadge = App.getSettlementStatusBadge(inv.settlement_status);

      let actionBtn = "";
      if (inv.audit_status === "PENDING_AUDIT") {
        actionBtn = `<button class="btn btn-primary btn-sm" onclick="App.navigateTo('workbench', '${inv.id}')">Audit</button>`;
      } else if (inv.settlement_status === "UNSETTLED" && inv.audit_status !== "BLOCKED") {
        actionBtn = `<button class="btn btn-secondary btn-sm" onclick="App.navigateTo('payments', '${inv.id}')">Authorize</button>`;
      } else {
        actionBtn = `<button class="btn btn-secondary btn-sm" onclick="App.navigateTo('workbench', '${inv.id}')">Inspect</button>`;
      }

      tr.innerHTML = `
        <td><strong class="mono">${inv.invoice_number}</strong></td>
        <td>${inv.carrier_name} <span class="mono" style="color: var(--text-muted); font-size: 11px;">(${inv.carrier_scac || 'CARRIER'})</span></td>
        <td style="font-size: 12px; color: var(--text-secondary);">${inv.origin || 'ORD'} &rarr; ${inv.destination || 'DFW'}</td>
        <td style="font-size: 12px; color: var(--text-muted);">${inv.invoice_date}</td>
        <td class="amount-cell amount">$${inv.total_billed_formatted}</td>
        <td class="amount-cell amount" style="color: var(--status-success); font-weight: 600;">$${inv.approved_payable_formatted}</td>
        <td class="amount-cell amount" style="color: ${inv.disputed_amount_cents > 0 ? 'var(--status-warning)' : 'var(--text-muted)'}; font-weight: 600;">
          ${inv.disputed_amount_cents > 0 ? '+$' + inv.disputed_amount_formatted : '$0.00'}
        </td>
        <td>${auditBadge}</td>
        <td>${settleBadge}</td>
        <td style="text-align: right;">${actionBtn}</td>
      `;
      tbody.appendChild(tr);
    });
  }
};
