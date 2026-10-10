/**
 * FreightGuard API Client Wrapper
 * Handles backend REST requests, JSON serialization, and error propagation.
 */
const API = {
  async get(url) {
    try {
      const res = await fetch(url);
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
        headers: { "Content-Type": "application/json" },
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

  // Endpoints
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
  getDisputes: () => API.get("/api/disputes"),
  generateDispute: (invoiceId, notes) => API.post("/api/disputes/generate", { invoice_id: invoiceId, custom_message_notes: notes }),
  updateDisputeStatus: (disputeId, status, creditRef) => {
    let url = `/api/disputes/${encodeURIComponent(disputeId)}/status?new_status=${encodeURIComponent(status)}`;
    if (creditRef) url += `&credit_note_ref=${encodeURIComponent(creditRef)}`;
    return API.post(url);
  },
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
  getAuditEvents: () => API.get("/api/audit-events"),
  getSettings: () => API.get("/api/settings"),
  resetDemoData: () => API.post("/api/settings/reset-demo")
};
