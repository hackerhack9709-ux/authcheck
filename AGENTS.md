# AGENTS.md — PayCheck

Repository-specific notes for AI agents working in this codebase.

## What this is
A single-page, dependency-light **static web app** (no build step, no backend, no framework).
It is a UPI payment-verification helper for shopkeepers, inspired by an anti-fraud Instagram reel
("Check the payment first, then hand over the goods").

## Layout
```
index.html            shell: auth screen, topbar, <main id="view">, 5-tab bottom bar
styles.css            dark UPI-style theme; CSS variables in :root
auth.js               window.Auth  — accounts, PBKDF2 hashing, session, per-user data keys
gateway.js            window.Gateway — payment verification adapter (sandbox + live)
share.js              window.Share — WhatsApp / native share / clipboard
app.js                everything else: i18n, state, views, verification logic, QR
vendor/qrcode.min.js  qrcode-generator 1.4.4 (vendored; global `qrcode`)
```

## Run / verify
```bash
python3 -m http.server 12000     # then open http://localhost:12000
for f in app.js auth.js gateway.js share.js; do node --check $f; done
```
There is **no automated test suite**. Verify changes by loading the page and exercising the
five tabs. Preview hosts: see `work_hosts` (ports 12000 / 12001).

Important: Web Crypto (`crypto.subtle`) only exists in a secure context. Use `localhost` or https,
otherwise `auth.js` falls back to a weak hash and shows a warning.

## Conventions
- Vanilla ES2018+ IIFEs. No modules, no bundler, no npm runtime dependency.
- DOM helpers: `el(tag, cls, html)`, `$(sel, root)`, `$$`, `esc()`. **Always `esc()` data** before
  injecting into `innerHTML`.
- All user-visible strings live in `I18N` under `en` (default) and `hi`. Add keys to **both**
  locales and reference via `T().key`. Static nodes use `data-i18n` and are synced each render.
- State lives in `state`; `render()` re-renders the active view. Views are `viewTx / viewAdd /
  viewVerify / viewQr / viewSettings` in the `VIEWS` map.
- Search typing swaps only the `#txn-list` node, not a full `render()`.
- Storage keys are scoped per user via `Auth.dataKey(base, userId)`. Never read a business-data
  key without a user id.
- `load()` reads the signed-in user's transactions (falling back to `seed()`), QR draft, and meta.

## Domain notes
- `runChecks(input)` returns `{checks[]}` (local record checks). `verdictFor(checks, gw)` combines
  them with a gateway result into `{verdict: 'ok'|'pend'|'bad', advice}`.
- Gateway results are normalised to `SUCCESS | PENDING | FAILED | NOT_FOUND | UNKNOWN` by
  `Gateway.normaliseStatus`, with field extraction via `Gateway.pick`.
- `buildUpi()` produces `upi://pay?pa=..&pn=..&am=..&cu=INR&tn=..`.
- This app never contacts a real bank unless the user configures a live endpoint in Settings.
  Any change implying real payment confirmation must keep the "confirm in your bank app" advice.

## Do not
- Do not add a bundler, framework, or npm runtime dependency.
- Do not load scripts from a CDN at runtime (the QR lib is vendored for offline use).
- Do not commit API keys; gateway secrets live only in the user's browser localStorage.
