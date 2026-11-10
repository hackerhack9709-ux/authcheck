/* =========================================================================
   Gateway — payment verification adapter for PayCheck.

   Two modes:
     sandbox : deterministic local simulator, works fully offline
     live    : POSTs to a user-supplied verification endpoint (a real
               payment gateway, PSP dashboard API, or bank webhook) and
               normalises whatever it returns.

   No credentials ship with this app. In live mode the merchant enters their
   own endpoint + API key, stored only in this browser.
   ========================================================================= */
(() => {
  'use strict';

  const K_CFG = 'paycheck.gateway';

  const DEFAULTS = {
    provider: 'generic',  // 'generic' | 'razorpay'
    mode: 'sandbox',      // 'sandbox' | 'live'
    endpoint: '',         // https://api.example.com/v1/payments/verify
    apiKey: '',           // Bearer token / secret / Basic user
    apiSecret: '',        // Basic password (Razorpay key_secret)
    authStyle: 'bearer',  // 'bearer' | 'x-api-key' | 'query' | 'basic'
    timeoutMs: 12000,
    autoCheck: true       // run gateway check automatically on the Verify tab
  };

  /* Known provider presets. Razorpay's API needs the *secret* key, which must
     never live in a browser — so the preset points at your own proxy, and the
     proxy holds the secret. See server/razorpay-verify.js. */
  const PRESETS = {
    generic: {
      endpoint: '', authStyle: 'bearer',
      hint: 'Any endpoint that accepts a JSON POST and returns a status.'
    },
    razorpay: {
      endpoint: 'https://YOUR-PROXY.example.com/api/razorpay/verify',
      authStyle: 'basic',
      hint: 'Your proxy URL. The proxy holds the Razorpay key_secret; the browser never sees it.'
    }
  };

  const key = (userId) => `${K_CFG}.${userId || 'anon'}`;

  const Gateway = {
    getConfig(userId) {
      try { return { ...DEFAULTS, ...(JSON.parse(localStorage.getItem(key(userId))) || {}) }; }
      catch { return { ...DEFAULTS }; }
    },
    setConfig(userId, patch) {
      const next = { ...this.getConfig(userId), ...patch };
      localStorage.setItem(key(userId), JSON.stringify(next));
      return next;
    },
    reset(userId) { localStorage.removeItem(key(userId)); return { ...DEFAULTS }; },
    presets() { return PRESETS; },

    /* ------------------- Razorpay payload normalisation ------------------ */
    /* Razorpay payment objects: { status: 'captured'|'authorized'|'created'|
       'failed', amount (paise), currency, method, bank, acquirer_data.{rrn,utr},
       notes, email, contact, order_id, ... } */
    _fromRazorpay(raw) {
      const p = raw && (raw.payment || raw.data || raw);
      if (!p || typeof p !== 'object') return raw;
      const acquirer = p.acquirer_data || {};
      return {
        status: p.status || p.error_description || '',
        referenceId: p.id || '',
        orderId: p.order_id || '',
        utr: acquirer.rrn || acquirer.utr || '',
        payerName: (p.notes && (p.notes.name || p.notes.payer_name)) || '',
        payerVpa: p.vpa || (p.notes && p.notes.vpa) || '',
        payerEmail: p.email || '',
        payerContact: p.contact || '',
        // Razorpay amounts are in paise.
        amount: p.amount != null ? Number(p.amount) / 100 : null,
        currency: p.currency || 'INR',
        method: p.method || '',
        bank: p.bank || acquirer.bank_transaction_id || '',
        fee: p.fee != null ? Number(p.fee) / 100 : null,
        tax: p.tax != null ? Number(p.tax) / 100 : null,
        netAmount: p.amount != null && p.fee != null ? (Number(p.amount) - Number(p.fee) - Number(p.tax || 0)) / 100 : null,
        captured: !!p.captured,
        at: p.created_at ? new Date(Number(p.created_at) * 1000).toISOString() : new Date().toISOString(),
        raw: p
      };
    },

    /* ------------------------- response mapping ------------------------ */
    /** Pull a status out of whatever shape the endpoint returns. */
    normaliseStatus(raw) {
      const v = String(
        raw.status ?? raw.state ?? raw.paymentStatus ?? raw.txnStatus ??
        raw.result ?? raw.code ?? raw.responseCode ?? ''
      ).toUpperCase();
      if (!v) return null;
      if (/(SUCCESS|SUCCEEDED|COMPLETED|CAPTURED|PAID|SETTLED|00$|^0$|^000$|OK$)/.test(v)) return 'SUCCESS';
      if (/(PENDING|PROCESSING|INITIATED|AWAITED|IN_PROGRESS|CREATED|AUTHORIZED|AUTHORISED)/.test(v)) return 'PENDING';
      if (/(FAIL|DECLINED|ERROR|CANCELLED|CANCELED|REJECT|TIMEOUT|EXPIRED)/.test(v)) return 'FAILED';
      if (/(NOT_?FOUND|NO_?RECORD|MISSING|UNKNOWN)/.test(v)) return 'NOT_FOUND';
      return null;
    },

    /** Best-effort extraction of the useful fields from an arbitrary payload. */
    pick(raw, ...names) {
      for (const n of names) {
        const parts = n.split('.');
        let cur = raw;
        for (const p of parts) { if (cur == null || typeof cur !== 'object') { cur = undefined; break; } cur = cur[p]; }
        if (cur != null && cur !== '') return cur;
      }
      return null;
    },

    toResult(raw) {
      const status = this.normaliseStatus(raw) || 'UNKNOWN';
      const amount = Number(this.pick(raw, 'amount', 'txnAmount', 'data.amount', 'transaction.amount') || 0) || null;
      return {
        status,
        ref: String(this.pick(raw, 'referenceId', 'reference', 'refId', 'rrn', 'utr', 'txnId', 'transactionId', 'data.referenceId') || ''),
        utr: String(this.pick(raw, 'utr', 'rrn', 'bankRrn', 'data.utr') || ''),
        payerName: String(this.pick(raw, 'payerName', 'payer.name', 'senderName', 'customerName', 'data.payerName') || ''),
        payerVpa: String(this.pick(raw, 'payerVpa', 'payer.vpa', 'senderVpa', 'data.payerVpa') || ''),
        amount,
        method: String(this.pick(raw, 'method', 'paymentMethod', 'instrument', 'mode') || ''),
        bank: String(this.pick(raw, 'bank', 'payerBank', 'issuerBank', 'data.bank') || ''),
        at: String(this.pick(raw, 'timestamp', 'createdAt', 'paidAt', 'txnDate', 'data.timestamp') || new Date().toISOString()),
        raw
      };
    },

    /* ---------------------------- sandbox ------------------------------ */
    _sandbox(input) {
      const amt = Number(input.amount || 0);
      const name = String(input.payee || '').trim();
      const utr = String(input.utr || '').trim();
      let h = 0; for (const c of name + amt + utr) h = (h * 31 + c.charCodeAt(0)) % 1000;

      let status;
      if (!name && !input.vpa) status = 'NOT_FOUND';
      else if (!/^\d{12}$/.test(utr)) status = utr ? 'FAILED' : 'PENDING';
      else if (amt > 0 && amt % 100 === 0 && h % 3 === 0) status = 'PENDING';
      else if (h % 11 === 0) status = 'FAILED';
      else status = 'SUCCESS';

      const banks = ['HDFC Bank', 'ICICI Bank', 'State Bank of India', 'Axis Bank', 'Kotak Mahindra Bank'];
      return {
        status,
        referenceId: 'PAY' + String(1000000000 + h * 7919).slice(0, 12),
        utr: utr || (status === 'SUCCESS' ? String(402730210000 + (h % 99999)) : ''),
        payerName: name || 'Unknown payer',
        payerVpa: input.vpa || (name ? name.toLowerCase().replace(/\s+/g, '') + '@okaxis' : ''),
        amount: amt || null,
        method: input.method || 'UPI',
        bank: banks[h % banks.length],
        timestamp: new Date().toISOString(),
        sandbox: true
      };
    },

    /* ------------------------------ live ------------------------------- */
    /* Build the request for the chosen provider.
       Razorpay: the proxy exposes GET /api/razorpay/verify/:paymentId (or
       accepts {paymentId}). We pass the payment id (UTR field) so the proxy
       can fetch the real payment from Razorpay and return it. */
    _buildRequest(input, cfg) {
      const base = {
        payee: input.payee || '',
        vpa: input.vpa || '',
        amount: Number(input.amount || 0),
        utr: input.utr || '',
        date: input.date || new Date().toISOString().slice(0, 10)
      };

      if (cfg.provider === 'razorpay') {
        // The UTR box doubles as the Razorpay payment id (pay_XXXXXXXXXXXX).
        const paymentId = String(input.utr || '').trim();
        const url = cfg.endpoint.replace(/\/+$/, '') + '/' + encodeURIComponent(paymentId);
        return { url, body: null, extra: { 'X-Razorpay-Key-Id': cfg.apiKey || '' } };
      }

      return { url: cfg.endpoint, body: base, extra: {} };
    },

    async _live(input, cfg) {
      const { url: baseUrl, body, extra } = this._buildRequest(input, cfg);
      let url = baseUrl;
      const headers = { 'Content-Type': 'application/json', ...extra };
      if (cfg.authStyle === 'bearer') headers.Authorization = 'Bearer ' + cfg.apiKey;
      else if (cfg.authStyle === 'x-api-key') headers['x-api-key'] = cfg.apiKey;
      else if (cfg.authStyle === 'basic') {
        // Basic auth against YOUR proxy, so the proxy can gate access.
        headers.Authorization = 'Basic ' + btoa((cfg.apiKey || '') + ':' + (cfg.apiSecret || ''));
      } else if (cfg.authStyle === 'query' && cfg.apiKey) {
        url += (url.includes('?') ? '&' : '?') + 'key=' + encodeURIComponent(cfg.apiKey);
      }

      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), cfg.timeoutMs || 12000);
      let res, text;
      try {
        res = await fetch(url, {
          method: body ? 'POST' : 'GET',
          headers,
          body: body ? JSON.stringify(body) : undefined,
          signal: ctrl.signal
        });
        text = await res.text();
      } catch (e) {
        clearTimeout(timer);
        if (e.name === 'AbortError') throw new Error('Gateway timed out after ' + (cfg.timeoutMs / 1000) + 's.');
        throw new Error('Could not reach gateway: ' + e.message);
      }
      clearTimeout(timer);

      let raw;
      try { raw = JSON.parse(text); } catch { raw = { status: res.ok ? 'SUCCESS' : 'FAILED', message: text.slice(0, 300) }; }
      if (!res.ok && !this.normaliseStatus(raw)) {
        throw new Error('Gateway returned HTTP ' + res.status + '. ' + (raw.message || raw.error_description || ''));
      }
      return raw;
    },

    /* ----------------------------- public ------------------------------ */
    async verify(input, userId) {
      const cfg = this.getConfig(userId);
      if (cfg.mode === 'live') {
        if (!/^https?:\/\//.test(cfg.endpoint || '')) {
          throw new Error('Set a valid verification endpoint URL in Settings first.');
        }
        if (cfg.provider === 'razorpay' && !String(input.utr || '').trim()) {
          throw new Error('Razorpay mode needs the payment id (pay_…) in the UTR box.');
        }
        const raw = await this._live(input, cfg);
        const mapped = cfg.provider === 'razorpay' ? this._fromRazorpay(raw) : raw;
        return { ...this.toResult(mapped), mode: 'live', provider: cfg.provider };
      }
      // sandbox: simulate network latency so the UI state is realistic
      await new Promise((r) => setTimeout(r, 550 + Math.random() * 700));
      return { ...this._sandbox(input), mode: 'sandbox', provider: 'sandbox' };
    }
  };

  window.Gateway = Gateway;
})();
