/**
 * Invoices Intelligence View Controller
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
      searchInput.addEventListener("input", () => this.filterAndRender());
    }
    if (statusFilter) {
      statusFilter.addEventListener("change", () => this.filterAndRender());
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
    const tbody = document.getElementById("full-invoices-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (invoices.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 30px; color: var(--text-muted);">No invoices match selected criteria.</td></tr>`;
      return;
    }

    invoices.forEach(inv => {
      const tr = document.createElement("tr");
      if (inv.id === "INV-2025-88419") {
        tr.className = "highlighted";
      }

      const auditBadge = App.getAuditStatusBadge(inv.audit_status);
      const settleBadge = App.getSettlementStatusBadge(inv.settlement_status);

      tr.innerHTML = `
        <td class="mono" style="font-weight: 700; color: var(--text-primary);">${inv.invoice_number}</td>
        <td>
          <div style="font-weight: 600;">${inv.carrier_name}</div>
          <div style="font-size: 11px; color: var(--text-muted);">${inv.carrier_scac || 'CARRIER'} &bull; Net 30</div>
        </td>
        <td style="font-size: 12px;">${inv.origin && inv.destination ? `${inv.origin} &rarr; ${inv.destination}` : 'Unassigned Lane'}</td>
        <td class="mono" style="font-size: 12px;">${inv.bol_number || 'N/A'}</td>
        <td class="amount-cell mono" style="font-weight: 600;">$${inv.total_billed_formatted}</td>
        <td class="amount-cell mono" style="color: var(--accent-cyan); font-weight: 600;">$${inv.approved_payable_formatted}</td>
        <td class="amount-cell mono" style="color: ${inv.disputed_amount_cents > 0 ? 'var(--status-warning)' : 'var(--text-muted)'}; font-weight: 600;">
          ${inv.disputed_amount_cents > 0 ? '+$' + inv.disputed_amount_formatted : '$0.00'}
        </td>
        <td>${auditBadge}</td>
        <td>${settleBadge}</td>
        <td>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-secondary btn-sm" onclick="App.navigateTo('workbench', '${inv.id}')">Workbench</button>
            <button class="btn btn-primary btn-sm" onclick="App.quickAudit('${inv.id}')">Run Audit</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }
};
