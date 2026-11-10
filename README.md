# PayCheck — UPI payment verification app

A mobile-first web app that helps a shopkeeper **verify a payment before handing over the goods**.
Inspired by the anti-fraud reel: *"Check the payment first, then hand over the goods."*

No build step. No backend. Vanilla HTML + CSS + JS.

## Run it

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
- **Live** — set your endpoint URL, API key, auth style (`bearer` / `x-api-key` / `query`) and
  timeout in **Settings**. The app POSTs:

```json
{ "payee": "...", "vpa": "...", "amount": 2000, "utr": "402730210114", "date": "2026-11-10" }
```

and reads back any common shape (`status` / `state` / `paymentStatus` / `result` / `code`,
plus `referenceId`, `utr`, `payerName`, `amount`, `bank`, ...).

No credentials ship with the app. Yours are stored only in this browser.

## Files

```
index.html            shell: auth screen, topbar, 5-tab bar
styles.css            dark UPI-style theme
auth.js               accounts + session (PBKDF2), per-user data scoping
gateway.js            payment verification adapter (sandbox + live)
share.js              WhatsApp / native share / clipboard helpers
app.js                i18n (English + Hindi), state, views, verification logic
vendor/qrcode.min.js  QR generator (local, no CDN)
```

## Language

English is the default. The `हिं` button in the top bar switches to Hindi.
