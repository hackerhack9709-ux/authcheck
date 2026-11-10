# AGENTS.md — PayCheck

Repository-specific notes for AI agents working in this codebase.

## What this is
A single-page, dependency-light web app. The frontend is **static** (no build step, no framework);
an optional zero-dependency Node server adds the Razorpay verification proxy and serves the same
static files, so the whole thing deploys as one container.
It is a UPI payment-verification helper for shopkeepers, inspired by an anti-fraud Instagram reel
("Check the payment first, then hand over the goods").

## Layout
```
index.html            shell: auth screen, topbar, <main id="view">, 5-tab bottom bar
styles.css            dark UPI-style theme; CSS variables in :root
auth.js               window.Auth  — accounts, PBKDF2 hashing, session, per-user data keys
gateway.js            window.Gateway — payment verification adapter (sandbox + live)
share.js              window.Share — WhatsApp / native share / clipboard
icons.js              window.Icon — hand-drawn single-stroke SVG icon set
app.js                everything else: i18n, state, views, verification logic, QR
sw.js                 service worker (stale-while-revalidate)
vendor/qrcode.min.js  qrcode-generator 1.4.4 (vendored; global `qrcode`)
server/razorpay-verify.js  static host + Razorpay proxy (Node 18+ built-ins only)
Dockerfile            single-container deploy (app + proxy)
render.yaml           Render blueprint; .env.example documents the server env
```

## Run / verify
```bash
npm start                        # app + proxy on http://localhost:8080
python3 -m http.server 12000     # static only, no proxy
npm run check                    # node --check across every JS file
```
There is **no automated test suite**. Verify changes by loading the page and exercising the
five tabs. Preview hosts: see `work_hosts` (ports 12000 / 12001).

The proxy needs `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `PROXY_USER`, `PROXY_PASS`. Set
`RAZORPAY_API_BASE` to point at a stub during testing. `/api/health` reports whether
credentials and proxy auth are on. **Never leave the proxy unauthenticated** — it spends your
Razorpay keys on behalf of anyone who reaches the URL.

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

## Deployment (live)
- GitHub: `hackerhack9709-ux/authcheck`, branch **`paycheck`** (repo `main` is a different app — never merge/push PayCheck there).
- Render service: `paycheck` → https://paycheck-5amq.onrender.com (Docker, free plan, `paycheck` branch).
- Env on Render: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `PROXY_USER`, `PROXY_PASS`.
- To redeploy after changes: commit on `master`, then `git push origin master:paycheck`.
- Razorpay creds currently on the service were leaked (found in a public "brute force" key list) — rotate them in the Razorpay dashboard.

## Security hardening (2026-11)
- The static server serves an **allowlist** (`PUBLIC_FILES` in `server/razorpay-verify.js`).
  Previously it served any file under `ROOT`, so `/.env` (Razorpay secret + proxy password),
  `/.git/`, `/server/` source and docs were readable over HTTP. When adding a new asset, add
  its path to `PUBLIC_FILES` or it will 404.
- `index.html` and `sw.js` are sent with `Cache-Control: no-cache`; other assets use a 5-min max-age.
- `sw.js` is **network-first** (cache is only an offline fallback). A stale-while-revalidate cache
  kept serving the previous `app.js` for one extra load after a deploy.
- `buildUpi()` keeps `@` literal and encodes spaces as `%20` (not `%40`/`+`) — some UPI apps
  fail to parse the percent-encoded forms.
