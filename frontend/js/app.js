/**
 * FreightGuard Core Application Controller
 * Manages view switching, role-based auth, theme toggle, modals, toasts,
 * live gateway status badges, upload workflow, and the 3-minute guided tour.
 */
const App = {
  currentView: "control-tower",
  currentUser: null,

  async init() {
    this.initTheme();
    this.bindNavigation();
    this.bindGlobalActions();
    this.bindModal();
    this.bindRoleSwitcher();
    this.bindUploadModal();
    
    // Auto-login default demo user (AP Clerk)
    await this.setupDefaultAuth();
    await this.refreshStatusBadges();

    // Initial view
    await this.navigateTo("control-tower");
  },

  initTheme() {
    const savedTheme = localStorage.getItem("fg_theme") || "dark";
    if (savedTheme === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }

    const themeBtn = document.getElementById("btn-theme-toggle");
    if (themeBtn) {
      themeBtn.addEventListener("click", () => {
        const isLight = document.documentElement.getAttribute("data-theme") === "light";
        if (isLight) {
          document.documentElement.removeAttribute("data-theme");
          localStorage.setItem("fg_theme", "dark");
          themeBtn.textContent = "🌓";
        } else {
          document.documentElement.setAttribute("data-theme", "light");
          localStorage.setItem("fg_theme", "light");
          themeBtn.textContent = "☀️";
        }
      });
    }
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
            this.refreshStatusBadges();
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

    // 3-Minute Automated Demo Button
    const guidedTourBtn = document.getElementById("btn-start-guided-tour");
    if (guidedTourBtn) {
      guidedTourBtn.addEventListener("click", () => this.runThreeMinuteGuidedTour());
    }
  },

  bindRoleSwitcher() {
    const roleBtns = document.querySelectorAll(".role-pill-btn");
    roleBtns.forEach(btn => {
      btn.addEventListener("click", async () => {
        const email = btn.getAttribute("data-email");
        await this.switchUser(email);
      });
    });
  },

  async setupDefaultAuth() {
    try {
      const email = localStorage.getItem("fg_active_email") || "clerk@freightguard.internal";
      await this.switchUser(email, false);
    } catch (e) {
      console.warn("Could not setup default auth:", e);
    }
  },

  async switchUser(email, notify = true) {
    try {
      const res = await API.login(email);
      API.setAuthToken(res.token);
      this.currentUser = res.user;
      localStorage.setItem("fg_active_email", email);

      // Update UI active state
      document.querySelectorAll(".role-pill-btn").forEach(btn => {
        if (btn.getAttribute("data-email") === email) {
          btn.classList.add("active");
        } else {
          btn.classList.remove("active");
        }
      });

      if (notify) {
        this.showToast(`Switched user to ${res.user.name} (${res.user.role})`, "info");
      }
    } catch (e) {
      console.error("Login failed:", e);
    }
  },

  bindUploadModal() {
    const uploadBtn = document.getElementById("btn-open-upload-modal");
    if (!uploadBtn) return;

    uploadBtn.addEventListener("click", () => {
      this.openModal(
        "Upload Freight Invoice (PDF or Text)",
        `
        <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
          Ingest a freight bill. Our hybrid extraction pipeline uses LLMs (Groq / Gemini / OpenAI) or deterministic rule extraction with local BM25 contract clause retrieval.
        </div>

        <div class="upload-dropzone" id="modal-dropzone" onclick="document.getElementById('modal-file-input').click()">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--accent-cyan); margin-bottom: 10px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
          <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">Click or drag PDF / Text freight invoice here</div>
          <div style="font-size: 11px; color: var(--text-muted);">Supports .pdf, .txt, or paste below</div>
          <input type="file" id="modal-file-input" accept=".pdf,.txt" style="display:none;">
        </div>

        <div style="margin: 16px 0; text-align: center; color: var(--text-muted); font-size: 11px; font-weight: 700;">OR PASTE INVOICE TEXT</div>

        <div class="form-group">
          <textarea id="modal-paste-text" class="form-input mono" rows="6" placeholder="INVOICE: INV-2025-EXAMPLE&#10;CARRIER: Apex Global Freight&#10;BASE FREIGHT: $3,200.00&#10;FUEL SURCHARGE: $740.00&#10;..."></textarea>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px;">
          <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
          <button class="btn btn-primary" id="btn-submit-upload" onclick="App.handleUploadSubmit()">
            Extract & Run Audit
          </button>
        </div>
        `
      );

      // Handle dropzone drag events
      const dropzone = document.getElementById("modal-dropzone");
      const fileInput = document.getElementById("modal-file-input");
      if (dropzone && fileInput) {
        dropzone.ondragover = (e) => { e.preventDefault(); dropzone.classList.add("dragover"); };
        dropzone.ondragleave = () => { dropzone.classList.remove("dragover"); };
        dropzone.ondrop = (e) => {
          e.preventDefault();
          dropzone.classList.remove("dragover");
          if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            App.showToast(`Selected file: ${e.dataTransfer.files[0].name}`, "info");
          }
        };
        fileInput.onchange = () => {
          if (fileInput.files.length > 0) {
            App.showToast(`Selected file: ${fileInput.files[0].name}`, "info");
          }
        };
      }
    });
  },

  async handleUploadSubmit() {
    const fileInput = document.getElementById("modal-file-input");
    const pasteText = document.getElementById("modal-paste-text")?.value;
    const submitBtn = document.getElementById("btn-submit-upload");

    const formData = new FormData();
    if (fileInput && fileInput.files.length > 0) {
      formData.append("file", fileInput.files[0]);
    } else if (pasteText && pasteText.trim()) {
      formData.append("raw_text", pasteText.trim());
    } else {
      this.showToast("Please select a file or paste invoice text.", "error");
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Processing Extraction...";
    }

    try {
      this.showToast("Parsing invoice and evaluating contract tariff rules...", "info");
      const res = await API.uploadInvoice(formData);
      this.closeModal();
      this.showToast(`Extraction Complete: ${res.invoice.invoice_number} audited! Legitimate payable: $${res.audit.approved_payable_formatted}`, "success");
      await this.navigateTo("workbench", res.invoice.id);
    } catch (e) {
      this.showToast(`Upload failed: ${e.message}`, "error");
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Extract & Run Audit";
      }
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

  async refreshStatusBadges() {
    try {
      const diag = await API.getSettings();
      const aiBadge = document.getElementById("ai-status-badge");
      const paypalBadge = document.getElementById("gateway-status-badge");
      const sidebarMode = document.getElementById("sidebar-mode-text");

      if (aiBadge) {
        aiBadge.textContent = `AI: ${diag.ai_engine.active_provider}`;
      }
      if (paypalBadge) {
        paypalBadge.textContent = `PayPal: ${diag.paypal.mode}`;
        if (diag.paypal.mode === "LIVE_SANDBOX") {
          paypalBadge.className = "badge badge-purple";
        } else {
          paypalBadge.className = "badge badge-clean";
        }
      }
      if (sidebarMode) {
        sidebarMode.textContent = diag.paypal.mode;
      }
    } catch (e) {
      console.warn("Could not refresh status badges:", e);
    }
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

  /**
   * 3-Minute Automated Guided Tour
   * End-to-end evidence-to-settlement walkthrough for judges.
   */
  async runThreeMinuteGuidedTour() {
    const sleep = (ms) => new Promise(r => setTimeout(r, ms));

    this.showToast("🚀 Step 1/7: Initializing clean signature demo state...", "info");
    await API.resetDemoData();
    await this.switchUser("clerk@freightguard.internal", false);
    await this.navigateTo("control-tower");
    await sleep(2000);

    this.showToast("🔍 Step 2/7: AP Clerk triggers autonomous audit on Apex Global (INV-2025-88419)...", "info");
    await API.runAudit("INV-2025-88419");
    await this.navigateTo("workbench", "INV-2025-88419");
    await sleep(2500);

    this.showToast("🤖 Step 3/7: Synthesizing natural-language AI audit explanation...", "info");
    await WorkbenchView.loadAiExplanation("INV-2025-88419");
    await sleep(2500);

    this.showToast("📝 Step 4/7: Generating formal dispute packet with BM25 contract citations...", "info");
    await this.navigateTo("disputes", "INV-2025-88419");
    await API.generateDispute("INV-2025-88419", "Autonomous contract rate audit discrepancy");
    await DisputesView.loadDisputes();
    await sleep(2500);

    this.showToast("✍️ Step 5/7: Switching to Approver 1 (Sarah Chen) to authorize settlement...", "info");
    await this.switchUser("sarah.chen@shipper.internal", false);
    await this.navigateTo("settlement", "INV-2025-88419");
    await sleep(1500);
    await API.authorizeSettlement(
      "INV-2025-88419",
      "sarah.chen@shipper.internal",
      "david.ross@shipper.internal",
      "Two-man approval for verified payable"
    );
    await SettlementView.loadSettlementView("INV-2025-88419");
    await sleep(2000);

    this.showToast("💳 Step 6/7: Executing PayPal Payout for legitimate payable ($3,342.00)...", "info");
    const payoutRes = await API.executePayout("INV-2025-88419");
    await SettlementView.loadSettlementView("INV-2025-88419");
    await sleep(2500);

    this.showToast("⚡ Step 7/7: PayPal Webhook reconciles payment state machine to RECONCILED!", "success");
    await API.simulateWebhook("PAYMENT.PAYOUTS-ITEM.SUCCEEDED", payoutRes.paypal_item_id, payoutRes.paypal_batch_id);
    await SettlementView.loadSettlementView("INV-2025-88419");
    await sleep(2000);

    await this.navigateTo("control-tower");
    this.showToast("🏆 3-Minute Guided Tour Complete! Full Evidence-to-Settlement lifecycle verified.", "success");
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
