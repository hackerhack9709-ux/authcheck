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

## Honest limits

- No tool proves truth. The score is about the *artefact*, not the claim.
- Missing credentials are normal and are treated as neutral, never as proof of faking.
- Watermarks can be stripped, so provenance is weighted above watermark absence.
- Detection degrades against new generators — that is why signals are blended.

## Licence

MIT
