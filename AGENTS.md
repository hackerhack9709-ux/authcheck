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

## Do not

- Do not add rate-limit or lockout bypass tooling, phishing pages, OTP grabbers
  or similar. This project is a defender tool; keep it that way.
- Do not commit `server.log`, `__pycache__` or generated tarballs.
