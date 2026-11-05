/**
 * Settings & Integrations View Controller
 * Runtime configuration for AI providers, PayPal Sandbox credentials,
 * connection tests, failure simulation, and safe masked credential viewing.
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
                ${diag.paypal.is_simulated ? 'Offline Simulator' : 'Live Sandbox'}
              </span>
            </div>
            
            <div style="font-size: 13px; line-height: 1.8;">
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Active Mode:</span>
                <strong style="color: var(--accent-cyan);">${diag.paypal.mode}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">PayPal Sandbox Endpoint:</span>
                <span class="mono">${diag.paypal.base_url}</span>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Client ID (Masked):</span>
                <span class="mono">${diag.paypal.client_id_masked || 'None (Using Local Demo)'}</span>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Client Secret:</span>
                <span>${diag.paypal.client_secret_configured ? '<span class="badge badge-clean">Configured (In-Memory/Env)</span>' : '<span class="badge badge-info">Offline Demo Active</span>'}</span>
              </div>
              <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                <span style="color: var(--text-muted);">Webhook ID:</span>
                <span class="mono">${diag.paypal.webhook_id_configured ? '<span class="badge badge-clean">Configured</span>' : '<span class="badge badge-info">Local HMAC Active</span>'}</span>
              </div>
            </div>
          </div>

          <!-- AI & Deterministic Engine Card -->
          <div class="panel-card">
            <div class="panel-header">
              <span class="panel-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                AI & Deterministic Policy Engine
              </span>
              <span class="badge badge-clean">Operational</span>
            </div>

            <div style="font-size: 13px; line-height: 1.8;">
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Active Provider:</span>
                <strong style="color: var(--accent-cyan);">${diag.ai_engine.active_provider}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Financial Rule:</span>
                <strong style="color: var(--status-success);">AI Never Decides Money (Policy Gate)</strong>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Contract RAG Search:</span>
                <span class="badge badge-info">BM25 Ranked Clause Matching</span>
              </div>
              <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                <span style="color: var(--text-muted);">Database Engine:</span>
                <span class="mono">${diag.database.engine} (WAL Mode + Foreign Keys)</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Runtime Configuration Drawer Card -->
        <div class="panel-card" style="margin-bottom: 24px;">
          <div class="panel-header">
            <span class="panel-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
              Runtime Credentials & Mode Configuration (Kept in Memory)
            </span>
            <span class="badge badge-info">Zero Disk Persistence</span>
          </div>

          <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
            Enter your live PayPal Sandbox credentials or model API keys below for live evaluation. Keys are held in memory only and never written to disk or logs. Leaving these blank preserves the safe offline simulation mode.
          </p>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
            <div>
              <div class="form-group">
                <label class="form-label">AI Model Provider</label>
                <select id="cfg-ai-provider" class="form-select">
                  <option value="LOCAL_DETERMINISTIC" ${diag.ai_engine.active_provider === 'LOCAL_DETERMINISTIC' ? 'selected' : ''}>LOCAL_DETERMINISTIC (Zero API Key)</option>
                  <option value="GROQ" ${diag.ai_engine.active_provider === 'GROQ' ? 'selected' : ''}>GROQ (llama-3.3-70b-versatile)</option>
                  <option value="GEMINI" ${diag.ai_engine.active_provider === 'GEMINI' ? 'selected' : ''}>GEMINI (gemini-2.0-flash)</option>
                  <option value="OPENAI" ${diag.ai_engine.active_provider === 'OPENAI' ? 'selected' : ''}>OPENAI (gpt-4o-mini)</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">AI Provider API Key (Groq / Gemini / OpenAI)</label>
                <input type="password" id="cfg-ai-key" class="form-input mono" placeholder="Enter key (leave blank to use env or local simulator)">
              </div>

              <div class="form-group">
                <label class="form-label">PayPal Simulator Failure Mode (Demo Toggle)</label>
                <select id="cfg-failure-mode" class="form-select">
                  <option value="">Normal Operation (Successful Payouts)</option>
                  <option value="UNCLAIMED">Simulate UNCLAIMED Payout Item</option>
                  <option value="FAILED">Simulate FAILED Payout Item</option>
                  <option value="BLOCKED">Simulate BLOCKED Payout Item</option>
                </select>
              </div>
            </div>

            <div>
              <div class="form-group">
                <label class="form-label">PayPal Developer Sandbox Client ID</label>
                <input type="text" id="cfg-paypal-client-id" class="form-input mono" placeholder="e.g. A21AAJ... (leave empty for LOCAL_DEMO)">
              </div>

              <div class="form-group">
                <label class="form-label">PayPal Developer Sandbox Client Secret</label>
                <input type="password" id="cfg-paypal-client-secret" class="form-input mono" placeholder="Enter PayPal client secret">
              </div>

              <div class="form-group">
                <label class="form-label">PayPal Webhook ID (Optional)</label>
                <input type="text" id="cfg-paypal-webhook-id" class="form-input mono" placeholder="e.g. 8W... (for live webhook verification)">
              </div>
            </div>
          </div>

          <div style="display: flex; gap: 10px; margin-top: 14px;">
            <button class="btn btn-primary" onclick="SettingsView.saveSettings()">
              Apply Runtime Settings
            </button>
            <button class="btn btn-secondary" onclick="SettingsView.testConnection()">
              Test Connection
            </button>
            <button class="btn btn-secondary" onclick="SettingsView.clearCredentials()">
              Revert to Safe Offline Demo
            </button>
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
      container.innerHTML = `<div style="padding: 40px; color: var(--status-danger);">Failed loading settings diagnostics: ${e.message}</div>`;
    }
  },

  async saveSettings() {
    const aiProvider = document.getElementById("cfg-ai-provider")?.value;
    const aiKey = document.getElementById("cfg-ai-key")?.value;
    const paypalClientId = document.getElementById("cfg-paypal-client-id")?.value;
    const paypalClientSecret = document.getElementById("cfg-paypal-client-secret")?.value;
    const paypalWebhookId = document.getElementById("cfg-paypal-webhook-id")?.value;
    const failureMode = document.getElementById("cfg-failure-mode")?.value;

    const payload = {};
    if (aiProvider) payload.ai_provider = aiProvider;
    if (aiKey) {
      if (aiProvider === "GROQ") payload.groq_api_key = aiKey;
      else if (aiProvider === "GEMINI") payload.gemini_api_key = aiKey;
      else if (aiProvider === "OPENAI") payload.openai_api_key = aiKey;
    }
    if (paypalClientId) payload.paypal_client_id = paypalClientId;
    if (paypalClientSecret) payload.paypal_client_secret = paypalClientSecret;
    if (paypalWebhookId) payload.paypal_webhook_id = paypalWebhookId;
    if (failureMode !== undefined) payload.simulator_failure_mode = failureMode;

    try {
      const res = await API.updateSettings(payload);
      App.showToast("Settings updated successfully!", "success");
      await this.loadDiagnostics();
      await App.refreshStatusBadges();
    } catch (e) {
      App.showToast(`Failed to update settings: ${e.message}`, "error");
    }
  },

  async testConnection() {
    try {
      App.showToast("Testing gateway connections...", "info");
      const res = await API.testConnection();
      App.showToast(`Connection Test: PayPal [${res.paypal.status}], AI [${res.ai.status}]`, "success");
    } catch (e) {
      App.showToast(`Connection test failed: ${e.message}`, "error");
    }
  },

  async clearCredentials() {
    try {
      await API.updateSettings({
        paypal_client_id: "",
        paypal_client_secret: "",
        paypal_webhook_id: "",
        forced_mode: "LOCAL_DEMO",
        simulator_failure_mode: ""
      });
      App.showToast("Reverted to offline simulation mode.", "success");
      await this.loadDiagnostics();
      await App.refreshStatusBadges();
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  async confirmReset() {
    if (confirm("Reset all freight data to initial signature demo state?")) {
      try {
        const res = await API.resetDemoData();
        App.showToast(res.message, "success");
        await this.loadDiagnostics();
      } catch (e) {
        App.showToast(e.message, "error");
      }
    }
  }
};
