/* =========================================================================
   PayCheck — UPI payment verification app.
   Inspired by the anti-fraud reel: "Check the payment first, then hand over
   the goods." Vanilla JS, no build step. Per-user data in localStorage.

   Modules: auth.js (accounts), gateway.js (payment API), share.js (WhatsApp).
   ========================================================================= */
(() => {
  'use strict';

  const STORE_LANG = 'paycheck.lang.v1';
  const STORE_TX = 'paycheck.txns.v1';
  const STORE_QR = 'paycheck.qr.v1';
  const STORE_NOTIFIED = 'paycheck.notified.v1';

  /* ------------------------------- i18n -------------------------------- */
  const I18N = {
    en: {
      appName: 'PayCheck', tagline: 'UPI payment verifier',
      tabTx: 'Payments', tabAdd: 'Add', tabVerify: 'Verify', tabQr: 'QR', tabSettings: 'Settings',
      bannerTitle: 'Beware of online fraud',
      bannerText: 'Check the money first, then hand over the goods. Never trust a screenshot — confirm inside your bank app.',
      totalReceived: 'Received this month', txnCount: 'Payments', success: 'Successful', pending: 'Pending',
      searchPh: 'Search name, UPI ID, amount or UTR…',
      all: 'All', dateFilter: 'Date', methodFilter: 'Method',
      anyDate: 'Any date', anyMethod: 'Any method',
      noTxns: 'No payments found yet.',
      addTitle: 'Add a payment',
      fPayee: 'Payer / person name', fPayeePh: 'e.g. Saif Sayeed',
      fVpa: 'UPI ID (payer)', fVpaPh: 'name@bank',
      fAmount: 'Amount (₹)', fMethod: 'Method', fStatus: 'Status', fDate: 'Date',
      fUtr: 'UTR / reference no. (12 digits)', fUtrPh: 'e.g. 402730210114',
      fNote: 'Note (optional)',
      save: 'Save', saved: 'Payment saved', invalidAmount: 'Enter a valid amount', invalidName: 'Enter a name',
      verifyTitle: 'Verify a payment',
      verifyIntro: 'Fill this in before handing over goods. PayCheck scores the risk, then checks your payment gateway.',
      vPayee: 'Paid by whom? (name or UPI ID)', vPayeePh: 'Saif Sayeed / saif@okaxis',
      vAmount: 'How much? (₹)', vUtr: 'UTR number (if available)',
      check: 'Check now',
      safe: 'Safe — you can hand over the goods',
      caution: 'Be careful', danger: 'Danger — do not hand over the goods',
      checks: 'Your record check', gatewayTitle: 'Payment gateway check',
      gatewayRunning: 'Contacting gateway…', gatewaySkipped: 'Gateway check skipped.',
      addPaymentBtn: 'Add this payment to records',
      qrTitle: 'Collect a payment (QR)',
      qrIntro: 'Enter your UPI ID and amount — the customer scans the QR and pays you.',
      qrPayeeName: 'Merchant / your name', qrVpa: 'Your UPI ID', qrAmount: 'Amount (₹)',
      qrNote: 'Note', generate: 'Generate QR', upiLink: 'UPI link',
      detail: 'Payment detail', close: 'Close', delete: 'Delete payment', deleted: 'Payment deleted',
      reset: 'Demo data restored', resetDemo: 'Restore demo data',
      share: 'Share on WhatsApp', copy: 'Copy', copied: 'Copied to clipboard',
      shareReceipt: 'Share receipt', remind: 'Send reminder', sendQr: 'Send payment request',
      lang: 'Language', account: 'Account', signedInAs: 'Signed in as',
      signOut: 'Sign out', signIn: 'Sign in', signUp: 'Create account',
      fName: 'Your name', fShop: 'Shop / business name', fEmail: 'Email', fPassword: 'Password',
      fPin: 'App PIN (optional, 4–6 digits)',
      passHint: 'At least 8 characters.', pinHint: 'Quick unlock next time. You can skip this.',
      authTagline: 'Verify the payment before you hand over the goods.',
      authPoint1: 'Track every UPI payment you receive',
      authPoint2: 'Check a payer against your own records',
      authPoint3: 'Generate a UPI QR to collect money',
      useDemo: 'Use the demo account', welcome: 'Welcome',
      settingsTitle: 'Settings', merchantProfile: 'Merchant profile',
      shopNameLbl: 'Shop name', vpaLbl: 'Your UPI ID', vpaHint: 'Used for the collect QR.',
      gatewaySection: 'Payment gateway', gatewayMode: 'Verification mode',
      sandbox: 'Sandbox (offline simulator)', live: 'Live API',
      endpoint: 'Verification endpoint URL', apiKey: 'API key / secret',
      authStyle: 'Auth style', timeout: 'Timeout (seconds)', autoCheck: 'Auto-check on Verify tab',
      saveSettings: 'Save settings', settingsSaved: 'Settings saved',
      security: 'Security', changePassword: 'Change password',
      currentPass: 'Current password', newPass: 'New password', setPinLbl: 'Set / change app PIN',
      data: 'Data', exportData: 'Export my data (JSON)', importData: 'Import data (JSON)',
      imported: 'Data imported', exported: 'Backup downloaded',
      demoBanner: 'You are using the sandbox simulator — no real money or bank API is contacted.',
      liveBanner: 'Live mode: results come from your own gateway endpoint.',
      status: { success: 'Success', pending: 'Pending', failed: 'Failed' },
      res: {
        format_bad: 'UPI ID format is invalid', format_ok: 'UPI ID format looks valid',
        known_payee: 'You have received a successful payment from this person before',
        new_payee: 'This is a new payer — first-time transaction',
        dup_amount: 'The same amount arrived recently — possible duplicate',
        large_amount: 'Large amount — confirm it yourself in the bank app',
        round_amount: 'Round amount — fake screenshots are common',
        utr_bad: 'UTR number must be 12 digits', utr_ok: 'UTR number format is valid',
        utr_missing: 'No UTR given — confirm inside the bank app',
        past_fail: 'A previous payment from this person had failed',
        unsupported: 'This payment is recorded as “Unsupported”',
        unsaved: 'This payment is not in your records yet',
        advice_safe: 'Payment found in your records and the gateway confirms it. You may hand over the goods.',
        advice_caution: 'The payment is not fully confirmed. Confirm the credit in your bank app before handing over goods.',
        advice_danger: 'Payment could not be verified. Do not hand over the goods and re-check the payment.'
      },
      gw: {
        SUCCESS: 'Gateway confirms the payment', PENDING: 'Gateway says the payment is still processing',
        FAILED: 'Gateway says the payment failed', NOT_FOUND: 'Gateway has no record of this payment',
        UNKNOWN: 'Gateway returned an unclear status'
      }
    },
    hi: {
      appName: 'पेचेक', tagline: 'UPI भुगतान जाँच',
      tabTx: 'लेन-देन', tabAdd: 'जोड़ें', tabVerify: 'जाँचें', tabQr: 'QR', tabSettings: 'सेटिंग',
      bannerTitle: 'ऑनलाइन धोखाधड़ी से सावधान',
      bannerText: 'पैसा पहले जाँचें, फिर सामान दें। स्क्रीनशॉट पर भरोसा न करें — बैंक ऐप में खुद देखें।',
      totalReceived: 'इस महीने कुल प्राप्त', txnCount: 'लेन-देन', success: 'सफल', pending: 'प्रतीक्षित',
      searchPh: 'नाम, UPI ID, रकम या UTR खोजें…',
      all: 'सभी', dateFilter: 'तारीख़', methodFilter: 'तरीक़ा',
      anyDate: 'कोई भी तारीख़', anyMethod: 'कोई भी तरीक़ा',
      noTxns: 'अभी कोई लेन-देन नहीं।',
      addTitle: 'नया भुगतान जोड़ें',
      fPayee: 'भुगतानकर्ता / व्यक्ति का नाम', fPayeePh: 'जैसे: Saif Sayeed',
      fVpa: 'UPI ID (भुगतानकर्ता)', fVpaPh: 'name@bank',
      fAmount: 'रकम (₹)', fMethod: 'तरीक़ा', fStatus: 'स्थिति', fDate: 'तारीख़',
      fUtr: 'UTR / संदर्भ नंबर (12 अंक)', fUtrPh: 'जैसे: 402730210114', fNote: 'नोट (वैकल्पिक)',
      save: 'सहेजें', saved: 'लेन-देन सहेजा गया', invalidAmount: 'सही रकम डालें', invalidName: 'नाम भरें',
      verifyTitle: 'भुगतान की जाँच करें',
      verifyIntro: 'सामान देने से पहले यह भरें। पेचेक जोखिम जाँचता है, फिर आपके भुगतान गेटवे से पुष्टि करता है।',
      vPayee: 'किसका भुगतान? (नाम या UPI ID)', vPayeePh: 'Saif Sayeed / saif@okaxis',
      vAmount: 'कितनी रकम? (₹)', vUtr: 'UTR नंबर (यदि मिला हो)',
      check: 'अब जाँचें',
      safe: 'सुरक्षित — सामान दे सकते हैं', caution: 'सावधानी बरतें', danger: 'खतरा — सामान न दें',
      checks: 'आपके रिकॉर्ड की जाँच', gatewayTitle: 'भुगतान गेटवे जाँच',
      gatewayRunning: 'गेटवे से संपर्क हो रहा है…', gatewaySkipped: 'गेटवे जाँच छोड़ी गई।',
      addPaymentBtn: 'इस भुगतान को रिकॉर्ड में जोड़ें',
      qrTitle: 'भुगतान लें (QR)',
      qrIntro: 'अपना UPI ID और रकम डालें — ग्राहक QR स्कैन करके भुगतान करेगा।',
      qrPayeeName: 'व्यापारी / आपका नाम', qrVpa: 'आपका UPI ID', qrAmount: 'रकम (₹)',
      qrNote: 'नोट', generate: 'QR बनाएँ', upiLink: 'UPI लिंक',
      detail: 'लेन-देन विवरण', close: 'बंद करें', delete: 'भुगतान हटाएँ', deleted: 'हटा दिया गया',
      reset: 'डेमो डेटा बहाल', resetDemo: 'डेमो डेटा बहाल करें',
      share: 'WhatsApp पर भेजें', copy: 'कॉपी', copied: 'क्लिपबोर्ड पर कॉपी हो गया',
      shareReceipt: 'रसीद भेजें', remind: 'याद दिलाएँ', sendQr: 'भुगतान अनुरोध भेजें',
      lang: 'भाषा', account: 'खाता', signedInAs: 'साइन इन',
      signOut: 'साइन आउट', signIn: 'साइन इन', signUp: 'खाता बनाएँ',
      fName: 'आपका नाम', fShop: 'दुकान / व्यवसाय का नाम', fEmail: 'ईमेल', fPassword: 'पासवर्ड',
      fPin: 'ऐप PIN (वैकल्पिक, 4–6 अंक)',
      passHint: 'कम से कम 8 अक्षर।', pinHint: 'अगली बार जल्दी खुलेगा। छोड़ भी सकते हैं।',
      authTagline: 'सामान देने से पहले भुगतान जाँचें।',
      authPoint1: 'हर UPI भुगतान दर्ज करें', authPoint2: 'अपने रिकॉर्ड से भुगतानकर्ता जाँचें',
      authPoint3: 'पैसे लेने के लिए UPI QR बनाएँ',
      useDemo: 'डेमो खाते से चलाएँ', welcome: 'स्वागत है',
      settingsTitle: 'सेटिंग', merchantProfile: 'व्यापारी प्रोफ़ाइल',
      shopNameLbl: 'दुकान का नाम', vpaLbl: 'आपका UPI ID', vpaHint: 'QR बनाने में इस्तेमाल होगा।',
      gatewaySection: 'भुगतान गेटवे', gatewayMode: 'जाँच का तरीक़ा',
      sandbox: 'सैंडबॉक्स (ऑफ़लाइन सिम्युलेटर)', live: 'लाइव API',
      endpoint: 'जाँच एंडपॉइंट URL', apiKey: 'API कुंजी / सीक्रेट',
      authStyle: 'प्रमाणीकरण शैली', timeout: 'टाइमआउट (सेकंड)', autoCheck: 'जाँच टैब पर अपने-आप चलाएँ',
      saveSettings: 'सेटिंग सहेजें', settingsSaved: 'सेटिंग सहेजी गई',
      security: 'सुरक्षा', changePassword: 'पासवर्ड बदलें',
      currentPass: 'वर्तमान पासवर्ड', newPass: 'नया पासवर्ड', setPinLbl: 'ऐप PIN बदलें',
      data: 'डेटा', exportData: 'मेरा डेटा निर्यात करें (JSON)', importData: 'डेटा आयात करें (JSON)',
      imported: 'डेटा आयात हुआ', exported: 'बैकअप डाउनलोड हुआ',
      demoBanner: 'आप सैंडबॉक्स सिम्युलेटर पर हैं — कोई असली पैसा या बैंक API नहीं जुड़ा।',
      liveBanner: 'लाइव मोड: नतीजे आपके ही गेटवे एंडपॉइंट से आते हैं।',
      status: { success: 'सफल', pending: 'प्रतीक्षित', failed: 'असफल' },
      res: {
        format_bad: 'UPI ID का प्रारूप ग़लत है', format_ok: 'UPI ID सही प्रारूप में है',
        known_payee: 'इस व्यक्ति से पहले भी सफल भुगतान मिला है',
        new_payee: 'यह नया भुगतानकर्ता है — पहली बार लेन-देन',
        dup_amount: 'कुछ समय पहले ही इतनी ही रकम मिली है — दोहराव हो सकता है',
        large_amount: 'रकम बड़ी है — बैंक ऐप में खुद पुष्टि करें',
        round_amount: 'गोल रकम है — फ़र्ज़ी स्क्रीनशॉट आम हैं',
        utr_bad: 'UTR नंबर 12 अंकों का होना चाहिए', utr_ok: 'UTR नंबर का प्रारूप सही है',
        utr_missing: 'UTR नंबर नहीं दिया गया — बैंक ऐप में जाँचें',
        past_fail: 'इस व्यक्ति का पहले का भुगतान असफल रहा था',
        unsupported: 'यह भुगतान “Unsupported” के रूप में दर्ज है',
        unsaved: 'यह भुगतान अभी आपके रिकॉर्ड में नहीं है',
        advice_safe: 'भुगतान रिकॉर्ड में मिला और गेटवे ने भी पुष्टि की। सामान दे सकते हैं।',
        advice_caution: 'भुगतान पूरी तरह पक्का नहीं है। सामान देने से पहले बैंक ऐप में पुष्टि करें।',
        advice_danger: 'भुगतान सत्यापित नहीं हुआ। कृपया सामान न दें और दोबारा जाँचें।'
      },
      gw: {
        SUCCESS: 'गेटवे भुगतान की पुष्टि करता है', PENDING: 'गेटवे कहता है भुगतान अभी प्रक्रिया में है',
        FAILED: 'गेटवे कहता है भुगतान असफल रहा', NOT_FOUND: 'गेटवे के पास इस भुगतान का कोई रिकॉर्ड नहीं',
        UNKNOWN: 'गेटवे ने अस्पष्ट स्थिति दी'
      }
    }
  };

  /* ----------------------------- utilities ----------------------------- */
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
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
  const uid = () => 'tx_' + Math.random().toString(36).slice(2, 10);
  const todayLabel = () => new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long' });
  const readJSON = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
  const writeJSON = (k, v) => localStorage.setItem(k, JSON.stringify(v));

  /* ------------------------------- state -------------------------------- */
  const state = {
    lang: localStorage.getItem(STORE_LANG) || 'en',
    tab: 'tx',
    q: '', date: '', method: '', status: '',
    txns: [],
    verifyDraft: null,
    lastGateway: null,
    qr: null,
    user: null
  };
  const T = () => I18N[state.lang];

  const METHODS = ['Google Pay', 'PhonePe', 'Paytm', 'UPI QR', 'Bank Transfer'];

  /* ---------------------------- storage --------------------------------- */
  const txKey = () => Auth.dataKey(STORE_TX, state.user && state.user.id);
  const qrKey = () => Auth.dataKey(STORE_QR, state.user && state.user.id);
  const save = () => writeJSON(txKey(), state.txns);

  function seed() {
    const mk = (payee, amount, method, status, day, time, vpa, utr) => ({
      id: uid(), payee, amount, method, status, day, time, vpa: vpa || '', utr: utr || '', note: ''
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
    state.txns = readJSON(txKey(), null) || seed();
    state.qr = readJSON(qrKey(), null);
    state.user = Auth.current();
    const meta = readJSON(Auth.dataKey('paycheck.meta', state.user && state.user.id), {});
    state.vpa = meta.vpa || '';
  }

  /* --------------------------- derivation ------------------------------- */
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
      count: state.txns.length, success: ok.length,
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

  /* ---------------------------- shared UI ------------------------------- */
  function toast(msg) {
    const t = $('#toast');
    t.textContent = msg; t.classList.add('show');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove('show'), 2400);
  }

  const statusBadge = (s) =>
    `<span class="badge ${{ success: 'ok', pending: 'pend', failed: 'bad' }[s] || 'pend'}">${esc(T().status[s] || s)}</span>`;

  function merchantName() {
    return (state.user && state.user.shop) || (state.user && state.user.name) || 'PayCheck';
  }

  /* ------------------------- view: payments ----------------------------- */
  function viewTx() {
    const v = el('div');
    const tot = totals();
    const days = [...new Set(state.txns.map((t) => t.day))];

    v.appendChild(el('div', 'banner',
      `<span class="em">⚠️</span><div><strong>${esc(T().bannerTitle)}</strong><p>${esc(T().bannerText)}</p></div>`));

    v.appendChild(el('div', 'summary',
      `<div class="label">${esc(T().totalReceived)}</div>
       <div class="amount">${inr(tot.amount).replace('.00', '')}</div>
       <div class="summary-grid">
         <div class="cell"><b>${tot.count}</b><span>${esc(T().txnCount)}</span></div>
         <div class="cell"><b style="color:#4ade80">${tot.success}</b><span>${esc(T().success)}</span></div>
         <div class="cell"><b style="color:#fbbf24">${tot.pending}</b><span>${esc(T().pending)}</span></div>
       </div>`));

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
    if (state.method || state.date)
      addChip('✕ ' + T().all, false, () => { state.method = ''; state.date = ''; render(); });
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
      const dayTotal = items.filter((t) => t.status === 'success').reduce((a, t) => a + Number(t.amount), 0);
      const g = el('div', 'day-group');
      g.appendChild(el('div', 'day-head', `<span>${esc(day)}</span><b>${inr(dayTotal).replace('.00', '')}</b>`));
      items.forEach((t) => {
        const row = el('div', 'txn',
          `<div class="av" style="background:${avatarColor(t.payee)}">${esc(initials(t.payee))}</div>
           <div class="mid"><div class="name">${esc(t.payee)}</div>
             <div class="sub">${esc(t.method)}${t.vpa ? ' · ' + esc(t.vpa) : ''}</div></div>
           <div class="right"><div class="amt cr">${inr(t.amount)}</div>
             <div class="time">${esc(t.time)}</div>${statusBadge(t.status)}</div>`);
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
    state.method = (opts[(opts.indexOf(cur) + 1) % opts.length]) === T().anyMethod ? '' :
      opts[(opts.indexOf(cur) + 1) % opts.length];
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
         <div class="share-bar">
           <button class="btn wa-btn" id="wa" type="button">🟢 ${esc(T().shareReceipt)}</button>
           <button class="btn copy-btn" id="cp" type="button">⧉ ${esc(T().copy)}</button>
         </div>
         ${t.status === 'pending' ? `<button class="btn ghost sm" id="rm" type="button" style="margin-top:8px">🔔 ${esc(T().remind)}</button>` : ''}
         <button class="btn ghost sm" id="del" type="button" style="margin-top:8px">${esc(T().delete)}</button>
       </div>`;
    const close = () => m.remove();
    $('.close', m).onclick = close;
    m.onclick = (e) => { if (e.target === m) close(); };

    const receipt = Share.receipt(t, merchantName());
    $('#wa', m).onclick = () => Share.open(receipt);
    $('#cp', m).onclick = async () => toast((await Share.copy(receipt)) ? T().copied : T().share);
    const rm = $('#rm', m);
    if (rm) rm.onclick = () => Share.open(Share.reminder(t.payee, t.amount, merchantName()));
    $('#del', m).onclick = () => {
      state.txns = state.txns.filter((x) => x.id !== t.id);
      save(); close(); render(); toast(T().deleted);
    };
    document.body.appendChild(m);
  }

  /* ---------------------------- view: add ------------------------------- */
  function viewAdd() {
    const v = el('div');
    v.appendChild(el('div', 'section-title', esc(T().addTitle)));
    const days = [...new Set(state.txns.map((t) => t.day))].concat(todayLabel());
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
           <select id="a-status">${['success', 'pending', 'failed'].map((s) => `<option value="${s}">${esc(T().status[s])}</option>`).join('')}</select></div>
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
      state.txns.unshift({
        id: uid(), payee, amount,
        vpa: $('#a-vpa', card).value.trim(),
        method: $('#a-method', card).value,
        status: $('#a-status', card).value,
        day: $('#a-day', card).value,
        time: new Date().toTimeString().slice(0, 5),
        utr: $('#a-utr', card).value.trim(),
        note: $('#a-note', card).value.trim()
      });
      save(); toast(T().saved); go('tx');
    };
    return v;
  }

  /* --------------------------- view: verify ----------------------------- */
  function runChecks(input) {
    const R = T().res;
    const out = [];
    const raw = String(input.payee || '').trim();
    const isVpa = raw.includes('@');
    const key = raw.toLowerCase();

    if (isVpa) out.push(VPA_RE.test(raw)
      ? { level: 'ok', text: R.format_ok } : { level: 'bad', text: R.format_bad });

    const hist = state.txns.filter((t) =>
      t.payee.toLowerCase() === key || (t.vpa && t.vpa.toLowerCase() === key) ||
      (!isVpa && t.payee.toLowerCase().includes(key)));

    if (hist.some((t) => t.status === 'success')) out.push({ level: 'ok', text: R.known_payee });
    else if (!hist.length) out.push({ level: 'warn', text: R.new_payee });
    else out.push({ level: 'warn', text: R.unsaved });

    if (hist.some((t) => /unsupported/i.test(t.payee))) out.push({ level: 'bad', text: R.unsupported });
    else if (hist.some((t) => t.status === 'failed')) out.push({ level: 'bad', text: R.past_fail });

    const amt = Number(input.amount || 0);
    if (amt >= 5000) out.push({ level: 'warn', text: R.large_amount });
    if (amt > 0 && amt % 500 === 0) out.push({ level: 'warn', text: R.round_amount });

    if (amt > 0) {
      const dup = state.txns.find((t) => Number(t.amount) === amt &&
        (t.payee.toLowerCase() === key || (t.vpa && t.vpa.toLowerCase() === key)) && t.status === 'success');
      if (dup) out.push({ level: 'warn', text: R.dup_amount });
    }

    if (input.utr && String(input.utr).trim()) {
      out.push(/^\d{12}$/.test(String(input.utr).trim())
        ? { level: 'ok', text: R.utr_ok } : { level: 'bad', text: R.utr_bad });
    } else out.push({ level: 'warn', text: R.utr_missing });

    return { checks: out };
  }

  /** Combine local checks with a gateway result into a final verdict. */
  function verdictFor(checks, gw) {
    const R = T().res;
    let hasBad = checks.some((c) => c.level === 'bad');
    let hasWarn = checks.some((c) => c.level === 'warn');

    if (gw) {
      if (gw.status === 'SUCCESS') hasBad = false;
      else if (gw.status === 'FAILED' || gw.status === 'NOT_FOUND') hasBad = true;
      else if (gw.status === 'PENDING' || gw.status === 'UNKNOWN') hasWarn = true;
    }
    const verdict = hasBad ? 'bad' : (hasWarn ? 'pend' : 'ok');
    const advice = hasBad ? R.advice_danger : (hasWarn ? R.advice_caution : R.advice_safe);
    return { verdict, advice };
  }

  function gwStatusText(status) {
    return (T().gw[status] || T().gw.UNKNOWN);
  }

  function viewVerify() {
    const v = el('div');
    v.appendChild(el('div', 'section-title', esc(T().verifyTitle)));

    const cfg = Gateway.getConfig(state.user && state.user.id);
    const banner = el('div', 'mode-pill ' + (cfg.mode === 'live' ? 'live' : 'sandbox'),
      cfg.mode === 'live' ? '● ' + esc(T().live) : '● ' + esc(T().sandbox));
    v.appendChild(el('div', 'card',
      `<p style="margin:0 0 10px;font-size:12.5px;color:#9fb0cd;line-height:1.5">${esc(T().verifyIntro)}</p>`));
    v.appendChild(banner);

    const form = el('div', 'card',
      `<div class="field"><label>${esc(T().vPayee)}</label>
         <input id="v-payee" placeholder="${esc(T().vPayeePh)}"></div>
       <div class="row2">
         <div class="field"><label>${esc(T().vAmount)}</label><input id="v-amt" type="number" inputmode="decimal" placeholder="0"></div>
         <div class="field"><label>${esc(T().vUtr)}</label><input id="v-utr" inputmode="numeric" maxlength="12" placeholder="402730210114"></div>
       </div>
       <button class="btn green" id="v-go" type="button">🛡️ ${esc(T().check)}</button>`);
    v.appendChild(form);

    const out = el('div');
    v.appendChild(out);

    const icon = { ok: '✔', warn: '!', bad: '✕' };

    function renderResult(checks, gw, gwState) {
      const { verdict, advice } = verdictFor(checks, gw);
      const title = verdict === 'ok' ? '✅ ' + T().safe : verdict === 'pend' ? '⚠️ ' + T().caution : '⛔ ' + T().danger;
      out.innerHTML =
        `<div class="result ${verdict}"><h3>${esc(title)}</h3><p>${esc(advice)}</p></div>
         <div class="section-title">${esc(T().checks)}</div>
         <div class="card">${checks.map((c) =>
            `<div class="kv"><span>${icon[c.level]}</span><span style="text-align:right">${esc(c.text)}</span></div>`).join('')}</div>`;

      // gateway panel
      const gwBox = el('div', 'gw-box');
      if (gwState === 'running') {
        gwBox.innerHTML = `<div class="head"><b>${esc(T().gatewayTitle)}</b>
          <span class="gw-status PENDING"><span class="spinner"></span> ${esc(T().gatewayRunning)}</span></div>`;
      } else if (gwState === 'skipped') {
        gwBox.innerHTML = `<div class="head"><b>${esc(T().gatewayTitle)}</b>
          <span class="gw-status UNKNOWN">${esc(T().gatewaySkipped)}</span></div>`;
      } else if (gw) {
        gwBox.innerHTML =
          `<div class="head"><b>${esc(T().gatewayTitle)}</b>
             <span class="gw-status ${esc(gw.status)}">${esc(gw.status)}</span></div>
           <div class="kv"><span>${esc(gwStatusText(gw.status))}</span><span></span></div>
           ${gw.payerName ? `<div class="kv"><span>${esc(T().fPayee)}</span><span>${esc(gw.payerName)}</span></div>` : ''}
           ${gw.amount ? `<div class="kv"><span>${esc(T().fAmount)}</span><span>${inr(gw.amount)}</span></div>` : ''}
           ${gw.utr ? `<div class="kv"><span>UTR</span><span>${esc(gw.utr)}</span></div>` : ''}
           ${gw.ref ? `<div class="kv"><span>Ref</span><span>${esc(gw.ref)}</span></div>` : ''}
           ${gw.bank ? `<div class="kv"><span>Bank</span><span>${esc(gw.bank)}</span></div>` : ''}
           <div class="kv"><span>Mode</span><span>${esc(gw.mode)}</span></div>`;
      }
      out.appendChild(gwBox);

      // actions
      const actions = el('div');
      const summary = Share.verifySummary({
        payee: form.querySelector('#v-payee').value, amount: form.querySelector('#v-amt').value,
        verdict, gatewayStatus: gw && gw.status, merchant: merchantName()
      });
      actions.innerHTML =
        `<div class="share-bar">
           <button class="btn wa-btn" id="v-wa" type="button">🟢 ${esc(T().share)}</button>
           <button class="btn copy-btn" id="v-cp" type="button">⧉ ${esc(T().copy)}</button>
         </div>
         <button class="btn sm" id="v-add" type="button" style="margin-top:8px">＋ ${esc(T().addPaymentBtn)}</button>`;
      out.appendChild(actions);
      $('#v-wa', actions).onclick = () => Share.open(summary);
      $('#v-cp', actions).onclick = async () => toast((await Share.copy(summary)) ? T().copied : T().copy);
      $('#v-add', actions).onclick = () => {
        const payee = form.querySelector('#v-payee').value.trim();
        const amount = Number(form.querySelector('#v-amt').value || 0);
        state.txns.unshift({
          id: uid(), payee, amount,
          vpa: payee.includes('@') ? payee : '',
          method: 'UPI QR',
          status: verdict === 'ok' ? 'success' : 'pending',
          day: todayLabel(), time: new Date().toTimeString().slice(0, 5),
          utr: form.querySelector('#v-utr').value.trim(), note: ''
        });
        save(); toast(T().saved); go('tx');
      };
    }

    async function check() {
      const input = {
        payee: $('#v-payee', v).value, amount: $('#v-amt', v).value, utr: $('#v-utr', v).value
      };
      if (!input.payee.trim()) return toast(T().invalidName);
      state.verifyDraft = input;

      const checks = runChecks(input).checks;
      renderResult(checks, null, cfg.autoCheck ? 'running' : 'skipped');
      out.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

      if (!cfg.autoCheck) return;
      try {
        const gw = await Gateway.verify(input, state.user && state.user.id);
        state.lastGateway = gw;
        renderResult(checks, gw, 'done');
      } catch (e) {
        renderResult(checks, { status: 'UNKNOWN', mode: cfg.mode, payerName: '', amount: null,
          utr: '', ref: '', bank: '', error: e.message }, 'done');
        toast(e.message);
      }
    }

    $('#v-go', v).onclick = check;
    return v;
  }

  /* ----------------------------- view: qr ------------------------------- */
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
      img.width = 220; img.height = 220; img.alt = 'UPI QR';
      img.src = qr.createDataURL(4, 8);
      node.appendChild(img);
    } catch (e) {
      node.appendChild(el('div', 'empty', 'QR error: ' + esc(e.message)));
    }
  }

  function viewQr() {
    const v = el('div');
    v.appendChild(el('div', 'section-title', esc(T().qrTitle)));

    const saved = state.qr || {};
    const defaultName = saved.name || merchantName();
    const defaultVpa = saved.vpa || state.vpa || '';
    const card = el('div', 'card',
      `<p style="margin:0 0 12px;font-size:12.5px;color:#9fb0cd;line-height:1.5">${esc(T().qrIntro)}</p>
       <div class="field"><label>${esc(T().qrPayeeName)}</label><input id="q-name" value="${esc(defaultName)}"></div>
       <div class="field"><label>${esc(T().qrVpa)}</label><input id="q-vpa" value="${esc(defaultVpa)}" placeholder="store@okaxis"></div>
       <div class="row2">
         <div class="field"><label>${esc(T().qrAmount)}</label><input id="q-amt" type="number" inputmode="decimal" value="${esc(saved.amt || '')}" placeholder="0"></div>
         <div class="field"><label>${esc(T().qrNote)}</label><input id="q-note" value="${esc(saved.note || '')}" placeholder="Order #101"></div>
       </div>
       <button class="btn" id="q-go" type="button">▦ ${esc(T().generate)}</button>`);
    v.appendChild(card);

    const box = el('div', 'qr-wrap');
    const qrBox = el('div', 'qr-box');
    const link = el('div', 'upi-link', esc(T().upiLink) + ': —');
    box.appendChild(qrBox); box.appendChild(link);
    v.appendChild(box);

    const actions = el('div', 'share-bar');
    actions.innerHTML =
      `<button class="btn wa-btn" id="q-wa" type="button">🟢 ${esc(T().sendQr)}</button>
       <button class="btn copy-btn" id="q-cp" type="button">⧉ ${esc(T().copy)}</button>`;
    v.appendChild(actions);

    const gen = () => {
      const name = $('#q-name', v).value.trim();
      const vpa = $('#q-vpa', v).value.trim();
      const amt = $('#q-amt', v).value;
      const note = $('#q-note', v).value.trim();
      if (!vpa) return toast(T().res.format_bad);
      if (!VPA_RE.test(vpa)) toast(T().res.format_bad);
      const upi = buildUpi(name, vpa, amt, note);
      state.qr = { name, vpa, amt, note, upi };
      writeJSON(qrKey(), state.qr);
      renderQr(qrBox, upi);
      link.textContent = T().upiLink + ': ' + upi;
      return upi;
    };
    $('#q-go', v).onclick = gen;
    $('#q-wa', v).onclick = () => {
      const cur = state.qr && state.qr.upi ? state.qr : { name: $('#q-name', v).value, vpa: $('#q-vpa', v).value, amt: $('#q-amt', v).value, note: $('#q-note', v).value };
      Share.open(Share.collect({ merchant: cur.name, vpa: cur.vpa, amount: cur.amt, note: cur.note }));
    };
    $('#q-cp', v).onclick = async () => {
      const text = state.qr && state.qr.upi ? state.qr.upi : '';
      toast((await Share.copy(text)) ? T().copied : T().copy);
    };
    requestAnimationFrame(() => { if (defaultVpa) gen(); });
    return v;
  }

  /* --------------------------- view: settings --------------------------- */
  function viewSettings() {
    const v = el('div');
    const u = state.user || {};
    const uidr = u.id;
    const cfg = Gateway.getConfig(uidr);
    v.appendChild(el('div', 'section-title', esc(T().settingsTitle)));

    // account
    v.appendChild(el('div', 'set-group',
      `<div class="set-row"><div><div class="lbl">${esc(T().account)}</div>
         <div class="sub">${esc(u.name || '')}</div></div><div class="val">${esc(u.email || '')}</div></div>
       <div class="set-row"><div><div class="lbl">${esc(T().shopNameLbl)}</div></div>
         <div class="val" id="s-shop">${esc(u.shop || '—')}</div></div>`));

    // merchant profile
    const prof = el('div', 'set-group',
      `<div class="set-row col"><div class="lbl">${esc(T().merchantProfile)}</div></div>
       <div class="set-row col"><div class="lbl"><span>${esc(T().shopNameLbl)}</span></div>
         <input id="s-shop-in" value="${esc(u.shop || '')}" placeholder="My Store"></div>
       <div class="set-row col"><div class="lbl"><span>${esc(T().vpaLbl)}</span>
         <span class="sub">${esc(T().vpaHint)}</span></div>
         <input id="s-vpa-in" value="${esc(state.vpa || '')}" placeholder="store@okaxis"></div>`);
    v.appendChild(prof);

    // gateway
    const gw = el('div', 'set-group',
      `<div class="set-row"><div><div class="lbl">${esc(T().gatewaySection)}</div>
         <div class="sub">${esc(T().gatewayMode)}</div></div>
         <span class="mode-pill ${cfg.mode === 'live' ? 'live' : 'sandbox'}">${esc(cfg.mode === 'live' ? T().live : T().sandbox)}</span></div>
       <div class="set-row col"><div class="lbl"><span>${esc(T().gatewayMode)}</span></div>
         <select id="s-mode">
           <option value="sandbox"${cfg.mode === 'sandbox' ? ' selected' : ''}>${esc(T().sandbox)}</option>
           <option value="live"${cfg.mode === 'live' ? ' selected' : ''}>${esc(T().live)}</option>
         </select></div>
       <div class="set-row col"><div class="lbl"><span>${esc(T().endpoint)}</span></div>
         <input id="s-endpoint" value="${esc(cfg.endpoint)}" placeholder="https://api.example.com/v1/payments/verify"></div>
       <div class="set-row col"><div class="lbl"><span>${esc(T().apiKey)}</span></div>
         <input id="s-key" type="password" value="${esc(cfg.apiKey)}" placeholder="sk_live_…"></div>
       <div class="set-row col"><div class="lbl"><span>${esc(T().authStyle)}</span></div>
         <select id="s-auth">
           ${['bearer', 'x-api-key', 'query'].map((a) => `<option value="${a}"${cfg.authStyle === a ? ' selected' : ''}>${a}</option>`).join('')}
         </select></div>
       <div class="set-row"><div><div class="lbl">${esc(T().timeout)}</div></div>
         <input id="s-timeout" type="number" min="2" max="60" value="${cfg.timeoutMs / 1000}" style="width:80px"></div>
       <div class="set-row"><div><div class="lbl">${esc(T().autoCheck)}</div></div>
         <label class="switch"><input id="s-auto" type="checkbox"${cfg.autoCheck ? ' checked' : ''}>
           <span class="track"></span><span class="knob"></span></label></div>
       <div class="set-row"><button class="btn sm" id="s-save-gw" type="button">${esc(T().saveSettings)}</button></div>`);
    v.appendChild(gw);

    // security
    const sec = el('div', 'set-group',
      `<div class="set-row col"><div class="lbl">${esc(T().security)}</div></div>
       <div class="set-row col"><div class="lbl"><span>${esc(T().currentPass)}</span></div>
         <input id="s-oldpass" type="password"></div>
       <div class="set-row col"><div class="lbl"><span>${esc(T().newPass)}</span></div>
         <input id="s-newpass" type="password"></div>
       <div class="set-row"><button class="btn sm ghost" id="s-chpass" type="button">${esc(T().changePassword)}</button></div>
       <div class="set-row col"><div class="lbl"><span>${esc(T().setPinLbl)}</span></div>
         <input id="s-pin" inputmode="numeric" maxlength="6" placeholder="1234"></div>
       <div class="set-row"><button class="btn sm ghost" id="s-setpin" type="button">${esc(T().saveSettings)}</button></div>`);
    v.appendChild(sec);

    // data
    const data = el('div', 'set-group',
      `<div class="set-row col"><div class="lbl">${esc(T().data)}</div></div>
       <div class="set-row"><button class="btn sm ghost" id="s-export" type="button">⬇ ${esc(T().exportData)}</button>
         <button class="btn sm ghost" id="s-import" type="button">⬆ ${esc(T().importData)}</button></div>
       <div class="set-row"><button class="btn sm ghost" id="s-reset" type="button">${esc(T().resetDemo)}</button></div>`);
    v.appendChild(data);

    // handlers
    $('#s-save-gw', gw).onclick = () => {
      Gateway.setConfig(uidr, {
        mode: $('#s-mode', gw).value,
        endpoint: $('#s-endpoint', gw).value.trim(),
        apiKey: $('#s-key', gw).value,
        authStyle: $('#s-auth', gw).value,
        timeoutMs: Math.max(2, Math.min(60, Number($('#s-timeout', gw).value) || 12)) * 1000,
        autoCheck: $('#s-auto', gw).checked
      });
      const meta = readJSON(Auth.dataKey('paycheck.meta', uidr), {});
      meta.vpa = $('#s-vpa-in', prof).value.trim();
      writeJSON(Auth.dataKey('paycheck.meta', uidr), meta);
      state.vpa = meta.vpa;
      const shop = $('#s-shop-in', prof).value.trim();
      state.user = Auth.update(uidr, { shop });
      paintUser();
      toast(T().settingsSaved);
    };

    $('#s-chpass', sec).onclick = async () => {
      try {
        await Auth.changePassword(uidr, $('#s-oldpass', sec).value, $('#s-newpass', sec).value);
        $('#s-oldpass', sec).value = ''; $('#s-newpass', sec).value = '';
        toast(T().settingsSaved);
      } catch (e) { toast(e.message); }
    };
    $('#s-setpin', sec).onclick = async () => {
      try { await Auth.setPin(uidr, $('#s-pin', sec).value.trim()); toast(T().settingsSaved); }
      catch (e) { toast(e.message); }
    };
    $('#s-export', data).onclick = () => {
      const blob = new Blob([JSON.stringify({
        exportedAt: new Date().toISOString(), account: { name: u.name, email: u.email, shop: u.shop },
        payments: state.txns, qr: state.qr
      }, null, 2)], { type: 'application/json' });
      const a = el('a'); a.href = URL.createObjectURL(blob);
      a.download = 'paycheck-backup.json'; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      toast(T().exported);
    };
    $('#s-import', data).onclick = () => {
      const inp = el('input'); inp.type = 'file'; inp.accept = 'application/json';
      inp.onchange = () => {
        const f = inp.files[0]; if (!f) return;
        const fr = new FileReader();
        fr.onload = () => {
          try {
            const j = JSON.parse(fr.result);
            if (Array.isArray(j.payments)) { state.txns = j.payments; save(); }
            render(); toast(T().imported);
          } catch { toast(T().invalidAmount); }
        };
        fr.readAsText(f);
      };
      inp.click();
    };
    $('#s-reset', data).onclick = () => { state.txns = seed(); save(); render(); toast(T().reset); };

    return v;
  }

  /* ------------------------------ router -------------------------------- */
  const VIEWS = { tx: viewTx, add: viewAdd, verify: viewVerify, qr: viewQr, settings: viewSettings };

  function go(tab) { state.tab = tab; render(); }

  function paintUser() {
    const u = state.user || {};
    const chip = $('#userChip');
    if (chip) {
      chip.innerHTML = `<span class="dot">${esc(initials(u.name || '?'))}</span><span>${esc(u.name || '')}</span>`;
    }
    const shop = $('#shopName');
    if (shop) shop.textContent = u.shop || T().tagline;
  }

  function render() {
    document.documentElement.lang = state.lang;
    $$('.tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === state.tab));
    $$('[data-i18n]').forEach((n) => { const k = n.dataset.i18n; if (T()[k]) n.textContent = T()[k]; });
    const langBtn = $('#langBtn'); if (langBtn) langBtn.textContent = state.lang === 'hi' ? 'EN' : 'हिं';
    paintUser();
    const view = $('#view'); if (!view) return;
    view.innerHTML = '';
    view.appendChild(VIEWS[state.tab]());
    view.scrollTop = 0;
  }

  /* --------------------------- auth screen ------------------------------ */
  let authMode = 'signin';

  function setAuthMode(mode) {
    authMode = mode;
    $$('#authSeg .seg-btn').forEach((b) => b.classList.toggle('active', b.dataset.auth === mode));
    $('#fName').hidden = mode !== 'signup';
    $('#fShop').hidden = mode !== 'signup';
    $('#fPin').hidden = mode !== 'signup';
    $('#passHint').hidden = mode !== 'signup';
    $('#auPass').setAttribute('autocomplete', mode === 'signup' ? 'new-password' : 'current-password');
    $('#authSubmit').textContent = mode === 'signup' ? T().signUp : T().signIn;
    $('#authError').hidden = true;
  }

  function showAuthError(msg) {
    const box = $('#authError');
    box.textContent = msg; box.hidden = false;
  }

  async function submitAuth(e) {
    if (e) e.preventDefault();
    const email = $('#auEmail').value.trim();
    const pass = $('#auPass').value;
    try {
      let user;
      if (authMode === 'signup') {
        user = await Auth.signup({
          name: $('#auName').value, email, shop: $('#auShop').value,
          password: pass, pin: $('#auPin').value.trim()
        });
      } else {
        user = await Auth.signin(email, pass);
      }
      enterApp(user);
    } catch (err) { showAuthError(err.message); }
  }

  function enterApp(user) {
    state.user = user;
    state.q = ''; state.date = ''; state.method = ''; state.status = ''; state.tab = 'tx';
    load();
    $('#authScreen').hidden = true;
    $('#mainScreen').hidden = false;
    render();
  }

  function signOut() {
    Auth.signout();
    state.user = null; state.txns = []; state.qr = null;
    $('#mainScreen').hidden = true;
    $('#authScreen').hidden = false;
    $('#authForm').reset();
    setAuthMode('signin');
  }

  /* ------------------------------- init --------------------------------- */
  function init() {
    // tabs
    $$('.tab').forEach((b) => b.onclick = () => go(b.dataset.tab));
    $('#langBtn').onclick = () => {
      state.lang = state.lang === 'hi' ? 'en' : 'hi';
      localStorage.setItem(STORE_LANG, state.lang);
      render();
    };
    $('#logoutBtn').onclick = signOut;
    $('#userChip').onclick = () => go('settings');

    // auth screen
    $$('#authSeg .seg-btn').forEach((b) => b.onclick = () => setAuthMode(b.dataset.auth));
    $('#authForm').onsubmit = submitAuth;
    $('#demoBtn').onclick = async () => {
      try {
        const user = await Auth.signin('demo@paycheck.app', 'demo1234');
        enterApp(user);
      } catch { showAuthError('Demo account is not available in this browser.'); }
    };
    if (!Auth.hasSubtle) {
      const note = $('#cryptoNote');
      note.hidden = false;
      note.textContent = 'Note: Web Crypto is unavailable here (use http://localhost or https), so passwords use a weaker fallback hash.';
    }
    setAuthMode('signin');

    // resume session
    const existing = Auth.current();
    if (existing) enterApp(existing);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
