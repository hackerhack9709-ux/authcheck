/* =========================================================================
   PayCheck (पेचेक) — UPI payment verification helper
   Inspired by an anti-fraud reel: "Payment pehle check kare, phir maal de"
   Pure vanilla JS, no build step. Data persists in localStorage.
   ========================================================================= */
(() => {
  'use strict';

  const STORE_TX = 'paycheck.txns.v1';
  const STORE_LANG = 'paycheck.lang.v1';

  /* ----------------------------- i18n ---------------------------------- */
  const I18N = {
    hi: {
      appName: 'पेचेक', tagline: 'UPI भुगतान जाँच',
      tabTx: 'लेन-देन', tabAdd: 'जोड़ें', tabVerify: 'जाँचें', tabQr: 'QR',
      bannerTitle: 'ऑनलाइन धोखाधड़ी से सावधान',
      bannerText: 'पैसा पहले जाँचें, फिर सामान दें। स्क्रीनशॉट पर भरोसा न करें — बैंक ऐप में खुद देखें।',
      totalReceived: 'इस महीने कुल प्राप्त',
      txnCount: 'लेन-देन', success: 'सफल', pending: 'प्रतीक्षित',
      searchPh: 'नाम, UPI ID, रकम या UTR खोजें…',
      all: 'सभी', dateFilter: 'तारीख़', methodFilter: 'तरीक़ा', statusFilter: 'स्थिति',
      anyDate: 'कोई भी तारीख़', anyMethod: 'कोई भी तरीक़ा', anyStatus: 'कोई भी स्थिति',
      noTxns: 'कोई लेन-देन नहीं मिला।',
      addTitle: 'नया भुगतान जोड़ें',
      fPayee: 'भुगतानकर्ता / व्यक्ति का नाम', fPayeePh: 'जैसे: Saif Sayeed',
      fVpa: 'UPI ID (भुगतानकर्ता)', fVpaPh: 'name@bank',
      fAmount: 'रकम (₹)', fMethod: 'तरीक़ा', fStatus: 'स्थिति', fDate: 'तारीख़',
      fUtr: 'UTR / संदर्भ नंबर (12 अंक)', fUtrPh: 'जैसे: 402730210114',
      fNote: 'नोट (वैकल्पिक)',
      save: 'सहेजें', saved: 'लेन-देन सहेजा गया', invalidAmount: 'सही रकम डालें',
      invalidName: 'नाम भरें',
      verifyTitle: 'भुगतान की जाँच करें',
      verifyIntro: 'सामान देने से पहले यह फॉर्म भरें। ऐप जोखिम की जाँच करके बताएगा कि भुगतान सुरक्षित है या नहीं।',
      vPayee: 'किसको भुगतान? (नाम या UPI ID)', vPayeePh: 'Saif Sayeed / saif@okaxis',
      vAmount: 'कितनी रकम? (₹)', vUtr: 'UTR नंबर (यदि मिला हो)',
      check: 'जाँचें', safe: 'सुरक्षित — सामान दे सकते हैं',
      caution: 'सावधानी बरतें', danger: 'खतरा — सामान न दें',
      checks: 'जाँच के नतीजे',
      addPaymentBtn: 'इस भुगतान को रिकॉर्ड में जोड़ें',
      qrTitle: 'भुगतान लें (QR)',
      qrIntro: 'अपना UPI ID और रकम डालें — ग्राहक QR स्कैन करके भुगतान करेगा।',
      qrPayeeName: 'व्यापारी / आपका नाम', qrVpa: 'आपका UPI ID', qrAmount: 'रकम (₹)',
      qrNote: 'नोट', generate: 'QR बनाएँ',
      upiLink: 'UPI लिंक',
      detail: 'लेन-देन विवरण', close: 'बंद करें', delete: '🗑 हटाएँ',
      deleted: 'हटा दिया गया', reset: 'डेमो डेटा बहाल',
      status: { success: 'सफल', pending: 'प्रतीक्षित', failed: 'असफल' },
      res: {
        format_bad: 'UPI ID का प्रारूप ग़लत है',
        format_ok: 'UPI ID सही प्रारूप में है',
        known_payee: 'इस व्यक्ति से पहले भी सफल भुगतान मिला है',
        new_payee: 'यह नया भुगतानकर्ता है — पहली बार लेन-देन',
        dup_amount: 'कुछ मिनट पहले ही इतनी ही रकम मिली है — दोहराव हो सकता है',
        large_amount: 'रकम बड़ी है — बैंक ऐप में खुद पुष्टि करें',
        round_amount: 'गोल रकम है — फ़र्ज़ी स्क्रीनशॉट आम हैं',
        utr_bad: 'UTR नंबर 12 अंकों का होना चाहिए',
        utr_ok: 'UTR नंबर का प्रारूप सही है',
        utr_missing: 'UTR नंबर नहीं दिया गया — बैंक ऐप में जाँचें',
        past_fail: 'इस व्यक्ति का पहले का भुगतान असफल रहा था',
        unsupported: 'यह QR/भुगतान “Unsupported” के रूप में दर्ज है',
        unsaved: 'यह भुगतान आपके रिकॉर्ड में नहीं है',
        advice_safe: 'रिकॉर्ड में भुगतान मिल गया। बैंक ऐप में रकम जमा दिख रही हो तो सामान दे सकते हैं।',
        advice_caution: 'भुगतान पूरी तरह पक्का नहीं है। बैंक ऐप खोलकर रकम जमा होने की पुष्टि करें, तब सामान दें।',
        advice_danger: 'भुगतान सत्यापित नहीं हुआ। कृपया सामान न दें और भुगतान दोबारा जाँचें।'
      }
    },
    en: {
      appName: 'PayCheck', tagline: 'UPI payment verifier',
      tabTx: 'Transactions', tabAdd: 'Add', tabVerify: 'Verify', tabQr: 'QR',
      bannerTitle: 'Beware of online fraud',
      bannerText: 'Check the money first, then hand over the goods. Never trust a screenshot — confirm inside your bank app.',
      totalReceived: 'Received this month',
      txnCount: 'Transactions', success: 'Successful', pending: 'Pending',
      searchPh: 'Search name, UPI ID, amount or UTR…',
      all: 'All', dateFilter: 'Date', methodFilter: 'Method', statusFilter: 'Status',
      anyDate: 'Any date', anyMethod: 'Any method', anyStatus: 'Any status',
      noTxns: 'No transactions found.',
      addTitle: 'Add a new payment',
      fPayee: 'Payer / person name', fPayeePh: 'e.g. Saif Sayeed',
      fVpa: 'UPI ID (payer)', fVpaPh: 'name@bank',
      fAmount: 'Amount (₹)', fMethod: 'Method', fStatus: 'Status', fDate: 'Date',
      fUtr: 'UTR / reference no. (12 digits)', fUtrPh: 'e.g. 402730210114',
      fNote: 'Note (optional)',
      save: 'Save', saved: 'Transaction saved', invalidAmount: 'Enter a valid amount',
      invalidName: 'Enter a name',
      verifyTitle: 'Verify a payment',
      verifyIntro: 'Fill this in before handing over goods. The app scores the risk and tells you whether it is safe.',
      vPayee: 'Paid by whom? (name or UPI ID)', vPayeePh: 'Saif Sayeed / saif@okaxis',
      vAmount: 'How much? (₹)', vUtr: 'UTR number (if available)',
      check: 'Check', safe: 'Safe — you can hand over the goods',
      caution: 'Be careful', danger: 'Danger — do not hand over the goods',
      checks: 'Check results',
      addPaymentBtn: 'Add this payment to records',
      qrTitle: 'Collect a payment (QR)',
      qrIntro: 'Enter your UPI ID and amount — the customer scans the QR and pays.',
      qrPayeeName: 'Merchant / your name', qrVpa: 'Your UPI ID', qrAmount: 'Amount (₹)',
      qrNote: 'Note', generate: 'Generate QR',
      upiLink: 'UPI link',
      detail: 'Transaction detail', close: 'Close', delete: '🗑 Delete',
      deleted: 'Deleted', reset: 'Demo data restored',
      status: { success: 'Success', pending: 'Pending', failed: 'Failed' },
      res: {
        format_bad: 'UPI ID format is invalid',
        format_ok: 'UPI ID format looks valid',
        known_payee: 'You have received a successful payment from this person before',
        new_payee: 'This is a new payer — first-time transaction',
        dup_amount: 'The same amount arrived a few minutes ago — possible duplicate',
        large_amount: 'Large amount — confirm it yourself in the bank app',
        round_amount: 'Round amount — fake screenshots are common',
        utr_bad: 'UTR number must be 12 digits',
        utr_ok: 'UTR number format is valid',
        utr_missing: 'No UTR given — confirm inside the bank app',
        past_fail: 'A previous payment from this person had failed',
        unsupported: 'This QR/payment is recorded as “Unsupported”',
        unsaved: 'This payment is not in your records',
        advice_safe: 'Payment found in your records. If your bank app shows the credit, you may hand over the goods.',
        advice_caution: 'The payment is not fully confirmed. Open your bank app and confirm the credit before handing over goods.',
        advice_danger: 'Payment could not be verified. Do not hand over the goods and re-check the payment.'
      }
    }
  };

  /* --------------------------- utilities ------------------------------- */
  const $ = (s, r = document) => r.querySelector(s);
  const el = (tag, cls, html) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  };
  const inr = (n) => '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));

  const VPA_RE = /^[a-zA-Z0-9][a-zA-Z0-9.\-_]{1,255}@[a-zA-Z]{2,64}$/;

  /* ----------------------------- state --------------------------------- */
  const state = {
    lang: localStorage.getItem(STORE_LANG) || 'hi',
    tab: 'tx',
    q: '',
    date: '', method: '', status: '',
    txns: [],
    verifyDraft: null,
    qr: null
  };

  const T = () => I18N[state.lang];

  /* --------------------------- seed data ------------------------------- */
  const METHODS = ['Google Pay', 'PhonePe', 'Paytm', 'UPI QR', 'Bank Transfer'];

  function seed() {
    const mk = (payee, amount, method, status, day, time, vpa, utr) => ({
      id: 'tx_' + Math.random().toString(36).slice(2, 10),
      payee, amount, method, status, day, time, vpa: vpa || '', utr: utr || '', note: ''
    });
    return [
      mk('Snapdeal Private Limited', 630.0, 'UPI QR', 'success', '10 November', '10:12', 'snapdeal@icici', '402730210114'),
      mk('Google Pay Merchant', 1450.0, 'Google Pay', 'success', '10 November', '10:41', 'merchant@okaxis', '402730210115'),
      mk('Saif Sayeed', 2000.0, 'PhonePe', 'success', '10 November', '11:05', 'saif@ybl', '402730210116'),
      mk('Phonepemerchant', 40.0, 'PhonePe', 'success', '10 November', '11:32', 'phonepemerchant@ybl', ''),
      mk('Samreen', 1450.0, 'UPI QR', 'success', '10 November', '12:02', 'samreen@paytm', '402730210117'),
      mk('Nadeem Sarwar', 200.0, 'Paytm', 'success', '11 November', '09:47', 'nadeem@paytm', '402730210118'),
      mk('Akash Kanaujlya', 30.0, 'UPI QR', 'success', '11 November', '10:15', 'akash@okhdfcbank', ''),
      mk('Unsupported QR Code', 100.0, 'UPI QR', 'failed', '11 November', '10:52', '', ''),
      mk('Prince', 450.0, 'Google Pay', 'success', '11 November', '12:20', 'prince@okicici', '402730210119'),
      mk('Paytm', 850.0, 'Paytm', 'success', '11 November', '13:11', 'paytm@paytm', '402730210120'),
      mk('Rizwan', 160.0, 'UPI QR', 'pending', '12 November', '15:26', 'rizwan@ybl', ''),
      mk('Mohammad Shariq', 2500.0, 'Bank Transfer', 'pending', '12 November', '16:03', 'shariq@okaxis', ''),
      mk('Gurjan Sharma', 58.0, 'PhonePe', 'success', '13 November', '18:38', 'gurjan@ybl', '402730210121')
    ];
  }

  function load() {
    try {
      const raw = localStorage.getItem(STORE_TX);
      state.txns = raw ? JSON.parse(raw) : seed();
    } catch { state.txns = seed(); }
  }
  const save = () => localStorage.setItem(STORE_TX, JSON.stringify(state.txns));

  /* --------------------------- derivation ------------------------------ */
  const AV_COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444', '#6366f1'];
  const avatarColor = (s) => {
    let h = 0; for (const ch of String(s)) h = (h * 31 + ch.charCodeAt(0)) % 997;
    return AV_COLORS[h % AV_COLORS.length];
  };
  const initials = (s) => String(s || '?').trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase();

  function totals() {
    const ok = state.txns.filter((t) => t.status === 'success');
    return {
      amount: ok.reduce((a, t) => a + Number(t.amount || 0), 0),
      count: state.txns.length,
      success: ok.length,
      pending: state.txns.filter((t) => t.status === 'pending').length
    };
  }

  function filtered() {
    const q = state.q.trim().toLowerCase();
    return state.txns.filter((t) => {
      if (state.date && t.day !== state.date) return false;
      if (state.method && t.method !== state.method) return false;
      if (state.status && t.status !== state.status) return false;
      if (!q) return true;
      return [t.payee, t.vpa, t.utr, String(t.amount), t.note]
        .some((v) => String(v || '').toLowerCase().includes(q));
    });
  }

  /* --------------------------- shared UI ------------------------------- */
  function toast(msg) {
    const t = $('#toast');
    t.textContent = msg; t.classList.add('show');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove('show'), 2200);
  }

  function statusBadge(s) {
    const map = { success: 'ok', pending: 'pend', failed: 'bad' };
    return `<span class="badge ${map[s] || 'pend'}">${esc(T().status[s] || s)}</span>`;
  }

  /* ------------------------- view: transactions ------------------------ */
  function viewTx() {
    const v = el('div');
    const tot = totals();
    const days = [...new Set(state.txns.map((t) => t.day))];

    v.appendChild(el('div', 'banner',
      `<span class="em">⚠️</span><div><strong>${esc(T().bannerTitle)}</strong>
       <p>${esc(T().bannerText)}</p></div>`));

    const sum = el('div', 'summary',
      `<div class="label">${esc(T().totalReceived)}</div>
       <div class="amount">${inr(tot.amount).replace('.00', '')}</div>
       <div class="summary-grid">
         <div class="cell"><b>${tot.count}</b><span>${esc(T().txnCount)}</span></div>
         <div class="cell"><b style="color:#4ade80">${tot.success}</b><span>${esc(T().success)}</span></div>
         <div class="cell"><b style="color:#fbbf24">${tot.pending}</b><span>${esc(T().pending)}</span></div>
       </div>`);
    v.appendChild(sum);

    const search = el('div', 'search',
      `<span class="ico">🔍</span><input id="q" placeholder="${esc(T().searchPh)}" value="${esc(state.q)}">`);
    const qInput = $('#q', search);
    qInput.oninput = () => {
      state.q = qInput.value;
      const list = $('#txn-list', v);
      if (list) list.replaceWith(txnList());
    };
    v.appendChild(search);

    const chips = el('div', 'chips');
    const addChip = (label, on, fn) => {
      const c = el('button', 'chip' + (on ? ' on' : ''), esc(label));
      c.type = 'button'; c.onclick = fn; chips.appendChild(c);
    };
    addChip(T().all, !state.status, () => { state.status = ''; render(); });
    ['success', 'pending', 'failed'].forEach((s) =>
      addChip(T().status[s], state.status === s, () => { state.status = state.status === s ? '' : s; render(); }));
    addChip('▦ ' + T().methodFilter, !!state.method, () => pickMethod());
    addChip('📅 ' + (state.date || T().dateFilter), !!state.date, () => pickDate(days));
    if (state.method || state.date) addChip('✕ ' + T().all, false, () => { state.method = ''; state.date = ''; render(); });
    v.appendChild(chips);

    v.appendChild(txnList());
    return v;
  }

  function txnList() {
    const wrap = el('div');
    wrap.id = 'txn-list';
    const list = filtered();
    if (!list.length) { wrap.appendChild(el('div', 'empty', esc(T().noTxns))); return wrap; }

    const groups = new Map();
    list.forEach((t) => { if (!groups.has(t.day)) groups.set(t.day, []); groups.get(t.day).push(t); });

    for (const [day, items] of groups) {
      const dayTotal = items.filter((t) => t.status === 'success')
        .reduce((a, t) => a + Number(t.amount), 0);
      const g = el('div', 'day-group');
      g.appendChild(el('div', 'day-head', `<span>${esc(day)}</span><b>${inr(dayTotal).replace('.00', '')}</b>`));
      items.forEach((t) => {
        const row = el('div', 'txn',
          `<div class="av" style="background:${avatarColor(t.payee)}">${esc(initials(t.payee))}</div>
           <div class="mid">
             <div class="name">${esc(t.payee)}</div>
             <div class="sub">${esc(t.method)}${t.vpa ? ' · ' + esc(t.vpa) : ''}</div>
           </div>
           <div class="right">
             <div class="amt cr">${inr(t.amount)}</div>
             <div class="time">${esc(t.time)}</div>
             ${statusBadge(t.status)}
           </div>`);
        row.onclick = () => openDetail(t);
        g.appendChild(row);
      });
      wrap.appendChild(g);
    }
    return wrap;
  }

  function pickMethod() {
    const opts = [T().anyMethod, ...METHODS];
    const cur = state.method || opts[0];
    const next = opts[(opts.indexOf(cur) + 1) % opts.length] || opts[0];
    state.method = next === T().anyMethod ? '' : next;
    render();
  }
  function pickDate(days) {
    const opts = [T().anyDate, ...days];
    const cur = state.date || opts[0];
    const next = opts[(opts.indexOf(cur) + 1) % opts.length] || opts[0];
    state.date = next === T().anyDate ? '' : next;
    render();
  }

  function openDetail(t) {
    const m = el('div', 'modal show');
    m.innerHTML =
      `<div class="modal-card">
         <button class="close" type="button">✕</button>
         <h3>${esc(T().detail)}</h3>
         <div class="result ok" style="margin-top:0">
           <div class="kv"><span>${esc(T().fPayee)}</span><span>${esc(t.payee)}</span></div>
           <div class="kv"><span>${esc(T().fAmount)}</span><span>${inr(t.amount)}</span></div>
           <div class="kv"><span>${esc(T().fMethod)}</span><span>${esc(t.method)}</span></div>
           <div class="kv"><span>${esc(T().fStatus)}</span><span>${esc(T().status[t.status] || t.status)}</span></div>
           <div class="kv"><span>${esc(T().fDate)}</span><span>${esc(t.day)} ${esc(t.time)}</span></div>
           <div class="kv"><span>${esc(T().fVpa)}</span><span>${esc(t.vpa || '—')}</span></div>
           <div class="kv"><span>UTR</span><span>${esc(t.utr || '—')}</span></div>
           ${t.note ? `<div class="kv"><span>${esc(T().fNote)}</span><span>${esc(t.note)}</span></div>` : ''}
         </div>
         <button class="btn ghost sm" id="del" style="margin-top:12px" type="button">${esc(T().delete)}</button>
       </div>`;
    const close = () => m.remove();
    $('.close', m).onclick = close;
    m.onclick = (e) => { if (e.target === m) close(); };
    $('#del', m).onclick = () => {
      state.txns = state.txns.filter((x) => x.id !== t.id);
      save(); close(); render(); toast(T().deleted);
    };
    document.body.appendChild(m);
  }

  /* ---------------------------- view: add ------------------------------ */
  function viewAdd() {
    const v = el('div');
    v.appendChild(el('div', 'section-title', esc(T().addTitle)));
    const days = [...new Set(state.txns.map((t) => t.day))].concat('14 November');
    const card = el('div', 'card',
      `<div class="field"><label>${esc(T().fPayee)}</label>
         <input id="a-payee" placeholder="${esc(T().fPayeePh)}"></div>
       <div class="field"><label>${esc(T().fVpa)}</label>
         <input id="a-vpa" placeholder="${esc(T().fVpaPh)}"></div>
       <div class="row2">
         <div class="field"><label>${esc(T().fAmount)}</label><input id="a-amt" type="number" inputmode="decimal" placeholder="0"></div>
         <div class="field"><label>${esc(T().fDate)}</label>
           <select id="a-day">${days.map((d) => `<option>${esc(d)}</option>`).join('')}</select></div>
       </div>
       <div class="row2">
         <div class="field"><label>${esc(T().fMethod)}</label>
           <select id="a-method">${METHODS.map((m) => `<option>${esc(m)}</option>`).join('')}</select></div>
         <div class="field"><label>${esc(T().fStatus)}</label>
           <select id="a-status">
             ${['success', 'pending', 'failed'].map((s) => `<option value="${s}">${esc(T().status[s])}</option>`).join('')}
           </select></div>
       </div>
       <div class="field"><label>${esc(T().fUtr)}</label>
         <input id="a-utr" inputmode="numeric" maxlength="12" placeholder="${esc(T().fUtrPh)}"></div>
       <div class="field"><label>${esc(T().fNote)}</label><input id="a-note"></div>
       <button class="btn" id="a-save" type="button">${esc(T().save)}</button>`);
    v.appendChild(card);

    $('#a-save', card).onclick = () => {
      const payee = $('#a-payee', card).value.trim();
      const amount = Number($('#a-amt', card).value);
      if (!payee) return toast(T().invalidName);
      if (!(amount > 0)) return toast(T().invalidAmount);
      const now = new Date();
      state.txns.unshift({
        id: 'tx_' + Math.random().toString(36).slice(2, 10),
        payee, amount,
        vpa: $('#a-vpa', card).value.trim(),
        method: $('#a-method', card).value,
        status: $('#a-status', card).value,
        day: $('#a-day', card).value,
        time: now.toTimeString().slice(0, 5),
        utr: $('#a-utr', card).value.trim(),
        note: $('#a-note', card).value.trim()
      });
      save(); toast(T().saved); go('tx');
    };
    return v;
  }

  /* --------------------------- view: verify ---------------------------- */
  function runChecks(input) {
    const R = T().res;
    const out = []; // {level, text}
    const payee = input.payee.trim();
    const isVpa = payee.includes('@');

    if (isVpa) out.push(VPA_RE.test(payee)
      ? { level: 'ok', text: R.format_ok }
      : { level: 'bad', text: R.format_bad });

    const key = payee.toLowerCase();
    const hist = state.txns.filter((t) =>
      t.payee.toLowerCase() === key || (t.vpa && t.vpa.toLowerCase() === key) ||
      (!isVpa && t.payee.toLowerCase().includes(key)));

    const knownOk = hist.filter((t) => t.status === 'success');
    if (knownOk.length) out.push({ level: 'ok', text: R.known_payee });
    else if (!hist.length) out.push({ level: 'warn', text: R.new_payee });
    else out.push({ level: 'warn', text: R.unsaved });

    if (hist.some((t) => /unsupported/i.test(t.payee)))
      out.push({ level: 'bad', text: R.unsupported });
    else if (hist.some((t) => t.status === 'failed'))
      out.push({ level: 'bad', text: R.past_fail });

    const amt = Number(input.amount || 0);
    if (amt >= 5000) out.push({ level: 'warn', text: R.large_amount });
    if (amt > 0 && amt % 500 === 0) out.push({ level: 'warn', text: R.round_amount });

    if (amt > 0) {
      const dup = state.txns.find((t) => Number(t.amount) === amt &&
        (t.payee.toLowerCase() === key || (t.vpa && t.vpa.toLowerCase() === key)) &&
        t.status === 'success');
      if (dup) out.push({ level: 'warn', text: R.dup_amount });
    }

    if (input.utr && input.utr.trim()) {
      out.push(/^\d{12}$/.test(input.utr.trim())
        ? { level: 'ok', text: R.utr_ok }
        : { level: 'bad', text: R.utr_bad });
    } else {
      out.push({ level: 'warn', text: R.utr_missing });
    }

    const hasBad = out.some((c) => c.level === 'bad');
    const hasWarn = out.some((c) => c.level === 'warn');
    const verdict = hasBad ? 'bad' : (hasWarn ? 'pend' : 'ok');
    const advice = hasBad ? R.advice_danger : (hasWarn ? R.advice_caution : R.advice_safe);
    return { verdict, advice, checks: out };
  }

  function viewVerify() {
    const v = el('div');
    v.appendChild(el('div', 'section-title', esc(T().verifyTitle)));
    v.appendChild(el('div', 'card',
      `<p style="margin:0 0 12px;font-size:12.5px;color:#9fb0cd;line-height:1.5">${esc(T().verifyIntro)}</p>
       <div class="field"><label>${esc(T().vPayee)}</label>
         <input id="v-payee" placeholder="${esc(T().vPayeePh)}"></div>
       <div class="row2">
         <div class="field"><label>${esc(T().vAmount)}</label><input id="v-amt" type="number" inputmode="decimal" placeholder="0"></div>
         <div class="field"><label>${esc(T().vUtr)}</label><input id="v-utr" inputmode="numeric" maxlength="12" placeholder="402730210114"></div>
       </div>
       <button class="btn green" id="v-go" type="button">🛡️ ${esc(T().check)}</button>`));

    const out = el('div');
    v.appendChild(out);

    $('#v-go', v).onclick = () => {
      const input = { payee: $('#v-payee', v).value, amount: $('#v-amt', v).value, utr: $('#v-utr', v).value };
      if (!input.payee.trim()) return toast(T().invalidName);
      state.verifyDraft = input;
      const r = runChecks(input);
      const title = r.verdict === 'ok' ? '✅ ' + T().safe : r.verdict === 'pend' ? '⚠️ ' + T().caution : '⛔ ' + T().danger;
      const icon = { ok: '✔', warn: '!', bad: '✕' };
      const cls = { ok: 'ok', warn: 'pend', bad: 'bad' };
      out.innerHTML =
        `<div class="result ${r.verdict}">
           <h3>${esc(title)}</h3>
           <p>${esc(r.advice)}</p>
         </div>
         <div class="section-title">${esc(T().checks)}</div>
         <div class="card">
           ${r.checks.map((c) => `<div class="kv"><span>${icon[c.level]}</span><span style="text-align:right">${esc(c.text)}</span></div>`).join('')}
         </div>
         <button class="btn sm" id="v-add" type="button">＋ ${esc(T().addPaymentBtn)}</button>`;
      $('#v-add', out).onclick = () => {
        const now = new Date();
        state.txns.unshift({
          id: 'tx_' + Math.random().toString(36).slice(2, 10),
          payee: input.payee.trim(),
          amount: Number(input.amount || 0),
          vpa: input.payee.includes('@') ? input.payee.trim() : '',
          method: 'UPI QR',
          status: r.verdict === 'ok' ? 'success' : 'pending',
          day: '14 November',
          time: now.toTimeString().slice(0, 5),
          utr: (input.utr || '').trim(), note: ''
        });
        save(); toast(T().saved); go('tx');
      };
      out.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };
    return v;
  }

  /* ----------------------------- view: qr ------------------------------ */
  function buildUpi(name, vpa, amount, note) {
    const p = new URLSearchParams();
    p.set('pa', vpa);
    if (name) p.set('pn', name);
    if (amount) p.set('am', Number(amount).toFixed(2));
    p.set('cu', 'INR');
    if (note) p.set('tn', note);
    return 'upi://pay?' + p.toString();
  }

  function renderQr(node, text) {
    node.innerHTML = '';
    try {
      const qr = qrcode(0, 'M');
      qr.addData(text);
      qr.make();
      const img = el('img');
      img.width = 220; img.height = 220;
      img.alt = 'UPI QR';
      img.src = qr.createDataURL(4, 8);
      node.appendChild(img);
    } catch (e) {
      node.appendChild(el('div', 'empty', 'QR error: ' + esc(e.message)));
    }
  }

  function viewQr() {
    const v = el('div');
    v.appendChild(el('div', 'section-title', esc(T().qrTitle)));
    v.appendChild(el('div', 'card',
      `<p style="margin:0 0 12px;font-size:12.5px;color:#9fb0cd;line-height:1.5">${esc(T().qrIntro)}</p>
       <div class="field"><label>${esc(T().qrPayeeName)}</label><input id="q-name" value="PayCheck Store"></div>
       <div class="field"><label>${esc(T().qrVpa)}</label><input id="q-vpa" placeholder="store@okaxis"></div>
       <div class="row2">
         <div class="field"><label>${esc(T().qrAmount)}</label><input id="q-amt" type="number" inputmode="decimal" placeholder="0"></div>
         <div class="field"><label>${esc(T().qrNote)}</label><input id="q-note" placeholder="Order #101"></div>
       </div>
       <button class="btn" id="q-go" type="button">▦ ${esc(T().generate)}</button>`));

    const box = el('div', 'qr-wrap');
    const qrBox = el('div', 'qr-box');
    const link = el('div', 'upi-link', esc(T().upiLink) + ': —');
    box.appendChild(qrBox); box.appendChild(link);
    v.appendChild(box);

    const gen = () => {
      const name = $('#q-name', v).value.trim();
      const vpa = $('#q-vpa', v).value.trim() || 'merchant@okaxis';
      const amt = $('#q-amt', v).value;
      const note = $('#q-note', v).value.trim();
      if (vpa && !VPA_RE.test(vpa)) toast(T().res.format_bad);
      const upi = buildUpi(name, vpa, amt, note);
      state.qr = { name, vpa, amt, note, upi };
      renderQr(qrBox, upi);
      link.textContent = T().upiLink + ': ' + upi;
    };
    $('#q-go', v).onclick = gen;
    requestAnimationFrame(gen);
    return v;
  }

  /* ------------------------------ router ------------------------------- */
  const VIEWS = { tx: viewTx, add: viewAdd, verify: viewVerify, qr: viewQr };

  function go(tab) { state.tab = tab; render(); }

  function render() {
    document.documentElement.lang = state.lang;
    document.querySelectorAll('.tab').forEach((b) =>
      b.classList.toggle('active', b.dataset.tab === state.tab));
    document.querySelectorAll('[data-i18n]').forEach((n) => {
      const k = n.dataset.i18n; if (T()[k]) n.textContent = T()[k];
    });
    $('#langBtn').textContent = state.lang === 'hi' ? 'EN' : 'हिं';
    const view = $('#view');
    view.innerHTML = '';
    view.appendChild(VIEWS[state.tab]());
    view.scrollTop = 0;
  }

  /* ------------------------------ init --------------------------------- */
  document.querySelectorAll('.tab').forEach((b) => b.onclick = () => go(b.dataset.tab));
  $('#langBtn').onclick = () => {
    state.lang = state.lang === 'hi' ? 'en' : 'hi';
    localStorage.setItem(STORE_LANG, state.lang);
    render();
  };
  $('#resetBtn').onclick = () => {
    state.txns = seed(); save(); render(); toast(T().reset);
  };

  load();
  render();
})();
