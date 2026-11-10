#!/usr/bin/env node
/* =========================================================================
   PayCheck server — static host + Razorpay verification proxy.

   Why a proxy? Razorpay authenticates with key_id + key_secret over Basic
   auth. The secret must never reach a browser. So the browser calls this
   proxy, and this proxy talks to Razorpay with the secret held in the
   environment.

   Zero dependencies. Node 18+ (uses the global fetch).

   Run:
     RAZORPAY_KEY_ID=rzp_test_xxx \
     RAZORPAY_KEY_SECRET=xxxxxxxx \
     PROXY_USER=merchant PROXY_PASS=change-me \
     node server/razorpay-verify.js

   Then open http://localhost:8080 and, in Settings:
     provider   = razorpay
     mode       = live
     endpoint   = http://localhost:8080/api/razorpay/verify
     authStyle  = basic
     API key    = PROXY_USER      (not the Razorpay key)
     API secret = PROXY_PASS
   ========================================================================= */
'use strict';

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const PORT = Number(process.env.PORT || 8080);
const ROOT = path.resolve(__dirname, '..');

const RZP_KEY_ID = process.env.RAZORPAY_KEY_ID || '';
const RZP_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET || '';
/* Overridable so you can point at a mock/stub in tests. Defaults to Razorpay. */
const RZP_API_BASE = (process.env.RAZORPAY_API_BASE || 'https://api.razorpay.com').replace(/\/+$/, '');
const PROXY_USER = process.env.PROXY_USER || '';
const PROXY_PASS = process.env.PROXY_PASS || '';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8'
};

const send = (res, code, body, type = 'application/json; charset=utf-8') => {
  res.writeHead(code, { 'Content-Type': type, 'Cache-Control': 'no-store' });
  res.end(typeof body === 'string' || Buffer.isBuffer(body) ? body : JSON.stringify(body));
};

const cors = (res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Razorpay-Key-Id');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
};

/* --------------------------- proxy auth ------------------------------- */
function proxyAuthorised(req) {
  if (!PROXY_USER && !PROXY_PASS) return true; // open (local dev only)
  const hdr = req.headers.authorization || '';
  if (!hdr.startsWith('Basic ')) return false;
  let decoded = '';
  try { decoded = Buffer.from(hdr.slice(6), 'base64').toString('utf8'); } catch { return false; }
  const i = decoded.indexOf(':');
  const user = i === -1 ? decoded : decoded.slice(0, i);
  const pass = i === -1 ? '' : decoded.slice(i + 1);
  return user === PROXY_USER && pass === PROXY_PASS;
}

/* ------------------------ Razorpay lookup ----------------------------- */
async function fetchRazorpayPayment(paymentId) {
  if (!RZP_KEY_ID || !RZP_KEY_SECRET) {
    const e = new Error('Server is missing RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET.');
    e.status = 500;
    throw e;
  }
  const auth = Buffer.from(`${RZP_KEY_ID}:${RZP_KEY_SECRET}`).toString('base64');
  const url = RZP_API_BASE + '/v1/payments/' + encodeURIComponent(paymentId);

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 12000);
  let res, text;
  try {
    res = await fetch(url, { headers: { Authorization: 'Basic ' + auth }, signal: ctrl.signal });
    text = await res.text();
  } catch (err) {
    clearTimeout(timer);
    const e = new Error(err.name === 'AbortError' ? 'Razorpay timed out.' : 'Could not reach Razorpay.');
    e.status = 504;
    throw e;
  }
  clearTimeout(timer);

  let body;
  try { body = JSON.parse(text); } catch { body = { message: text.slice(0, 300) }; }

  if (res.status === 404) {
    // No such payment — surface as a clean not_found so the app can score it.
    return { payment: { id: paymentId, status: 'not_found' } };
  }
  if (!res.ok) {
    const desc = (body && body.error && body.error.description) || body.message || ('HTTP ' + res.status);
    const e = new Error(desc);
    e.status = res.status === 401 ? 502 : res.status;
    throw e;
  }
  return { payment: body };
}

/* ------------------------- route: verify ------------------------------ */
async function handleVerify(req, res, paymentId) {
  cors(res);
  if (req.method === 'OPTIONS') return send(res, 204, '');
  if (!proxyAuthorised(req)) {
    res.setHeader('WWW-Authenticate', 'Basic realm="PayCheck"');
    return send(res, 401, { status: 'UNKNOWN', message: 'Proxy auth required.' });
  }
  if (!/^pay_[A-Za-z0-9]+$/.test(paymentId || '')) {
    return send(res, 400, { status: 'UNKNOWN', message: 'Provide a Razorpay payment id (pay_...).' });
  }
  try {
    const { payment } = await fetchRazorpayPayment(paymentId);
    return send(res, 200, { payment });
  } catch (err) {
    return send(res, err.status || 500, { status: 'UNKNOWN', message: err.message });
  }
}

/* --------------------------- static files ----------------------------- */
function serveStatic(req, res, urlPath) {
  const rel = decodeURIComponent(urlPath === '/' ? '/index.html' : urlPath);
  const file = path.join(ROOT, rel);
  if (!file.startsWith(ROOT + path.sep)) return send(res, 403, { message: 'Forbidden' });
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) return send(res, 404, { message: 'Not found' });
    const type = MIME[path.extname(file).toLowerCase()] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': type });
    fs.createReadStream(file).pipe(res);
  });
}

/* ------------------------------- server ------------------------------- */
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const p = url.pathname;

  if (p === '/api/razorpay/verify' && req.method === 'POST') {
    let body = '';
    req.on('data', (c) => { body += c; if (body.length > 1e5) req.destroy(); });
    req.on('end', () => {
      let id = '';
      try {
        const j = JSON.parse(body || '{}');
        id = String(j.utr || j.paymentId || '').trim();
      } catch {}
      handleVerify(req, res, id);
    });
    return;
  }
  if (p.startsWith('/api/razorpay/verify/')) {
    return handleVerify(req, res, p.slice('/api/razorpay/verify/'.length).trim());
  }
  if (p === '/api/health') {
    return send(res, 200, {
      ok: true,
      razorpayConfigured: !!(RZP_KEY_ID && RZP_KEY_SECRET),
      proxyAuth: !!(PROXY_USER || PROXY_PASS)
    });
  }
  return serveStatic(req, res, p);
});

server.listen(PORT, () => {
  console.log(`PayCheck server on http://localhost:${PORT}`);
  console.log(`  Razorpay credentials: ${RZP_KEY_ID && RZP_KEY_SECRET ? 'configured' : 'MISSING (set RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET)'}`);
  console.log(`  Proxy auth: ${PROXY_USER || PROXY_PASS ? 'on' : 'OFF - set PROXY_USER/PROXY_PASS before exposing this to a network'}`);
});
