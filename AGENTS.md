# AGENTS.md — PayCheck (पेचेक)

Repository-specific notes for AI agents working in this codebase.

## What this is
A single-page, dependency-light **static web app** (no build step, no backend, no framework).
It is a UPI payment-verification helper for shopkeepers, inspired by an anti-fraud Instagram reel
("Payment pehle check kare, phir maal de" / "ऑनलाइन धोखाधड़ी से सावधान").

## Layout
```
index.html          shell: topbar, <main id="view">, bottom tabbar
styles.css          dark UPI-style theme; CSS variables in :root
app.js              everything: i18n, state, views, verification logic, QR
vendor/qrcode.min.js  qrcode-generator 1.4.4 (vendored locally; global `qrcode`)
README.md           user-facing docs (Hindi + English)
```

## Run / verify
```bash
python3 -m http.server 12000     # then open http://localhost:12000
node --check app.js              # syntax check (no test suite exists)
```
There is **no automated test suite**. Verify changes by loading the page and exercising the
four tabs. Preview hosts: see `work_hosts` (ports 12000 / 12001).

## Conventions
- Vanilla ES2018+ in a single IIFE in `app.js`. No modules, no bundler, no npm deps at runtime.
- DOM is built with the small helpers `el(tag, cls, html)`, `$(sel, root)`, `esc()`.
  **Always `esc()` user/data strings** before injecting into `innerHTML`.
- All user-visible strings live in the `I18N` object under `hi` and `en`. When adding UI text,
  add keys to **both** locales and reference via `T().key`. The `data-i18n` attribute on static
  HTML nodes is synced on each render.
- State lives in the `state` object; `render()` re-renders the active view from scratch.
  Transaction data persists in `localStorage` under `paycheck.txns.v1`.
- Views are functions `viewTx / viewAdd / viewVerify / viewQr` registered in the `VIEWS` map.
- Keep the transaction list re-render cheap: search typing calls `txnList()` and swaps only the
  `#txn-list` node instead of a full `render()`.

## Domain notes
- UPI VPA format is validated by `VPA_RE` (`local@handle`).
- `runChecks()` returns `{verdict: 'ok'|'pend'|'bad', advice, checks[]}`. Verdict is `bad` if any
  check is `bad`, else `pend` if any is `warn`, else `ok`.
- `buildUpi()` produces `upi://pay?pa=..&pn=..&am=..&cu=INR&tn=..`.
- This app never contacts a real bank/UPI server — it only reasons over local records. Any change
  that implies real payment confirmation must keep the "confirm in your bank app" disclaimer.

## Do not
- Do not add a bundler, framework, or npm runtime dependency; the project must stay open-and-run.
- Do not load scripts from a CDN at runtime (the QR lib is vendored for offline/air-gapped use).
