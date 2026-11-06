/**
 * Activity & Audit Trail View Controller
 * - Chronological immutable event log
 * - SHA-256 cryptographic hash-chaining verification
 * - Validates tamper-evidence across all state transitions
 */
const AuditTrailView = {
  async init() {
    await this.loadEvents();
    this.bindEvents();
  },

  bindEvents() {
    const refreshBtn = document.getElementById("btn-refresh-audit-events");
    if (refreshBtn) {
      refreshBtn.onclick = () => this.loadEvents();
    }

    const verifyBtn = document.getElementById("btn-verify-audit-chain");
    if (verifyBtn) {
      verifyBtn.onclick = () => this.verifyIntegrity();
    }
  },

  async loadEvents() {
    const tbody = document.getElementById("audit-events-tbody");
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 32px; color: var(--text-muted);">Loading audit trail records...</td></tr>`;

    try {
      const events = await API.getAuditEvents();
      tbody.innerHTML = "";

      if (events.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 32px; color: var(--text-muted);">No audit events recorded yet.</td></tr>`;
        return;
      }

      events.forEach(ev => {
        const tr = document.createElement("tr");
        const actorBadge = this.getActorBadge(ev.actor);
        const dateStr = new Date(ev.created_at).toLocaleString();
        const hashDisplay = ev.event_hash ? ev.event_hash.substring(0, 12) + "..." : "GENESIS";

        tr.innerHTML = `
          <td class="mono" style="font-size: 11px; color: var(--text-muted); white-space: nowrap;">${dateStr}</td>
          <td><strong style="color: var(--text-primary); font-size: 13px;" class="mono">${ev.event_name}</strong></td>
          <td><span class="mono" style="font-size: 11px; color: var(--accent-primary);">${ev.entity_type}:${ev.entity_id}</span></td>
          <td>${actorBadge}</td>
          <td class="hash-cell" title="Full SHA-256: ${ev.event_hash || ''}">${hashDisplay}</td>
          <td>
            <pre style="font-size: 11px; color: var(--text-secondary); max-width: 440px; overflow-x: auto; font-family: var(--font-mono); margin: 0;">${JSON.stringify(ev.details, null, 1)}</pre>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="6" style="color: var(--status-danger); padding: 20px;">Failed loading audit trail: ${e.message}</td></tr>`;
    }
  },

  async verifyIntegrity() {
    const alertBox = document.getElementById("integrity-verification-alert");
    if (!alertBox) return;

    try {
      alertBox.innerHTML = `<div style="font-size: 13px; color: var(--text-muted);">Cryptographically verifying hash chain...</div>`;
      const res = await API.verifyAuditIntegrity();

      if (res.chain_valid) {
        alertBox.innerHTML = `
          <div class="integrity-badge" style="width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 12px 16px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
              <span><strong>Tamper-Evident Chain Verified:</strong> All ${res.total_events} audit events validated. SHA-256 links intact.</span>
            </div>
            <span class="mono" style="font-size: 11px;">Head: ${res.latest_hash ? res.latest_hash.substring(0, 16) + '...' : 'N/A'}</span>
          </div>
        `;
        App.showToast("Cryptographic audit log integrity verified!", "success");
      } else {
        alertBox.innerHTML = `
          <div class="badge badge-danger" style="width: 100%; padding: 12px 16px; font-size: 13px;">
            <strong>Integrity Alert:</strong> Hash verification failed at event #${res.failed_event_id}. Log tampering detected.
          </div>
        `;
        App.showToast("Log integrity verification failed!", "error");
      }
    } catch (e) {
      alertBox.innerHTML = `<div style="color: var(--status-danger);">Verification failed: ${e.message}</div>`;
    }
  },

  getActorBadge(actor) {
    if (actor.includes("POLICY") || actor.includes("FINANCIAL")) {
      return `<span class="badge badge-clean">${actor}</span>`;
    } else if (actor.includes("PAYPAL") || actor.includes("WEBHOOK")) {
      return `<span class="badge badge-purple">${actor}</span>`;
    } else if (actor.includes("HUMAN") || actor.includes("CLERK") || actor.includes("APPROVER")) {
      return `<span class="badge badge-warning">${actor}</span>`;
    } else {
      return `<span class="badge badge-neutral">${actor}</span>`;
    }
  }
};
