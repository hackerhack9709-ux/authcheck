# PayCheck — UPI payment verification app

A mobile-first web app that helps a shopkeeper **verify a payment before handing over the goods**.
Inspired by the anti-fraud reel: *"Check the payment first, then hand over the goods."*

No build step. No frontend framework — vanilla HTML + CSS + JS. An optional
zero-dependency Node server adds the Razorpay proxy; without it the app runs
fully offline in sandbox mode.

## Run it

Simplest — the zero-dependency Node server (serves the app **and** the Razorpay proxy):

```bash
npm start
# open http://localhost:8080
```

Static only, no gateway proxy:

```bash
python3 -m http.server 12000
# open http://localhost:12000
```

Sign in with the demo account (`demo@paycheck.app` / `demo1234`) or create your own.

> Passwords are hashed with PBKDF2-SHA256 via Web Crypto. This is a **client-side demo**:
> it isolates each user's local data on a shared device. It is not server-grade security.

## Tabs

| Tab | What it does |
|-----|--------------|
| **Payments** | Summary totals, search, status/method/date filters, day grouping, detail modal, delete |
| **Add** | Record a payment manually |
| **Verify** | Risk check + live payment-gateway check → Safe / Caution / Danger, with WhatsApp sharing |
| **QR** | Generate a real UPI collect QR (`upi://pay?...`) and send the request on WhatsApp |
| **Settings** | Merchant profile, gateway config, password/PIN, export/import, demo reset |

## How verification works

Two independent layers:

1. **Your records** — UPI ID format, known vs new payer, duplicate amount, large/round amount,
   past failed payments, UTR format (12 digits).
2. **Payment gateway** — `gateway.js` calls your verification endpoint and normalises the response.

Final verdict: `SUCCESS` clears the record warnings; `FAILED`/`NOT_FOUND` forces **Danger**;
`PENDING`/`UNKNOWN` keeps it at **Caution**.

### Gateway modes

- **Sandbox** (default) — offline deterministic simulator, no network. The badge on the Verify tab
  shows which mode is active.
- **Live** — set your endpoint URL, API key, auth style (`bearer` / `x-api-key` / `query` / `basic`) and
  timeout in **Settings**. The app POSTs:

```json
{ "payee": "...", "vpa": "...", "amount": 2000, "utr": "402730210114", "date": "2026-11-10" }
```

and reads back any common shape (`status` / `state` / `paymentStatus` / `result` / `code`,
plus `referenceId`, `utr`, `payerName`, `amount`, `bank`, ...).

No credentials ship with the app. Yours are stored only in this browser.

## Deploy it (so it isn't stuck on your laptop)

The Node server serves the static app **and** the Razorpay proxy from one
process, so a single container is all you need. `Dockerfile` and
`render.yaml` are ready.

**Render (free tier)**

1. Push this repo to GitHub.
2. Render → **New → Blueprint**, pick the repo. It reads `render.yaml`.
3. Fill the four secrets it prompts for (see `.env.example`):
   `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `PROXY_USER`, `PROXY_PASS`.

**Railway / Fly.io / any Docker host**

```bash
docker build -t paycheck .
docker run -p 8080:8080 \
  -e RAZORPAY_KEY_ID=rzp_live_xxx \
  -e RAZORPAY_KEY_SECRET=xxxxxxxx \
  -e PROXY_USER=merchant \
  -e PROXY_PASS=$(openssl rand -hex 16) \
  paycheck
```

Then in the app's **Settings**: provider `Razorpay (via your proxy)`, mode
`Live API`, endpoint `https://YOUR-HOST/api/razorpay/verify`, API key =
`PROXY_USER`, API secret = `PROXY_PASS`.

> Set `PROXY_PASS` to something long and random. Without it the proxy is open,
> and anyone who finds the URL could look up payments with your Razorpay keys.
> `/api/health` tells you whether credentials and proxy auth are on.

### Deploy checklist

- [ ] `PROXY_PASS` is long and random — never left as `change-me-to-something-long`
- [ ] Razorpay keys are **live** keys (`rzp_live_…`) in production, test keys in staging
- [ ] `curl https://YOUR-HOST/api/health` → `{"ok":true,"razorpayConfigured":true,"proxyAuth":true}`
- [ ] `curl -i https://YOUR-HOST/api/razorpay/verify/pay_x` → `401` (proxy is gated)
- [ ] App served over **HTTPS** — a UPI tool on plain HTTP is a phishing lookalike

## Files

```
index.html            shell: auth screen, topbar, 5-tab bar
styles.css            dark UPI-style theme
auth.js               accounts + session (PBKDF2), per-user data scoping
gateway.js            payment verification adapter (sandbox + live)
share.js              WhatsApp / native share / clipboard helpers
icons.js              hand-drawn single-stroke SVG icon set
app.js                i18n (English + Hindi), state, views, verification logic
sw.js                 service worker (stale-while-revalidate)
vendor/qrcode.min.js  QR generator (local, no CDN)
server/razorpay-verify.js  static host + Razorpay proxy (zero deps, Node 18+)
Dockerfile            single-container deploy (app + proxy)
render.yaml           Render blueprint
.env.example          server environment template
```

## Language

English is the default. The `हिं` button in the top bar switches to Hindi.
