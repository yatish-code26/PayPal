/**
 * Control Tower View Controller
 * Renders executive KPI metrics, interactive SVG visualizers, and priority invoice streams.
 */
const ControlTowerView = {
  async init() {
    await this.loadStats();
    await this.loadRecentInvoices();
  },

  async loadStats() {
    try {
      const stats = await API.getStats();
      
      document.getElementById("metric-total-billed").textContent = `$${stats.total_billed_formatted}`;
      document.getElementById("metric-verified-payable").textContent = `$${stats.verified_payable_formatted}`;
      document.getElementById("metric-detected-disputed").textContent = `$${stats.detected_disputed_formatted}`;
      document.getElementById("metric-confirmed-recovered").textContent = `$${stats.confirmed_recovered_formatted}`;
      document.getElementById("metric-successful-payouts").textContent = `$${stats.successful_payouts_formatted}`;
      document.getElementById("metric-total-invoices").textContent = `${stats.total_invoices} Invoices`;
      document.getElementById("audit-coverage-badge").textContent = `Audit Coverage: ${stats.audit_coverage_pct}%`;
      document.getElementById("metric-exception-rate").textContent = `${stats.exception_rate_pct}% Exception Rate`;

      this.renderDiscrepancyBreakdownChart();
      this.renderAuditVelocityChart();
    } catch (e) {
      App.showToast("Failed loading Control Tower statistics.", "error");
    }
  },

  async loadRecentInvoices() {
    try {
      const invoices = await API.getInvoices();
      const tbody = document.getElementById("dashboard-invoices-tbody");
      tbody.innerHTML = "";

      invoices.forEach(inv => {
        const tr = document.createElement("tr");
        if (inv.id === "INV-2025-88419") {
          tr.className = "highlighted";
        }

        const auditBadge = App.getAuditStatusBadge(inv.audit_status);
        const settleBadge = App.getSettlementStatusBadge(inv.settlement_status);

        tr.innerHTML = `
          <td class="mono" style="font-weight: 700; color: var(--text-primary);">${inv.invoice_number}</td>
          <td><strong>${inv.carrier_name}</strong> <span style="color: var(--text-muted); font-size: 11px;">(${inv.carrier_scac || 'CARRIER'})</span></td>
          <td class="mono" style="font-size: 12px;">${inv.bol_number || 'N/A'}</td>
          <td style="color: var(--text-muted); font-size: 12px;">${inv.invoice_date}</td>
          <td class="amount-cell mono" style="font-weight: 600;">$${inv.total_billed_formatted}</td>
          <td class="amount-cell mono" style="color: var(--accent-cyan); font-weight: 600;">$${inv.approved_payable_formatted}</td>
          <td class="amount-cell mono" style="color: ${inv.disputed_amount_cents > 0 ? 'var(--status-warning)' : 'var(--text-muted)'}; font-weight: 600;">
            ${inv.disputed_amount_cents > 0 ? '+$' + inv.disputed_amount_formatted : '$0.00'}
          </td>
          <td>${auditBadge}</td>
          <td>${settleBadge}</td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-secondary btn-sm" onclick="App.navigateTo('workbench', '${inv.id}')" title="Inspect Evidence">Evidence</button>
              <button class="btn btn-primary btn-sm" onclick="App.quickAudit('${inv.id}')" title="Execute Audit">Audit</button>
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error("Failed loading recent invoices:", e);
    }
  },

  renderDiscrepancyBreakdownChart() {
    const container = document.getElementById("chart-discrepancy-breakdown");
    // Crisp SVG Horizontal Distribution Chart
    container.innerHTML = `
      <svg width="100%" height="180" viewBox="0 0 500 180" preserveAspectRatio="none">
        <!-- Background Grid -->
        <line x1="120" y1="20" x2="480" y2="20" stroke="rgba(255,255,255,0.05)" />
        <line x1="120" y1="55" x2="480" y2="55" stroke="rgba(255,255,255,0.05)" />
        <line x1="120" y1="90" x2="480" y2="90" stroke="rgba(255,255,255,0.05)" />
        <line x1="120" y1="125" x2="480" y2="125" stroke="rgba(255,255,255,0.05)" />
        <line x1="120" y1="160" x2="480" y2="160" stroke="rgba(255,255,255,0.05)" />

        <!-- Row 1: Legitimate Payable -->
        <text x="10" y="24" fill="#94a3b8" font-size="11" font-weight="600">PAYABLE (60.5%)</text>
        <rect x="120" y="14" width="220" height="14" rx="3" fill="#00e5ff" />
        <text x="350" y="25" fill="#f8fafc" font-size="11" font-family="monospace">$3,342.00</text>

        <!-- Row 2: Secondary Congestion -->
        <text x="10" y="59" fill="#94a3b8" font-size="11" font-weight="600">DUPLICATE CONG.</text>
        <rect x="120" y="49" width="130" height="14" rx="3" fill="#ef4444" />
        <text x="260" y="60" fill="#f8fafc" font-size="11" font-family="monospace">+$850.00</text>

        <!-- Row 3: Rate Mismatch -->
        <text x="10" y="94" fill="#94a3b8" font-size="11" font-weight="600">RATE MISMATCH</text>
        <rect x="120" y="84" width="95" height="14" rx="3" fill="#f59e0b" />
        <text x="225" y="95" fill="#f8fafc" font-size="11" font-family="monospace">+$600.00</text>

        <!-- Row 4: Fuel Surcharge -->
        <text x="10" y="129" fill="#94a3b8" font-size="11" font-weight="600">FSC OVERCHARGE</text>
        <rect x="120" y="119" width="60" height="14" rx="3" fill="#f59e0b" />
        <text x="190" y="130" fill="#f8fafc" font-size="11" font-family="monospace">+$380.00</text>

        <!-- Row 5: Unauthorized Liftgate -->
        <text x="10" y="164" fill="#94a3b8" font-size="11" font-weight="600">UNAUTH LIFTGATE</text>
        <rect x="120" y="154" width="55" height="14" rx="3" fill="#a855f7" />
        <text x="185" y="165" fill="#f8fafc" font-size="11" font-family="monospace">+$350.00</text>
      </svg>
    `;
  },

  renderAuditVelocityChart() {
    const container = document.getElementById("chart-audit-velocity");
    // State transition pipeline visualizer
    container.innerHTML = `
      <svg width="100%" height="180" viewBox="0 0 520 180">
        <!-- Node 1: Ingestion -->
        <circle cx="50" cy="90" r="24" fill="#161f33" stroke="#38bdf8" stroke-width="2" />
        <text x="50" y="94" fill="#38bdf8" font-size="10" font-weight="700" text-anchor="middle">INGEST</text>
        <text x="50" y="130" fill="#94a3b8" font-size="10" text-anchor="middle">100% Extracted</text>

        <line x1="74" y1="90" x2="136" y2="90" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4" />

        <!-- Node 2: Deterministic Audit -->
        <circle cx="160" cy="90" r="24" fill="#161f33" stroke="#f59e0b" stroke-width="2" />
        <text x="160" y="94" fill="#f59e0b" font-size="10" font-weight="700" text-anchor="middle">AUDIT</text>
        <text x="160" y="130" fill="#94a3b8" font-size="10" text-anchor="middle">4 Findings</text>

        <line x1="184" y1="90" x2="246" y2="90" stroke="#f59e0b" stroke-width="2" />

        <!-- Node 3: Dispute Package -->
        <circle cx="270" cy="90" r="24" fill="#161f33" stroke="#ef4444" stroke-width="2" />
        <text x="270" y="94" fill="#ef4444" font-size="10" font-weight="700" text-anchor="middle">DISPUTE</text>
        <text x="270" y="130" fill="#94a3b8" font-size="10" text-anchor="middle">$2,180 Held</text>

        <line x1="294" y1="90" x2="356" y2="90" stroke="#00e5ff" stroke-width="2" />

        <!-- Node 4: Dual Authorization -->
        <circle cx="380" cy="90" r="24" fill="#161f33" stroke="#00e5ff" stroke-width="2" />
        <text x="380" y="94" fill="#00e5ff" font-size="10" font-weight="700" text-anchor="middle">AUTH</text>
        <text x="380" y="130" fill="#94a3b8" font-size="10" text-anchor="middle">Dual Signoff</text>

        <line x1="404" y1="90" x2="466" y2="90" stroke="#10b981" stroke-width="2" />

        <!-- Node 5: PayPal Sandbox Settlement -->
        <circle cx="490" cy="90" r="24" fill="#161f33" stroke="#10b981" stroke-width="2" />
        <text x="490" y="94" fill="#10b981" font-size="10" font-weight="700" text-anchor="middle">PAYPAL</text>
        <text x="490" y="130" fill="#94a3b8" font-size="10" text-anchor="middle">$3,342 Settled</text>
      </svg>
    `;
  }
};
