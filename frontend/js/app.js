/**
 * FreightGuard Core Application Controller
 * Modern fintech client controller supporting:
 * - Clean view navigation & breadcrumbs
 * - Role-based authentication & dropdown switcher
 * - Command palette (Ctrl+K) with instant search
 * - Floating "Ask FreightGuard" AI chat drawer
 * - Invoice upload & hybrid extraction
 * - Light/Dark theme switching
 */
const App = {
  currentView: "home",
  currentUser: null,
  invoicesCache: [],

  async init() {
    this.initTheme();
    this.bindNavigation();
    this.bindRoleDropdown();
    this.bindCommandPalette();
    this.bindChatDrawer();
    this.bindUploadModal();
    this.bindGlobalKeyboardShortcuts();
    
    // Auto-login default demo user (Sarah Chen, AP Clerk)
    await this.setupDefaultAuth();
    await this.refreshStatusBadges();

    // Initial view navigation
    await this.navigateTo("home");
  },

  initTheme() {
    const savedTheme = localStorage.getItem("fg_theme") || "light";
    if (savedTheme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }

    const themeBtn = document.getElementById("btn-theme-toggle");
    if (themeBtn) {
      themeBtn.textContent = savedTheme === "dark" ? "☀️" : "🌓";
      themeBtn.addEventListener("click", () => {
        const isDark = document.documentElement.getAttribute("data-theme") === "dark";
        if (isDark) {
          document.documentElement.removeAttribute("data-theme");
          localStorage.setItem("fg_theme", "light");
          themeBtn.textContent = "🌓";
        } else {
          document.documentElement.setAttribute("data-theme", "dark");
          localStorage.setItem("fg_theme", "dark");
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

    // Header primary action button
    const primaryBtn = document.getElementById("btn-primary-action");
    if (primaryBtn) {
      primaryBtn.addEventListener("click", () => {
        this.openUploadModal();
      });
    }
  },

  bindRoleDropdown() {
    const btn = document.getElementById("btn-user-dropdown");
    const menu = document.getElementById("user-dropdown-list");
    if (!btn || !menu) return;

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.toggle("show");
    });

    document.addEventListener("click", () => {
      menu.classList.remove("show");
    });

    menu.querySelectorAll(".dropdown-item").forEach(item => {
      item.addEventListener("click", async () => {
        const email = item.getAttribute("data-email");
        await this.switchUser(email);
        menu.classList.remove("show");
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

      // Update header label and avatar
      const label = document.getElementById("header-user-label");
      const avatar = document.getElementById("header-user-avatar");
      if (label) {
        label.textContent = `Signed in as ${res.user.name} (${res.user.role.replace('_', ' ')})`;
      }
      if (avatar) {
        const initials = res.user.name.split(" ").map(p => p[0]).join("").substring(0, 2);
        avatar.textContent = initials;
      }

      // Update active item in dropdown
      document.querySelectorAll("#user-dropdown-list .dropdown-item").forEach(item => {
        if (item.getAttribute("data-email") === email) {
          item.classList.add("active");
        } else {
          item.classList.remove("active");
        }
      });

      if (notify) {
        this.showToast(`Switched active user: ${res.user.name} (${res.user.role})`, "info");
      }
    } catch (e) {
      console.error("Login failed:", e);
    }
  },

  bindCommandPalette() {
    const trigger = document.getElementById("global-search-trigger");
    const overlay = document.getElementById("command-palette-overlay");
    const input = document.getElementById("palette-search-input");
    const results = document.getElementById("palette-results");

    if (!trigger || !overlay || !input || !results) return;

    trigger.addEventListener("click", () => this.openCommandPalette());

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) this.closeCommandPalette();
    });

    input.addEventListener("input", () => {
      this.renderCommandResults(input.value.trim().toLowerCase());
    });
  },

  openCommandPalette() {
    const overlay = document.getElementById("command-palette-overlay");
    const input = document.getElementById("palette-search-input");
    if (!overlay || !input) return;

    overlay.classList.add("open");
    input.value = "";
    input.focus();
    this.renderCommandResults("");
  },

  closeCommandPalette() {
    const overlay = document.getElementById("command-palette-overlay");
    if (overlay) overlay.classList.remove("open");
  },

  async renderCommandResults(query) {
    const results = document.getElementById("palette-results");
    if (!results) return;

    if (!this.invoicesCache || this.invoicesCache.length === 0) {
      this.invoicesCache = await API.getInvoices().catch(() => []);
    }

    const defaultCommands = [
      { type: "view", title: "Go to Home", action: () => this.navigateTo("home") },
      { type: "view", title: "Go to Invoices", action: () => this.navigateTo("invoices") },
      { type: "view", title: "Go to Invoice Detail (Workbench)", action: () => this.navigateTo("workbench", "INV-2025-88419") },
      { type: "view", title: "Go to Disputes", action: () => this.navigateTo("disputes") },
      { type: "view", title: "Go to Payments", action: () => this.navigateTo("payments") },
      { type: "view", title: "Go to Carrier Scorecards", action: () => this.navigateTo("scorecards") },
      { type: "view", title: "Go to Activity Log", action: () => this.navigateTo("activity") },
      { type: "view", title: "Go to Settings", action: () => this.navigateTo("settings") },
      { type: "action", title: "Upload New Invoice", action: () => this.openUploadModal() }
    ];

    let items = [];
    if (!query) {
      items = defaultCommands;
    } else {
      items = defaultCommands.filter(c => c.title.toLowerCase().includes(query));
      
      // Match invoices
      this.invoicesCache.forEach(inv => {
        if (
          inv.invoice_number.toLowerCase().includes(query) ||
          inv.carrier_name.toLowerCase().includes(query) ||
          (inv.bol_number && inv.bol_number.toLowerCase().includes(query))
        ) {
          items.push({
            type: "invoice",
            title: `Invoice #${inv.invoice_number} — ${inv.carrier_name} ($${inv.total_billed_formatted})`,
            action: () => this.navigateTo("workbench", inv.id)
          });
        }
      });
    }

    if (items.length === 0) {
      results.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 13px;">No matching commands or invoices found.</div>`;
      return;
    }

    results.innerHTML = items.map((item, idx) => `
      <div class="palette-item ${idx === 0 ? 'active' : ''}" data-idx="${idx}">
        <span>${item.title}</span>
        <span class="badge badge-neutral" style="font-size: 10px;">${item.type.toUpperCase()}</span>
      </div>
    `).join("");

    results.querySelectorAll(".palette-item").forEach((el, idx) => {
      el.addEventListener("click", () => {
        this.closeCommandPalette();
        items[idx].action();
      });
    });
  },

  bindChatDrawer() {
    const toggleBtn = document.getElementById("btn-toggle-chat");
    const drawer = document.getElementById("chat-drawer");
    const closeBtn = document.getElementById("btn-close-chat");
    const sendBtn = document.getElementById("btn-send-chat");
    const input = document.getElementById("chat-input");

    if (toggleBtn && drawer) {
      toggleBtn.addEventListener("click", () => {
        drawer.classList.toggle("open");
        if (drawer.classList.contains("open") && input) input.focus();
      });
    }

    if (closeBtn && drawer) {
      closeBtn.addEventListener("click", () => drawer.classList.remove("open"));
    }

    if (sendBtn && input) {
      sendBtn.addEventListener("click", () => this.sendChatMessage());
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") this.sendChatMessage();
      });
    }
  },

  askSuggested(question) {
    const input = document.getElementById("chat-input");
    if (input) {
      input.value = question;
      this.sendChatMessage();
    }
  },

  async sendChatMessage() {
    const input = document.getElementById("chat-input");
    const container = document.getElementById("chat-messages");
    if (!input || !container) return;

    const query = input.value.trim();
    if (!query) return;

    // Append user bubble
    const userBubble = document.createElement("div");
    userBubble.className = "chat-bubble user";
    userBubble.textContent = query;
    container.appendChild(userBubble);

    input.value = "";
    container.scrollTop = container.scrollHeight;

    // Append typing assistant bubble
    const assistantBubble = document.createElement("div");
    assistantBubble.className = "chat-bubble assistant";
    assistantBubble.textContent = "Checking SQLite database and Master Agreement clauses...";
    container.appendChild(assistantBubble);
    container.scrollTop = container.scrollHeight;

    try {
      const res = await API.askFreightGuard(query);
      assistantBubble.innerHTML = `
        <div>${res.answer.replace(/\n/g, '<br>')}</div>
        <div style="margin-top: 8px; font-size: 11px; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 4px;">
          Grounded DB Response &bull; Engine: ${res._ai || 'Local Policy'}
        </div>
      `;
    } catch (e) {
      assistantBubble.textContent = `Error: ${e.message}`;
    }
    container.scrollTop = container.scrollHeight;
  },

  bindUploadModal() {
    const modal = document.getElementById("app-modal");
    const closeBtn = document.getElementById("modal-close-btn");
    if (closeBtn && modal) {
      closeBtn.addEventListener("click", () => this.closeModal());
      modal.addEventListener("click", (e) => {
        if (e.target === modal) this.closeModal();
      });
    }
  },

  openUploadModal() {
    this.openModal(
      "Upload Freight Invoice",
      `
      <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
        Ingest a carrier freight invoice (PDF or text). Linehaul base rates, fuel pegs, and accessorials are automatically parsed and audited against contract tariffs.
      </div>

      <div style="border: 2px dashed var(--border-medium); border-radius: var(--radius-md); padding: 24px; text-align: center; cursor: pointer; margin-bottom: 16px;" id="modal-dropzone" onclick="document.getElementById('modal-file-input').click()">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--accent-primary); margin-bottom: 8px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
        <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 2px;">Click to select or drag PDF file here</div>
        <div style="font-size: 11px; color: var(--text-muted);">Supports .pdf and .txt freight bills</div>
        <input type="file" id="modal-file-input" accept=".pdf,.txt" style="display:none;">
      </div>

      <div style="margin: 12px 0; text-align: center; color: var(--text-muted); font-size: 11px; font-weight: 700;">OR PASTE INVOICE TEXT</div>

      <div class="form-group" style="margin-bottom: 16px;">
        <textarea id="modal-paste-text" class="form-textarea mono" rows="5" style="width: 100%;" placeholder="INVOICE: INV-2025-99401&#10;CARRIER: Swift Line Logistics&#10;BASE FREIGHT: $2,850.00&#10;FUEL SURCHARGE: $342.00&#10;..."></textarea>
      </div>

      <div style="display: flex; justify-content: flex-end; gap: 10px;">
        <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
        <button class="btn btn-primary" id="btn-submit-upload" onclick="App.handleUploadSubmit()">
          Extract & Run Audit
        </button>
      </div>
      `
    );

    const dropzone = document.getElementById("modal-dropzone");
    const fileInput = document.getElementById("modal-file-input");
    if (dropzone && fileInput) {
      dropzone.ondragover = (e) => { e.preventDefault(); dropzone.style.borderColor = "var(--accent-primary)"; };
      dropzone.ondragleave = () => { dropzone.style.borderColor = "var(--border-medium)"; };
      dropzone.ondrop = (e) => {
        e.preventDefault();
        dropzone.style.borderColor = "var(--border-medium)";
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
      this.showToast("Please choose a file or paste invoice text.", "error");
      return;
    }

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Parsing & Auditing...";
    }

    try {
      this.showToast("Parsing invoice and evaluating contract tariff rules...", "info");
      const res = await API.uploadInvoice(formData);
      this.closeModal();
      this.showToast(`Extraction Complete: ${res.invoice.invoice_number} audited! Approved payable: $${res.audit.approved_payable_formatted}`, "success");
      this.invoicesCache = []; // invalidate
      await this.navigateTo("workbench", res.invoice.id);
    } catch (e) {
      this.showToast(`Upload failed: ${e.message}`, "error");
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Extract & Run Audit";
      }
    }
  },

  openModal(title, htmlBody) {
    const modal = document.getElementById("app-modal");
    const titleEl = document.getElementById("modal-title");
    const bodyEl = document.getElementById("modal-body");
    if (modal && titleEl && bodyEl) {
      titleEl.textContent = title;
      bodyEl.innerHTML = htmlBody;
      modal.classList.add("open");
    }
  },

  closeModal() {
    const modal = document.getElementById("app-modal");
    if (modal) modal.classList.remove("open");
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
      toast.style.transform = "translateY(8px)";
      toast.style.transition = "all 0.2s ease";
      setTimeout(() => toast.remove(), 250);
    }, 4000);
  },

  bindGlobalKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        this.openCommandPalette();
      } else if (e.key === "Escape") {
        this.closeCommandPalette();
        this.closeModal();
        const drawer = document.getElementById("chat-drawer");
        if (drawer) drawer.classList.remove("open");
      }
    });
  },

  async refreshStatusBadges() {
    try {
      const diag = await API.getSettings();
      const sidebarMode = document.getElementById("sidebar-mode-text");
      if (sidebarMode) {
        sidebarMode.textContent = diag.paypal.mode === "LIVE_SANDBOX" ? "Live Sandbox" : "Built-in Sandbox";
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

    // Update page title
    const titleEl = document.getElementById("current-view-title");
    if (titleEl) {
      titleEl.textContent = this.formatViewTitle(viewName);
    }

    // Trigger view-specific controllers
    switch (viewName) {
      case "home":
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
      case "payments":
        await SettlementView.init(entityId);
        break;
      case "scorecards":
        await ScorecardsView.init();
        break;
      case "activity":
        await AuditTrailView.init();
        break;
      case "settings":
        await SettingsView.init();
        break;
    }
  },

  formatViewTitle(viewName) {
    const map = {
      "home": "Home",
      "invoices": "Invoices",
      "workbench": "Invoice Detail & Evidence",
      "disputes": "Disputes",
      "payments": "Payments",
      "scorecards": "Carrier Scorecards",
      "activity": "Activity",
      "settings": "Settings"
    };
    return map[viewName] || "Home";
  },

  async quickAudit(invoiceId) {
    try {
      const res = await API.runAudit(invoiceId);
      this.showToast(res.summary_message, res.disputed_amount_cents > 0 ? "warning" : "success");
      
      if (this.currentView === "home") {
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

  getAuditStatusBadge(status) {
    switch (status) {
      case "AUDITED_CLEAN":
        return `<span class="badge badge-clean">Audited Clean</span>`;
      case "AUDITED_DISCREPANCY":
        return `<span class="badge badge-discrepancy">Discrepancy</span>`;
      case "PENDING_AUDIT":
        return `<span class="badge badge-warning">Needs Review</span>`;
      case "DISPUTED":
        return `<span class="badge badge-warning">Disputed</span>`;
      case "BLOCKED":
        return `<span class="badge badge-danger">Blocked</span>`;
      default:
        return `<span class="badge badge-neutral">${status}</span>`;
    }
  },

  getSettlementStatusBadge(status) {
    switch (status) {
      case "RECONCILED":
        return `<span class="badge badge-clean">Reconciled</span>`;
      case "PAYOUT_SUCCESS":
      case "PAYOUT_INITIATED":
        return `<span class="badge badge-purple">Paid</span>`;
      case "PARTIALLY_SETTLED_HELD":
        return `<span class="badge badge-info">Split Settled</span>`;
      case "AUTHORIZED":
        return `<span class="badge badge-clean">Authorized</span>`;
      case "UNSETTLED":
        return `<span class="badge badge-neutral">Unsettled</span>`;
      case "PAYOUT_FAILED":
        return `<span class="badge badge-danger">Failed</span>`;
      default:
        return `<span class="badge badge-neutral">${status}</span>`;
    }
  }
};

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  App.init();
});
