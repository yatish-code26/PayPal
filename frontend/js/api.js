/**
 * FreightGuard API Client Wrapper
 * Handles backend REST requests, JSON serialization, auth headers, and error propagation.
 */
const API = {
  getAuthToken() {
    return localStorage.getItem("fg_auth_token") || "";
  },

  setAuthToken(token) {
    if (token) {
      localStorage.setItem("fg_auth_token", token);
    } else {
      localStorage.removeItem("fg_auth_token");
    }
  },

  getHeaders(extraHeaders = {}) {
    const headers = { ...extraHeaders };
    const token = this.getAuthToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  },

  async get(url) {
    try {
      const res = await fetch(url, {
        headers: this.getHeaders()
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (e) {
      console.error(`API GET ${url} failed:`, e);
      throw e;
    }
  },

  async post(url, data = {}) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: this.getHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(data)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (e) {
      console.error(`API POST ${url} failed:`, e);
      throw e;
    }
  },

  async uploadFile(url, formData) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: this.getHeaders(), // do not set Content-Type so browser sets boundary
        body: formData
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (e) {
      console.error(`API upload ${url} failed:`, e);
      throw e;
    }
  },

  // Auth & Roles
  getDemoUsers: () => API.get("/api/auth/demo-users"),
  login: (email) => API.post("/api/auth/login", { email }),
  getMe: () => API.get("/api/auth/me"),

  // Stats & Invoices
  getStats: () => API.get("/api/stats"),
  getInvoices: (status, carrier, q) => {
    let url = "/api/invoices?";
    if (status) url += `status=${encodeURIComponent(status)}&`;
    if (carrier) url += `carrier_id=${encodeURIComponent(carrier)}&`;
    if (q) url += `q=${encodeURIComponent(q)}&`;
    return API.get(url);
  },
  getInvoiceDetails: (id) => API.get(`/api/invoices/${encodeURIComponent(id)}`),
  runAudit: (id) => API.post(`/api/invoices/${encodeURIComponent(id)}/audit`),
  getWorkbench: (id) => API.get(`/api/invoices/${encodeURIComponent(id)}/evidence`),
  uploadInvoice: (formData) => API.uploadFile("/api/invoices/upload", formData),

  // AI Inference & Explanations
  getAiExplanation: (id) => API.get(`/api/ai/explain/${encodeURIComponent(id)}`),
  getAiProvider: () => API.get("/api/ai/provider"),

  // Disputes
  getDisputes: () => API.get("/api/disputes"),
  generateDispute: (invoiceId, notes) => API.post("/api/disputes/generate", { invoice_id: invoiceId, custom_message_notes: notes }),
  updateDisputeStatus: (disputeId, status, creditRef) => {
    let url = `/api/disputes/${encodeURIComponent(disputeId)}/status?new_status=${encodeURIComponent(status)}`;
    if (creditRef) url += `&credit_note_ref=${encodeURIComponent(creditRef)}`;
    return API.post(url);
  },

  // Settlements & PayPal Payouts
  authorizeSettlement: (invoiceId, approver1, approver2, notes) => 
    API.post("/api/settlements/authorize", {
      invoice_id: invoiceId,
      first_approver: approver1,
      second_approver: approver2,
      notes: notes
    }),
  executePayout: (invoiceId, idempotencyKey, approver1, approver2) =>
    API.post("/api/settlements/payout", {
      invoice_id: invoiceId,
      idempotency_key: idempotencyKey,
      first_approver: approver1,
      second_approver: approver2
    }),
  simulateWebhook: (eventType, payoutItemId, payoutBatchId) =>
    API.post("/api/webhooks/simulate", {
      event_type: eventType,
      payout_item_id: payoutItemId,
      payout_batch_id: payoutBatchId
    }),

  // Logs & Settings
  getAuditEvents: () => API.get("/api/audit-events"),
  getSettings: () => API.get("/api/settings"),
  updateSettings: (payload) => API.post("/api/settings", payload),
  testConnection: () => API.post("/api/settings/test-connection"),
  resetDemoData: () => API.post("/api/settings/reset-demo")
};
