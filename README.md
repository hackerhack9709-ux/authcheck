# AuthCheck

A free, explainable authenticity desk. Give it an **image**, a **video**, an
**audio clip**, or a **claim**, and it returns a trust score **with every reason
behind it** — never a bare yes or no.

## Why

Anyone can now generate a convincing fake photo, voice note or headline.
Ordinary people have no tool that answers *"is this real?"* and shows its
working. Journalists have InVID, enterprises have paid APIs — there is nothing
free, multilingual and explainable for the general public.

## Signals

| # | Signal | Input | What it does |
|---|--------|-------|--------------|
| 1 | C2PA / Content Credentials | image, video frame | Signed provenance and manifest completeness |
| 2 | EXIF metadata | image, video frame | Camera, software, GPS, capture date |
| 3 | AI tool signatures | image, audio, video | Midjourney, DALL·E, Firefly, SD, ElevenLabs, Runway, … |
| 4 | Error Level Analysis | image, video frame | Visualises locally edited regions |
| 5 | Generation heuristics | image, video frame | Generator dimensions, square canvases, noise profile |
| 6 | Claim language | text | Forward-bait, unnamed experts, absolutism, share requests |
| 7 | Claim references | text | Keyless Wikipedia + DuckDuckGo; optional Google Fact Check key |
| 8 | Audio forensics | audio | TTS signatures, clipping, RMS, silent-segment stitching |
| 9 | Video container | video | Codec, frame rate, aspect ratio, audio track, keyframe sampling |
| 10 | Multilingual | text | English, Hindi, Urdu, Bengali, Marathi, Tamil, Spanish |

Every finding carries an explicit weight. The score is a weighted fusion, and
the full reason list is always shown.

## Run locally

```bash
./start.sh --test          # install deps, self-test, start, print every link
./start.sh --stop          # stop
```

Or by hand:

```bash
pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 12000
# open http://localhost:12000
```

## Deploy

- **Render:** connect the repo; `render.yaml` is included.
- **Docker:** `docker build -t authcheck . && docker run -p 8000:8000 authcheck`
- **Any PaaS:** start command `python -m uvicorn app:app --host 0.0.0.0 --port $PORT`

Video support needs no system package: `imageio-ffmpeg` (in `requirements.txt`)
ships a static ffmpeg binary. This is verified inside the Docker image.

## API

```
POST <base>/api/analyze-image   -F "file=@photo.jpg"
POST <base>/api/analyze-video   -F "file=@clip.mp4"
POST <base>/api/analyze-audio   -F "file=@voice.wav"
POST <base>/api/check-text      --data-urlencode "text=<claim>"
GET  <base>/api/tiers
GET  <base>/api/usage
GET  <base>/api/health
```

### Access tiers and quotas

The four analysis endpoints are metered on a sliding one-hour window. A request
without a key still works; it just uses the anonymous quota, so a missing or
invalid key is never an error.

| Tier | How you get it | Checks / hour |
|------|----------------|---------------|
| Anonymous | no key, limited by client IP | 20 |
| Free | key issued on the free tier | 120 |
| Pro | paid — Starter, ₹99/month | 2000 |
| Desk | paid — Pro desk, ₹499/month | 10000 |

Send the key as an `X-API-Key` header:

```
curl -H "X-API-Key: ac_…" <base>/api/usage
```

Every metered response carries `X-RateLimit-Tier`, `X-RateLimit-Limit` and
`X-RateLimit-Remaining`. Over the limit returns `429` with `Retry-After`.

Keys are created and revoked from the control room (`/panel` → API Keys). They
are stored through `db.py`, which uses Postgres when `AUTHCHECK_DATABASE_URL` is
set and SQLite under `data/` otherwise. **On a host with an ephemeral filesystem
(Render's free plan, most containers) you must set `AUTHCHECK_DATABASE_URL`** —
otherwise a key issued after a payment is wiped on the next redeploy. Check
`GET /panel/api/keys` → `usage.storage`; it should read `postgres`. As a
last resort, `AUTHCHECK_API_KEYS` supplies static keys as `key:tier,key:tier`.

Paid keys carry a 30-day expiry. An expired key is rejected like a revoked one
and falls back to the anonymous quota; `keys.why_invalid()` reports `expired`
rather than `unknown` so the panel can say which.

Optional environment variables:

| Name | Purpose |
|------|---------|
| `FACTCHECK_API_KEY` | Adds the Google Fact Check Tools lookup on top of the keyless references |
| `PANEL_PIN` | Locks the control-room action buttons and the key-management endpoints |
| `AUTHCHECK_API_KEYS` | Static keys for read-only filesystems, e.g. `ac_abc:pro,ac_def:free` |
| `AUTHCHECK_DATABASE_URL` | Postgres connection string — **required in production** so keys survive restarts |
| `DATABASE_URL` | Alias for `AUTHCHECK_DATABASE_URL`; picked up automatically if present |
| `AUTHCHECK_DB` | Override the SQLite path (default `./data/authcheck.db`) |
| `AUTHCHECK_PUBLIC_URL` | Public base URL; used as the Razorpay callback target |
| `RAZORPAY_KEY_ID` | Razorpay key id — enables checkout |
| `RAZORPAY_KEY_SECRET` | Razorpay key secret — enables checkout |
| `RAZORPAY_WEBHOOK_SECRET` | Verifies webhook signatures before a key is issued |

### Selling keys (Razorpay)

Plans live in `billing.py` (`starter` ₹99 → pro tier, `pro` ₹499 → desk tier).
A buyer clicks Buy on the landing page, we open a Razorpay Payment Link with the
plan in its notes, and Razorpay calls `POST /billing/webhook` on payment. The
webhook signature is verified with `RAZORPAY_WEBHOOK_SECRET`, then a key is
issued on the matching tier and shown on `/billing/success`. Fulfilment is
idempotent, so replayed webhooks return the same key.

Point Razorpay's webhook at `https://<your-host>/billing/webhook` and subscribe
to `payment_link.paid`. Add it in the Razorpay dashboard — their REST API
rejects webhook creation from a script. Without the three Razorpay variables the
checkout endpoint reports exactly which ones are missing instead of failing
silently.

Renewals reuse the same key. A purchase stores a `renew_key`; the panel's
**Renew** button opens a link whose reference is `renew-<renew_key>`, and
`fulfil_payment` extends the existing key by 30 days instead of minting a new
one, so the customer never swaps credentials.

### When the webhook does not arrive

Razorpay only lets you add a webhook by hand in its dashboard, so a paid link can
sit unfulfilled — the buyer pays and gets nothing. The control room's
**Payments → Reconcile** button closes that gap: it asks Razorpay which pending
links are paid and issues the missing keys. The post-payment page also settles
itself, so a buyer who returns to it is served without any webhook.

Run Reconcile after every billing deploy and check that no purchase is left
unpaid.

### Winning teams (free-key requests)

`/for-teams` is the B2B page: the pitch, the use cases, API samples in curl,
Python and JavaScript, the pricing, and a request form. Submitting it calls
`POST /api/request-key`, which stores the lead through `leads.py` (same Postgres
or SQLite store as everything else). Nothing is issued automatically — open
**Key Requests** in the control room and mint a key per request; the plan the
visitor asked for is mapped to its tier for you.

`OUTREACH.md` is the playbook: who to approach, what to say, and how to handle
the replies.

## One-click control room

Everything runs from a single panel. Open `/panel`. Every button performs a real
action:

| Button | What it does |
|--------|--------------|
| Run Self-Test | Executes the engine checks and shows pass/fail per check |
| Check Live Site | Probes `/` and `/api/health` on the public URL |
| Automation Status | Shows the daily job state and the last 5 runs |
| Run Automation Now | Dispatches the daily job immediately |
| Toggle Automation | Turns the daily job on or off |
| Share Links | Builds WhatsApp / Telegram links and copy text |
| API Keys | Creates, lists and revokes free/pro/desk API keys |
| Payments | Razorpay status, plan catalogue, recent purchases, reconcile |
| Key Requests | Inbound free-key requests from `/for-teams`, issue in one click |
| Full Status | Routes, files, python version, uptime |
| Download Everything | Zips the whole project for backup or hand-off |
| Permanent Deploy | Copyable GitHub + Render steps |

### PIN protection

Set `PANEL_PIN` to lock the action buttons. `start.sh` generates a 6-digit PIN
into `.panel_pin` on first run and reuses it afterwards. With `PANEL_PIN` unset
the panel is open — only do that on a private machine.

## Honest limits

- No tool proves truth. The score is about the *artefact*, not the claim.
- A background reference is not evidence: a hit means "here is context", never
  "this claim is true".
- Missing credentials are normal and are treated as neutral, never as proof of faking.
- Watermarks can be stripped, so provenance is weighted above watermark absence.
- Video is weaker than stills: there is no lip-sync or temporal-consistency
  model, only container facts and sampled keyframes.
- Detection degrades against new generators — that is why signals are blended.

## Licence

MIT
