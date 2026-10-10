/**
 * Settings & Integrations View Controller
 * Diagnostic views of connection status, safe credential masking, and demo reset.
 */
const SettingsView = {
  async init() {
    await this.loadDiagnostics();
  },

  async loadDiagnostics() {
    const container = document.getElementById("settings-content");
    if (!container) return;
    container.innerHTML = `<div style="padding: 40px; text-align: center; color: var(--text-muted);">Loading system diagnostics...</div>`;

    try {
      const diag = await API.getSettings();

      container.innerHTML = `
        <div class="workbench-grid" style="margin-bottom: 24px;">
          <!-- PayPal Sandbox Card -->
          <div class="panel-card">
            <div class="panel-header">
              <span class="panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line></svg>
                PayPal Developer Platform Integration
              </span>
              <span class="badge ${diag.paypal.is_simulated ? 'badge-info' : 'badge-clean'}">
                ${diag.paypal.is_simulated ? 'Offline Simulator' : 'Live Gateway'}
              </span>
            </div>
            
            <div style="font-size: 13px; line-height: 1.8;">
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Gateway Mode:</span>
                <strong style="color: var(--accent-cyan);">${diag.paypal.status_label}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">PayPal Sandbox Endpoint:</span>
                <span class="mono">${diag.paypal.endpoint}</span>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Client ID (Masked):</span>
                <span class="mono">${diag.paypal.client_id_masked}</span>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Client Secret:</span>
                <span>${diag.paypal.client_secret_configured ? '<span class="badge badge-clean">Configured (Server-Side)</span>' : '<span class="badge badge-info">Safe Offline Default</span>'}</span>
              </div>
              <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                <span style="color: var(--text-muted);">Supported Payout API:</span>
                <span class="mono">POST /v1/payments/payouts</span>
              </div>
            </div>
          </div>

          <!-- AI & Deterministic Engine Card -->
          <div class="panel-card">
            <div class="panel-header">
              <span class="panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                AI & Deterministic Audit Engine
              </span>
              <span class="badge badge-clean">Operational</span>
            </div>

            <div style="font-size: 13px; line-height: 1.8;">
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Engine Architecture:</span>
                <strong>${diag.ai_engine.provider}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Financial Arithmetic:</span>
                <strong style="color: var(--accent-cyan);">${diag.ai_engine.confidence_model} (Zero Float Loss)</strong>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Database Engine:</span>
                <span class="mono">${diag.database.engine} (WAL Mode + Foreign Keys)</span>
              </div>
              <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                <span style="color: var(--text-muted);">Webhook Replay Defense:</span>
                <span class="badge badge-clean">Strict ID Deduplication</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Demo Data Reset Action Card -->
        <div class="panel-card" style="border-left: 4px solid var(--status-warning);">
          <div class="panel-header">
            <span class="panel-title">Demonstration Environment State Management</span>
            <span class="badge badge-warning">Resettable Dataset</span>
          </div>
          <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 13px;">
            Resetting the demo dataset restores all 5 freight logistics invoices, Master Service Agreements (MSAs), DOE diesel fuel surcharge formulas, and shipment telematics to their clean signature demonstration state.
          </p>
          <button class="btn btn-danger" onclick="SettingsView.confirmReset()">
            Reset All Demo Data to Signature State
          </button>
        </div>
      `;
    } catch (e) {
      container.innerHTML = `<div style="padding: 40px; color: var(--status-danger);">Failed loading diagnostics: ${e.message}</div>`;
    }
  },

  confirmReset() {
    if (confirm("Reset demo data? This will restore the signature $2,180 discrepancy scenario for demonstration.")) {
      API.resetDemoData().then(res => {
        App.showToast(res.message, "success");
        App.navigateTo("control-tower");
      }).catch(err => {
        App.showToast(err.message, "error");
      });
    }
  }
};
