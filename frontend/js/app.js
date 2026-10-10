/**
 * FreightGuard Core Application Controller
 * Manages view switching, modals, toasts, status badges, and signature demo flows.
 */
const App = {
  currentView: "control-tower",

  async init() {
    this.bindNavigation();
    this.bindGlobalActions();
    this.bindModal();
    
    // Initial view
    await this.navigateTo("control-tower");
  },

  bindNavigation() {
    document.querySelectorAll(".nav-item").forEach(item => {
      item.addEventListener("click", (e) => {
        e.preventDefault();
        const view = item.getAttribute("data-view");
        this.navigateTo(view);
      });
    });
  },

  bindGlobalActions() {
    // Reset Demo Button
    const resetBtn = document.getElementById("btn-reset-demo");
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        if (confirm("Reset all freight data to initial signature demo state?")) {
          API.resetDemoData().then(res => {
            this.showToast(res.message, "success");
            this.navigateTo("control-tower");
          }).catch(err => {
            this.showToast(err.message, "error");
          });
        }
      });
    }

    // Quick Run Demo Button
    const quickDemoBtn = document.getElementById("btn-quick-run-demo");
    if (quickDemoBtn) {
      quickDemoBtn.addEventListener("click", () => this.runSignatureDemo());
    }
  },

  bindModal() {
    const modal = document.getElementById("app-modal");
    const closeBtn = document.getElementById("modal-close-btn");
    if (closeBtn && modal) {
      closeBtn.addEventListener("click", () => this.closeModal());
      modal.addEventListener("click", (e) => {
        if (e.target === modal) this.closeModal();
      });
    }
  },

  openModal(title, htmlBody) {
    const modal = document.getElementById("app-modal");
    const titleEl = document.getElementById("modal-title");
    const bodyEl = document.getElementById("modal-body");
    if (modal && titleEl && bodyEl) {
      titleEl.textContent = title;
      bodyEl.innerHTML = htmlBody;
      modal.classList.add("active");
    }
  },

  closeModal() {
    const modal = document.getElementById("app-modal");
    if (modal) modal.classList.remove("active");
  },

  showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  },

  async navigateTo(viewName, entityId = null) {
    this.currentView = viewName;

    // Update active nav item
    document.querySelectorAll(".nav-item").forEach(item => {
      if (item.getAttribute("data-view") === viewName) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });

    // Update active section
    document.querySelectorAll(".view-section").forEach(sec => {
      sec.classList.remove("active");
    });
    const targetSec = document.getElementById(`view-${viewName}`);
    if (targetSec) targetSec.classList.add("active");

    // Update breadcrumb
    const breadcrumb = document.getElementById("current-view-title");
    if (breadcrumb) {
      breadcrumb.textContent = this.formatViewTitle(viewName);
    }

    // Trigger view-specific loaders
    switch (viewName) {
      case "control-tower":
        await ControlTowerView.init();
        break;
      case "invoices":
        await InvoicesView.init();
        break;
      case "workbench":
        await WorkbenchView.init(entityId);
        break;
      case "disputes":
        await DisputesView.init(entityId);
        break;
      case "settlement":
        await SettlementView.init(entityId);
        break;
      case "audit-trail":
        await AuditTrailView.init();
        break;
      case "settings":
        await SettingsView.init();
        break;
    }
  },

  formatViewTitle(viewName) {
    const map = {
      "control-tower": "Control Tower",
      "invoices": "Invoice Intelligence",
      "workbench": "Evidence Workbench",
      "disputes": "Dispute Center",
      "settlement": "Settlement Center",
      "audit-trail": "Agent & Audit Trail",
      "settings": "Settings & Diagnostics"
    };
    return map[viewName] || "Control Tower";
  },

  async quickAudit(invoiceId) {
    try {
      const res = await API.runAudit(invoiceId);
      this.showToast(res.summary_message, res.disputed_amount_cents > 0 ? "warning" : "success");
      
      // If currently on control tower or invoices, refresh stats
      if (this.currentView === "control-tower") {
        await ControlTowerView.init();
      } else if (this.currentView === "invoices") {
        await InvoicesView.loadInvoices();
      } else if (this.currentView === "workbench") {
        await WorkbenchView.loadWorkbenchData(invoiceId);
      }
    } catch (e) {
      this.showToast(`Audit failed: ${e.message}`, "error");
    }
  },

  async runSignatureDemo() {
    this.showToast("Starting Signature Demo: Auditing Invoice #INV-2025-88419...", "info");
    try {
      const res = await API.runAudit("INV-2025-88419");
      this.showToast(`Autonomous Audit Result: Flagged $${res.disputed_amount_formatted} in discrepancies! Legitimate payable: $${res.approved_payable_formatted}.`, "warning");
      await this.navigateTo("workbench", "INV-2025-88419");
    } catch (e) {
      this.showToast(e.message, "error");
    }
  },

  getAuditStatusBadge(status) {
    switch (status) {
      case "AUDITED_CLEAN":
        return `<span class="badge badge-clean">Audited (Clean)</span>`;
      case "AUDITED_DISCREPANCY":
        return `<span class="badge badge-discrepancy">Discrepancy</span>`;
      case "PENDING_AUDIT":
        return `<span class="badge badge-pending">Pending Audit</span>`;
      case "DISPUTED":
        return `<span class="badge badge-warning">Disputed</span>`;
      case "BLOCKED":
        return `<span class="badge badge-danger">Blocked</span>`;
      default:
        return `<span class="badge badge-info">${status}</span>`;
    }
  },

  getSettlementStatusBadge(status) {
    switch (status) {
      case "RECONCILED":
        return `<span class="badge badge-clean">Reconciled</span>`;
      case "PAYOUT_SUCCESS":
      case "PAYOUT_INITIATED":
        return `<span class="badge badge-purple">Payout Sent</span>`;
      case "AUTHORIZED":
        return `<span class="badge badge-clean">Authorized</span>`;
      case "UNSETTLED":
        return `<span class="badge badge-pending">Unsettled</span>`;
      case "PAYOUT_FAILED":
        return `<span class="badge badge-danger">Failed</span>`;
      default:
        return `<span class="badge badge-info">${status}</span>`;
    }
  },

  getLineItemBadge(findingStatus) {
    switch (findingStatus) {
      case "VALID":
        return `<span class="badge badge-clean">Valid</span>`;
      case "OVERCHARGE":
        return `<span class="badge badge-discrepancy">Overcharge</span>`;
      case "UNAUTHORIZED":
        return `<span class="badge badge-danger">Unauthorized</span>`;
      case "DUPLICATE":
        return `<span class="badge badge-danger">Duplicate</span>`;
      default:
        return `<span class="badge badge-info">${findingStatus}</span>`;
    }
  }
};

// Initialize App when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  App.init();
});
