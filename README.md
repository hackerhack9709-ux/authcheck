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
GET  <base>/api/health
```

Optional environment variable:

| Name | Purpose |
|------|---------|
| `FACTCHECK_API_KEY` | Adds the Google Fact Check Tools lookup on top of the keyless references |
| `PANEL_PIN` | Locks the control-room action buttons |

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
