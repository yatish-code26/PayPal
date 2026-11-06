/**
 * Carrier Scorecards & Renewal Intelligence View Controller
 * Visualizes carrier overcharge frequencies, recurring error patterns,
 * projected annual financial leakage, and automated contract renewal talking points.
 */
const ScorecardsView = {
  async init() {
    await this.loadScorecards();
  },

  async loadScorecards() {
    const container = document.getElementById("scorecards-content");
    if (!container) return;
    container.innerHTML = `<div style="padding: 40px; text-align: center; color: var(--text-muted);">Analyzing carrier billing metrics...</div>`;

    try {
      const scorecards = await API.getCarrierScorecards();
      const anomalies = await API.getAnomalies().catch(() => ({ total_anomalies: 0, anomalies: [] }));

      let html = `
        <!-- Anomaly Summary Alert if any -->
        ${anomalies.total_anomalies > 0 ? `
          <div class="card" style="margin-bottom: 24px; border-left: 4px solid var(--status-danger);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
              <strong style="color: var(--status-danger); font-size: 14px;">Cross-Invoice Anomalies Detected (${anomalies.total_anomalies})</strong>
              <span class="badge badge-danger">Action Required</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${anomalies.anomalies.map(a => `
                <div style="font-size: 13px; color: var(--text-secondary);">
                  &bull; <strong>${a.title}</strong>: ${a.description}
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <!-- Carrier Cards Grid -->
        <div style="display: flex; flex-direction: column; gap: 20px;">
      `;

      scorecards.forEach(sc => {
        const isHighRisk = sc.overcharge_rate_pct > 15.0;
        const statusBadge = isHighRisk 
          ? `<span class="badge badge-discrepancy">${sc.overcharge_rate_pct}% Error Rate</span>`
          : `<span class="badge badge-clean">${sc.overcharge_rate_pct}% Error Rate</span>`;

        html += `
          <div class="card">
            <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 14px;">
              <div>
                <div style="display: flex; align-items: center; gap: 10px;">
                  <h3 style="font-size: 16px; font-weight: 700; color: var(--text-primary);">${sc.name}</h3>
                  <span class="mono" style="font-size: 12px; color: var(--text-muted);">SCAC: ${sc.scac}</span>
                  ${statusBadge}
                </div>
                <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
                  Audited Freight Invoices: <strong>${sc.total_invoices}</strong> &bull; Total Billed: <strong class="amount">$${sc.total_billed_formatted}</strong>
                </div>
              </div>
              <div style="text-align: right;">
                <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Projected Annual Leakage</div>
                <div class="amount" style="font-size: 20px; font-weight: 700; color: ${isHighRisk ? 'var(--status-danger)' : 'var(--text-primary)'};">
                  $${sc.projected_annual_leakage_formatted}
                </div>
              </div>
            </div>

            <!-- Financial Position Bar -->
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
              <div style="background-color: var(--bg-muted); padding: 10px 14px; border-radius: var(--radius-sm);">
                <div style="font-size: 11px; color: var(--text-muted); font-weight: 600;">APPROVED PAYABLE</div>
                <div class="amount" style="font-size: 15px; font-weight: 700; color: var(--status-success);">$${sc.approved_payable_formatted}</div>
              </div>
              <div style="background-color: var(--bg-muted); padding: 10px 14px; border-radius: var(--radius-sm);">
                <div style="font-size: 11px; color: var(--text-muted); font-weight: 600;">DISPUTED VARIANCE</div>
                <div class="amount" style="font-size: 15px; font-weight: 700; color: var(--status-warning);">$${sc.disputed_formatted}</div>
              </div>
              <div style="background-color: var(--bg-muted); padding: 10px 14px; border-radius: var(--radius-sm);">
                <div style="font-size: 11px; color: var(--text-muted); font-weight: 600;">DISCREPANCY FREQUENCY</div>
                <div style="font-size: 15px; font-weight: 700; color: var(--text-primary);">${sc.overcharge_rate_pct}%</div>
              </div>
            </div>

            <!-- Talking Points for Master Agreement Renewal -->
            <div>
              <div style="font-size: 12px; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px;">
                Contract Renewal Talking Points & Evidence
              </div>
              <div class="talking-points-box">
                <ul style="padding-left: 18px; margin: 0; display: flex; flex-direction: column; gap: 6px;">
                  ${sc.talking_points.map(tp => `<li>${tp}</li>`).join('')}
                </ul>
              </div>
            </div>
          </div>
        `;
      });

      html += `</div>`;
      container.innerHTML = html;
    } catch (e) {
      container.innerHTML = `<div style="color: var(--status-danger); padding: 20px;">Failed to load carrier scorecards: ${e.message}</div>`;
    }
  }
};

