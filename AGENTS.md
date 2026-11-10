# AGENTS.md — AuthCheck

Repo memory for future sessions. Keep it short and current.

## What this is

A free, explainable content-authenticity desk. Give it an image, an audio clip
or a claim, and it returns a 0–100 trust score **with every reason behind it**.
Deployed as a FastAPI web app; also packaged as a no-LLM automation.

## Layout

```
authcheck/
  core.py         framework-free analysis engine (all signal logic lives here)
  app.py          FastAPI HTTP layer over core.py
  keys.py         API-key tiers, expiry and metering
  billing.py      Razorpay payment links, webhook fulfilment, renewal
  leads.py        inbound free-key requests from the /for-teams page
  db.py           storage layer: Postgres when AUTHCHECK_DATABASE_URL is set, else SQLite
  panel.py        control room router (/panel)
  static/index.html   single-file frontend (no build step)
  static/teams.html   B2B landing page served at /for-teams
  static/panel.html   control room UI
  requirements.txt / render.yaml / Dockerfile   deployment
  DEPLOY.md / README.md / OUTREACH.md / PRD-authcheck.md / RESEARCH-authenticity-apps.md
authcheck-automation/
  core.py         copy of the engine (keep in sync)
  selftest.py     deterministic self-test, 9 checks, no LLM
  main.py         automation entrypoint
```

## Architecture rules

- **All analysis logic belongs in `core.py`.** `app.py` must stay a thin HTTP
  wrapper. The automation reuses the same engine, so a fix in `core.py` must be
  copied to `authcheck-automation/core.py`.
- The engine is pure: functions take `bytes` / `str` and return dicts.
- No ML models are used. Signals are metadata, C2PA markers, ELA, heuristics
  and (for audio) PCM statistics. Keep it dependency-light.

## Scoring convention

`score` = **trust**, 0–100. Higher is safer.

- Positive heuristic `weight` = risk signal → subtracts from trust.
- Negative heuristic `weight` = authenticity evidence → adds to trust.
- Start at 50; C2PA present adds 30; ELA hot-spots subtract 10.
- Bands: `>=70` lower risk, `>=45` unclear, else higher risk.

Do not flip this convention. It was inverted once and produced nonsense.

## Run and test

```bash
pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 12000
python ../authcheck-automation/selftest.py     # 9 checks, must all pass
```

## Frontend

`static/index.html` is a single file — hand-written CSS, no framework, no
build. Aesthetic is "forensic evidence dossier": ink black, safelight amber,
Bricolage Grotesque / Newsreader / IBM Plex Mono, exhibit labels, grain and
scanline overlays. Keep that direction; do not revert to generic dark-blue
cards.

## Deployment state

- Live on Render: **https://authcheck-u1e8.onrender.com** (service
  `srv-dbovd99srm7s73d7d5cg`, free plan, oregon, auto-deploy from `main`).
- Storage is **Render Postgres** (`authcheck-db`, free, expires 2026-12-10) via
  `AUTHCHECK_DATABASE_URL`. The free Postgres expires after 30 days — replace it
  or move to a paid instance before then, or issued keys stop resolving.
- Razorpay runs in **test mode** (`rzp_test_...`). Switch to live keys after KYC.
- A free Render service still sleeps after inactivity; the first request after a
  nap is slow. That is unrelated to storage, which now survives restarts.
- `render.yaml` and `Dockerfile` are ready.
- The live `work-1-*` URL is runtime-session bound and dies with the session.

## Automation

`AuthCheck Daily Self-Test` — cron `0 6 * * *` Asia/Kolkata, `python3 main.py`,
no LLM, 300s timeout. Verifies the engine still produces the expected verdicts
on regenerated fixtures. Keep it no-LLM: it is deterministic by design.

**The automation sandbox is bare.** `core.py` imports Pillow, so the tarball
ships a `setup.sh` (`pip install pillow`) and the automation is created with
`setup_script_path: setup.sh`. Without it the run fails with
`ModuleNotFoundError: No module named 'PIL'`. Any new third-party import must
be added to `setup.sh` too.

After changing the tarball, upload it and PATCH the automation:

```bash
PATH=$(curl -s -X POST "$HOST/api/automation/v1/uploads?name=authcheck-selftest" \
  -H "Authorization: Bearer $OPENHANDS_API_KEY" -H "Content-Type: application/gzip" \
  --data-binary @authcheck-selftest.tar.gz | jq -r .tarball_path)
curl -X PATCH "$HOST/api/automation/v1/<id>" -H "Authorization: Bearer $OPENHANDS_API_KEY" \
  -H 'Content-Type: application/json' -d "{\"tarball_path\": \"$PATH\", \"setup_script_path\": \"setup.sh\"}"
```

Verify with a manual dispatch and poll `/runs` until the status is `COMPLETED`.

## Engine layers (v0.4)

`core.py` holds the whole engine as pure functions. Ten signals across four
modalities:

- image: `scan_c2pa`, `read_exif`, `ela`, `scan_signatures`, `ai_heuristics`
- audio: `analyze_audio_bytes` (container + TTS signatures + clipping/silence)
- video: `analyze_video_bytes` -> `probe_video` + `extract_keyframes`, then each
  keyframe is run through the image engine and fused
- text: `check_text` -> `detect_language`, `LEXICONS`, `lookup_references`

`VERSION` lives in `core.py` and is imported by `app.py` and `panel.py`. Change
it in one place only.

### ffmpeg

Video needs an ffmpeg binary. `_ffmpeg_path()` resolves in this order: the
`FFMPEG_BIN` env var, `PATH`, then the static binary bundled by
`imageio-ffmpeg`. Never shell out to `ffmpeg` by name - always go through
`_ffmpeg_path()`, or video silently breaks on hosts without it.

### References are not verdicts

`lookup_references()` is keyless (Wikipedia + DuckDuckGo) and returns background
only. The payload says so explicitly, and the UI repeats it. Never present a
reference hit as evidence that a claim is true.

## Control room (`/panel`)

`panel.py` is a separate router with one endpoint per button. `app.py` includes
it via `panel_router`. Keep every button backed by a real endpoint — no
decorative buttons.

- `selftest.py` lives in **both** the app dir and the automation dir. Keep them
  identical; the app copy is what the panel runs.
- `run_checks()` must call `CHECKS.clear()` first. `CHECKS` is module-level, so
  without it repeated runs accumulate (a real bug that showed 18/18).
- `PANEL_PIN` gates dispatch, toggle and export. Unset = open panel. `start.sh`
  writes `.panel_pin` (gitignored) and reuses it.
- `start.sh --test` is the one-command path: deps, self-test, start, links.

## Do not

- Do not add rate-limit or lockout bypass tooling, phishing pages, OTP grabbers
  or similar. This project is a defender tool; keep it that way.
- Do not commit `server.log`, `__pycache__` or generated tarballs.

## Storage, keys and payments (v0.5)

Every key and purchase query goes through `db.py`. With `AUTHCHECK_DATABASE_URL`
set it speaks Postgres; otherwise it falls back to SQLite at `AUTHCHECK_DB`
(`./data/authcheck.db`). Callers use `?` placeholders and one context manager;
`db.py` rewrites the placeholders and picks `ON CONFLICT` vs `INSERT OR REPLACE`.
**Never** reintroduce a bare `sqlite3.connect` — a free Render service has no
disk, so keys would be wiped on every redeploy.

- `keys.create_key(name, tier, days)` — `days=0` never expires; paid plans pass 30.
  Expired and revoked keys are both invalid, but `why_invalid()` distinguishes them.
- `keys.extend_key(key, days)` — renews in place, from now if already lapsed.
- `billing.PLANS` holds the prices. A reference of the form `renew-<renew_key>`
  extends the existing key instead of minting a new one; a plain reference issues
  a key and stores a `renew_key` for later.
- `billing.fulfil_payment()` is idempotent — replayed webhooks return the same key.
- Webhook HMAC is verified before anything is issued; `RAZORPAY_WEBHOOK_SECRET`
  must match the value in the Razorpay dashboard.

Razorpay's API refuses webhook creation from the CLI (a gateway quirk), so the
webhook is added once in the dashboard. Everything downstream of it is verified
end to end against the live service.

## Customer acquisition (v0.5)

Two surfaces feed the funnel, and `OUTREACH.md` is the playbook.

- `static/teams.html` at `/for-teams` is the B2B pitch: why teams, use cases,
  the API with curl/Python/JS samples, pricing, and a free-key request form.
- `POST /api/request-key` stores a request through `leads.py`. It is public, so
  it validates name and email and carries a hidden `website` honeypot field;
  a filled honeypot returns a fake success and stores nothing.
- Nothing is issued automatically. An operator opens **Key Requests** in the
  control room (`GET /panel/api/requests`) and mints a key with
  `POST /panel/api/requests/issue`, which marks the request issued.
- The request form asks for a *plan* (`free`/`starter`/`pro`); keys are minted
  on a *tier* (`free`/`pro`/`desk`). `billing.PLANS` holds that mapping —
  resolve through it, never assume the plan name is a tier name.

Razorpay activation (KYC) is the gate on real revenue: until the account is live,
checkout can only take test payments. See `OUTREACH.md` §0.
