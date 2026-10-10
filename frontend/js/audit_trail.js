/**
 * Audit & Agent Activity View Controller
 * Displays chronological, persisted state transitions and actor logs.
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
  },

  async loadEvents() {
    const tbody = document.getElementById("audit-events-tbody");
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 30px; color: var(--text-muted);">Loading audit events...</td></tr>`;

    try {
      const events = await API.getAuditEvents();
      tbody.innerHTML = "";

      if (events.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 30px; color: var(--text-muted);">No audit events recorded yet.</td></tr>`;
        return;
      }

      events.forEach(ev => {
        const tr = document.createElement("tr");
        const actorBadge = this.getActorBadge(ev.actor);
        const dateStr = new Date(ev.created_at).toLocaleString();

        tr.innerHTML = `
          <td class="mono" style="font-size: 11px; color: var(--text-muted); white-space: nowrap;">${dateStr}</td>
          <td><strong style="color: var(--text-primary); font-size: 12px;" class="mono">${ev.event_name}</strong></td>
          <td><span class="mono" style="font-size: 11px; color: var(--accent-cyan);">${ev.entity_type}:${ev.entity_id}</span></td>
          <td>${actorBadge}</td>
          <td>
            <pre style="font-size: 11px; color: var(--text-secondary); max-width: 480px; overflow-x: auto; font-family: var(--font-mono);">${JSON.stringify(ev.details, null, 1)}</pre>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" style="color: var(--status-danger); padding: 20px;">Failed loading audit trail: ${e.message}</td></tr>`;
    }
  },

  getActorBadge(actor) {
    if (actor.includes("POLICY") || actor.includes("FINANCIAL")) {
      return `<span class="badge badge-clean">${actor}</span>`;
    } else if (actor.includes("PAYPAL") || actor.includes("WEBHOOK")) {
      return `<span class="badge badge-purple">${actor}</span>`;
    } else if (actor.includes("HUMAN")) {
      return `<span class="badge badge-warning">${actor}</span>`;
    } else {
      return `<span class="badge badge-info">${actor}</span>`;
    }
  }
};
