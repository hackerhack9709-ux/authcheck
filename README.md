# AuthCheck

A free, explainable authenticity desk. Give it an **image**, a **claim**, or an
**audio clip**, and it returns a trust score **with every reason behind it** —
never a bare yes or no.

## Why

Anyone can now generate a convincing fake photo, voice note or headline.
Ordinary people have no tool that answers *"is this real?"* and shows its
working. Journalists have InVID, enterprises have paid APIs — there is nothing
free, multilingual and explainable for the general public.

## Signals

| # | Signal | What it does |
|---|--------|--------------|
| 1 | C2PA / Content Credentials | Detects signed provenance and manifest completeness |
| 2 | EXIF metadata | Camera, software, GPS, capture date |
| 3 | AI tool signatures | Midjourney, DALL·E, Firefly, SD, ComfyUI, … |
| 4 | Error Level Analysis | Visualises locally edited regions |
| 5 | Generation heuristics | Generator dimensions, square canvases, missing metadata, noise |
| 6 | Claim language | Forward-bait, unnamed experts, absolutism, share requests |
| 7 | Fact-check lookup | Google Fact Check Tools API (optional key) |
| 8 | Audio forensics | TTS signatures, clipping, RMS, silent-segment stitching |
| 9 | Multilingual | English, Hindi, Urdu, Bengali, Marathi, Tamil, Spanish |

Every finding carries an explicit weight. The score is a weighted fusion, and
the full reason list is always shown.

## Run locally

```bash
pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 12000
# open http://localhost:12000
```

## Deploy

- **Render:** connect the repo; `render.yaml` is included.
- **Docker:** `docker build -t authcheck . && docker run -p 8000:8000 authcheck`
- **Any PaaS:** start command `python -m uvicorn app:app --host 0.0.0.0 --port $PORT`

## API

```bash
curl -X POST <base>/api/analyze-image -F "file=@photo.jpg"
curl -X POST <base>/api/analyze-audio -F "file=@voice.wav"
curl -X POST <base>/api/check-text  --data-urlencode "text=<claim>"
curl <base>/api/health
```

Optional environment variable:

| Name | Purpose |
|------|---------|
| `FACTCHECK_API_KEY` | Enables the Google Fact Check Tools lookup |

## One-click control room

Everything runs from a single panel:

```bash
./start.sh --test          # install deps, self-test, start, print every link
```

Then open `/panel`. Every button performs a real action:

| Button | What it does |
|--------|--------------|
| Run Self-Test | Executes the 9 engine checks and shows pass/fail per check |
| Check Live Site | Probes `/` and `/api/health` on the public URL |
| Automation Status | Shows the daily job state and the last 5 runs |
| Run Automation Now | Dispatches the daily job immediately |
| Toggle Automation | Turns the daily job on or off |
| Share Links | Builds WhatsApp / Telegram links and copy text |
| Full Status | Routes, files, python version, uptime |
| Download Everything | Zips the whole project for backup or hand-off |
| Permanent Deploy | Copyable GitHub + Render steps |

Stop with `./start.sh --stop`.

### PIN protection

Set `PANEL_PIN` to lock the action buttons. `start.sh` generates a 6-digit PIN
into `.panel_pin` on first run and reuses it afterwards. With `PANEL_PIN` unset
the panel is open — only do that on a private machine.

## What it checks

| Layer | Input | Notes |
|-------|-------|-------|
| Provenance (C2PA) | image, video frame | Cryptographic, strongest signal |
| EXIF metadata | image, video frame | Camera, GPS, editing software |
| Error Level Analysis | image, video frame | Localised edits show up |
| Generation heuristics | image, video frame | Canvas size, noise profile |
| AI tool signatures | image, audio, video | Generator names in metadata |
| Claim language | text | Forward-bait, absolutism, caps |
| Multilingual lexicons | text | en, hi, ur, bn, mr, ta, es |
| Audio forensics | audio | TTS signatures, clipping, stitching |
| Video container | video | Codec, fps, aspect, audio track |
| References | text | Keyless Wikipedia + DuckDuckGo; optional Google Fact Check key |

## API

```
POST <base>/api/analyze-image   -F "file=@photo.jpg"
POST <base>/api/analyze-video   -F "file=@clip.mp4"
POST <base>/api/analyze-audio   -F "file=@voice.wav"
POST <base>/api/check-text      --data-urlencode "text=<claim>"
GET  <base>/api/health
```

Video needs an ffmpeg binary. `pip install imageio-ffmpeg` bundles a static one,
so no system package is required.

## Honest limits

- No tool proves truth. The score is about the *artefact*, not the claim.
- Missing credentials are normal and are treated as neutral, never as proof of faking.
- Watermarks can be stripped, so provenance is weighted above watermark absence.
- Detection degrades against new generators — that is why signals are blended.

## Licence

MIT
