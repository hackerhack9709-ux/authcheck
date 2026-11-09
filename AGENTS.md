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
  static/index.html   single-file frontend (no build step)
  requirements.txt / render.yaml / Dockerfile   deployment
  README.md / PRD-authcheck.md / RESEARCH-authenticity-apps.md
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

- `render.yaml` and `Dockerfile` are ready.
- **Blocker:** the workspace `GITHUB_TOKEN` is a GitHub App token scoped to
  `hackerhack9709-ux/apnavault` only. It **cannot create repositories**. To get a
  permanent public URL, the user must create a repo (e.g. `authcheck`) and grant
  access, or connect Render directly to a new repo.
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
