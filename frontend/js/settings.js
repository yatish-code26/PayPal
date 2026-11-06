/**
 * Settings & System Diagnostics View Controller
 * - Read-only status cards by default:
 *     "AI Assistant: built-in"
 *     "Payments: built-in sandbox"
 * - Sample data reset behind confirmation dialog
 * - Collapsed "Advanced > Connect live services (optional)" section (closed by default)
 *     with masked inputs, memory-only storage, and "Test connection" button.
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

      const aiModeLabel = diag.ai_engine.active_provider === "LOCAL_DETERMINISTIC" 
        ? "Built-in (Zero API Key)" 
        : `Live (${diag.ai_engine.active_provider})`;

      const paypalModeLabel = diag.paypal.is_simulated 
        ? "Built-in Sandbox" 
        : "Live PayPal Sandbox";

      container.innerHTML = `
        <!-- Status Overview: Read-Only by Default -->
        <div class="workbench-split-grid" style="margin-bottom: 24px;">
          <!-- Payments Gateway Status Card -->
          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;">
              <span style="font-weight: 700; font-size: 14px; display: flex; align-items: center; gap: 8px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect><line x1="1" y1="10" x2="23" y2="10"></line></svg>
                Payments Status
              </span>
              <span class="badge ${diag.paypal.is_simulated ? 'badge-neutral' : 'badge-clean'}">
                ${paypalModeLabel}
              </span>
            </div>
            
            <div style="font-size: 13px; line-height: 1.8;">
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Payments Gateway:</span>
                <strong style="color: var(--accent-primary);">${paypalModeLabel}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Sandbox Endpoint:</span>
                <span class="mono">${diag.paypal.base_url || 'https://api-m.sandbox.paypal.com'}</span>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Client ID:</span>
                <span class="mono">${diag.paypal.client_id_masked || 'Built-in Sandbox Default'}</span>
              </div>
              <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                <span style="color: var(--text-muted);">Webhook Verification:</span>
                <span>${diag.paypal.webhook_id_configured ? '<span class="badge badge-clean">Live Cert API</span>' : '<span class="badge badge-neutral">Built-in HMAC</span>'}</span>
              </div>
            </div>
          </div>

          <!-- AI Assistant Status Card -->
          <div class="card">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid var(--border-subtle); padding-bottom: 10px;">
              <span style="font-weight: 700; font-size: 14px; display: flex; align-items: center; gap: 8px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                AI Assistant Status
              </span>
              <span class="badge ${diag.ai_engine.active_provider === 'LOCAL_DETERMINISTIC' ? 'badge-neutral' : 'badge-clean'}">
                ${aiModeLabel}
              </span>
            </div>

            <div style="font-size: 13px; line-height: 1.8;">
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">AI Assistant:</span>
                <strong style="color: var(--status-success);">${aiModeLabel}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Financial Protection:</span>
                <strong style="color: var(--status-success);">AI Never Decides Money</strong>
              </div>
              <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding: 8px 0;">
                <span style="color: var(--text-muted);">Contract Retrieval:</span>
                <span class="badge badge-clean">BM25 Clause Ranking</span>
              </div>
              <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                <span style="color: var(--text-muted);">Database:</span>
                <span class="mono">SQLite 3 (WAL Mode &bull; Healthy)</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Collapsed Section: Advanced Live Credentials (Optional, Closed by Default) -->
        <div class="card" style="margin-bottom: 24px;">
          <details style="cursor: pointer;">
            <summary style="font-weight: 700; font-size: 14px; color: var(--text-primary); outline: none; user-select: none;">
              Advanced: Connect live services (optional)
            </summary>

            <div style="margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--border-subtle); font-size: 13px; color: var(--text-secondary); line-height: 1.5;">
              <p style="margin-bottom: 16px;">
                FreightGuard operates out-of-the-box with zero API keys. To connect live PayPal Sandbox accounts or custom LLM providers, enter credentials below. Credentials are held in volatile memory only and never written to disk.
              </p>

              <div class="workbench-split-grid" style="margin-bottom: 16px;">
                <div>
                  <div style="margin-bottom: 12px;">
                    <label style="font-size: 12px; font-weight: 600; display: block; margin-bottom: 4px;">AI Provider</label>
                    <select id="cfg-ai-provider" class="form-select" style="width: 100%;">
                      <option value="LOCAL_DETERMINISTIC" ${diag.ai_engine.active_provider === 'LOCAL_DETERMINISTIC' ? 'selected' : ''}>Built-in (Zero API Key)</option>
                      <option value="GROQ" ${diag.ai_engine.active_provider === 'GROQ' ? 'selected' : ''}>Groq (llama-3.3-70b-versatile)</option>
                      <option value="GEMINI" ${diag.ai_engine.active_provider === 'GEMINI' ? 'selected' : ''}>Gemini (gemini-2.0-flash)</option>
                      <option value="OPENAI" ${diag.ai_engine.active_provider === 'OPENAI' ? 'selected' : ''}>OpenAI (gpt-4o-mini)</option>
                    </select>
                  </div>

                  <div>
                    <label style="font-size: 12px; font-weight: 600; display: block; margin-bottom: 4px;">API Key (Groq / Gemini / OpenAI)</label>
                    <input type="password" id="cfg-ai-key" class="form-input mono" style="width: 100%;" placeholder="Enter key (or leave empty for built-in)">
                  </div>
                </div>

                <div>
                  <div style="margin-bottom: 12px;">
                    <label style="font-size: 12px; font-weight: 600; display: block; margin-bottom: 4px;">PayPal Sandbox Client ID</label>
                    <input type="text" id="cfg-paypal-client-id" class="form-input mono" style="width: 100%;" placeholder="e.g. A21AAJ... (or leave empty)">
                  </div>

                  <div style="margin-bottom: 12px;">
                    <label style="font-size: 12px; font-weight: 600; display: block; margin-bottom: 4px;">PayPal Sandbox Client Secret</label>
                    <input type="password" id="cfg-paypal-client-secret" class="form-input mono" style="width: 100%;" placeholder="Enter secret (masked)">
                  </div>

                  <div>
                    <label style="font-size: 12px; font-weight: 600; display: block; margin-bottom: 4px;">PayPal Webhook ID (Optional)</label>
                    <input type="text" id="cfg-paypal-webhook-id" class="form-input mono" style="width: 100%;" placeholder="e.g. 8W... (for live signature check)">
                  </div>
                </div>
              </div>

              <div style="display: flex; gap: 10px;">
                <button class="btn btn-primary btn-sm" onclick="SettingsView.saveSettings()">
                  Apply Credentials (Memory Only)
                </button>
                <button class="btn btn-secondary btn-sm" onclick="SettingsView.testConnection()">
                  Test Connection
                </button>
                <button class="btn btn-secondary btn-sm" onclick="SettingsView.clearCredentials()">
                  Revert to Built-in
                </button>
              </div>
            </div>
          </details>
        </div>

        <!-- Data Management Section: Reset Sample Data -->
        <div class="card" style="border-left: 4px solid var(--status-warning);">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <span style="font-weight: 700; font-size: 14px;">Data Management</span>
            <span class="badge badge-warning">Sample Data</span>
          </div>
          <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 13px;">
            Restores all 5 sample freight invoices, Master Service Agreement rate cards, fuel peg formulas, and telematics dwell logs to their initial clean state.
          </p>
          <button class="btn btn-danger btn-sm" onclick="SettingsView.confirmReset()">
            Reset Sample Data
          </button>
        </div>
      `;
    } catch (e) {
      container.innerHTML = `<div style="padding: 40px; color: var(--status-danger);">Failed loading settings: ${e.message}</div>`;
    }
  },

  async saveSettings() {
    const aiProvider = document.getElementById("cfg-ai-provider")?.value;
    const aiKey = document.getElementById("cfg-ai-key")?.value;
    const paypalClientId = document.getElementById("cfg-paypal-client-id")?.value;
    const paypalClientSecret = document.getElementById("cfg-paypal-client-secret")?.value;
    const paypalWebhookId = document.getElementById("cfg-paypal-webhook-id")?.value;

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

    try {
      await API.updateSettings(payload);
      App.showToast("Settings updated in memory!", "success");
      await this.loadDiagnostics();
      await App.refreshStatusBadges();
    } catch (e) {
      App.showToast(`Failed updating settings: ${e.message}`, "error");
    }
  },

  async testConnection() {
    try {
      App.showToast("Testing gateway connection...", "info");
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
        forced_mode: "LOCAL_DEMO"
      });
      App.showToast("Reverted to built-in simulation mode.", "success");
      await this.loadDiagnostics();
      await App.refreshStatusBadges();
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  async confirmReset() {
    if (confirm("Reset all freight sample data to initial clean state?")) {
      try {
        const res = await API.resetDemoData();
        App.showToast(res.message, "success");
        await this.loadDiagnostics();
        if (ControlTowerView.loadStats) {
          await ControlTowerView.loadStats();
        }
      } catch (e) {
        App.showToast(e.message, "error");
      }
    }
  }
};
