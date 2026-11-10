# Deploying AuthCheck and switching on payments

The app is already on Render (`authcheck-u1e8.onrender.com`) with auto-deploy from
`main`. This file covers the two things the app cannot do for itself: publishing a
build and turning Razorpay on.

## 1. Publish a build

Render redeploys from `main` on its own, but the first deploy after a repo is
connected sometimes needs a nudge. To force one:

```bash
# Render API key from https://dashboard.render.com/u/settings#api-keys
export RENDER_KEY=rnd_xxxxxxxxxxxxxxxx
SERVICE=srv-xxxxxxxxxxxxxxxx

curl -s -X POST \
  -H "Authorization: Bearer $RENDER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"clearCache":"do_not_clear"}' \
  "https://api.render.com/v1/services/$SERVICE/deploys" | python3 -m json.tool
```

Watch it land:

```bash
curl -s -H "Authorization: Bearer $RENDER_KEY" \
  "https://api.render.com/v1/services/$SERVICE/deploys?limit=3" \
  | python3 -c "import sys,json;[print(d['deploy']['status'], d['deploy']['commit']['id'][:7]) for d in json.load(sys.stdin)]"
```

Confirm the build is live:

```bash
curl -s https://authcheck-u1e8.onrender.com/api/health     # version
curl -s https://authcheck-u1e8.onrender.com/api/tiers      # 404 on an old build
curl -s https://authcheck-u1e8.onrender.com/api/plans      # 404 on an old build
```

## 2. Turn on Razorpay

Create a Razorpay account, then **Settings → API Keys → Generate**. You get a key
id and a secret. Add both, plus a webhook secret you invent, to the Render service
under **Environment**:

| Variable | Value |
|---|---|
| `RAZORPAY_KEY_ID` | `rzp_live_...` (or `rzp_test_...` while testing) |
| `RAZORPAY_KEY_SECRET` | the secret shown once at generation |
| `RAZORPAY_WEBHOOK_SECRET` | any long random string you make up |
| `AUTHCHECK_PUBLIC_URL` | `https://authcheck-u1e8.onrender.com` |
| `AUTHCHECK_DATABASE_URL` | a Postgres connection string (see below) |

Save; Render restarts. `GET /api/plans` should now report `"configured": true`.

### Storage must be persistent

A free Render service has **no disk**. Keys written to SQLite are wiped on every
redeploy, so a customer pays, gets a key, and finds it dead after the next
deploy — this was observed on the live service before the fix.

Set `AUTHCHECK_DATABASE_URL` to any Postgres and every key and purchase is
stored there instead:

- **Render Postgres** (easiest, same network): Dashboard → **New → Postgres**,
  free plan, same region as the service. Copy the **Internal** connection string
  into `AUTHCHECK_DATABASE_URL`. The free instance expires after 30 days — plan
  to move to a paid one, or use a service that does not expire.
- **Neon / Supabase**: both have free tiers that do not expire. Copy their
  connection string, keeping `?sslmode=require`.

`GET /panel/api/keys` reports `usage.storage` — it should read `postgres`. If it
reads `sqlite`, the variable is missing or unreachable and keys are not durable.

Create a Render Postgres from the API if you prefer:

```bash
curl -s -X POST -H "Authorization: Bearer $RENDER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"authcheck-db","plan":"free","region":"oregon","version":"16","ownerId":"tea-..."}' \
  https://api.render.com/v1/postgres | python3 -m json.tool

# then, once status is "available":
curl -s -H "Authorization: Bearer $RENDER_KEY" \
  https://api.render.com/v1/postgres/<id>/connection-info | python3 -m json.tool
```

### Point the webhook at the app

Razorpay Dashboard → **Settings → Webhooks → Add**:

- URL: `https://authcheck-u1e8.onrender.com/billing/webhook`
- Secret: the same string as `RAZORPAY_WEBHOOK_SECRET`
- Event: `payment_link.paid`

Without this, money arrives but no key is issued.

## 3. Prove it end to end

1. Open the site, click **Buy Starter**, enter an email.
2. On the Razorpay page use test mode card `4111 1111 1111 1111`, any future expiry, any CVV.
3. You land on `/billing/success`, which polls until the webhook has issued the key.
4. Copy the key and check it:

```bash
curl -s -H "X-API-Key: ac_..." https://authcheck-u1e8.onrender.com/api/usage
# tier should be "pro" (Starter) or "desk" (Pro desk)
```

5. `/panel` → **Payments** should list the purchase with its issued key and a
   **Renew link** button.

## Notes

- Keys run for 30 days. Renewals reuse the same key via a `renew-<key>` reference,
  so a customer never has to swap credentials.
- `PANEL_PIN` is set on Render already; keep it private.
- Razorpay's REST API will not accept webhook creation from a script (it returns
  400 `json request could not be decoded` for every payload). Add the webhook in
  the dashboard as above; it is the one manual step.
