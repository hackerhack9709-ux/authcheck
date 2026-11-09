"""AuthCheck web app - HTTP layer over the framework-free analysis core."""
from __future__ import annotations

import io
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from PIL import Image

import keys

from core import (
    FACTCHECK_KEY,
    analyze_video_bytes,
    LEXICONS,
    MAX_UPLOAD,
    MAX_VIDEO_UPLOAD,
    VERSION,
    ai_heuristics,
    analyze_audio_bytes,
    check_text,
    ela,
    fuse,
    noise_profile,
    read_exif,
    scan_c2pa,
    scan_signatures,
)

app = FastAPI(title="AuthCheck")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def meter_requests(request: Request, call_next):
    """Apply per-tier quotas to the analysis endpoints.

    Anonymous callers are limited by IP, keyed callers by their key. A bad key
    is not an error - it simply falls back to the anonymous quota.
    """
    if not keys.is_metered(request.url.path):
        return await call_next(request)

    identity = keys.identify(request.headers.get("x-api-key", "").strip(), _client_ip(request))
    quota = keys.check_rate(identity["bucket"], identity["tier"])
    if not quota["allowed"]:
        return JSONResponse(
            {
                "ok": False,
                "error": "rate limit exceeded",
                "tier": quota["tier"],
                "limit_per_hour": quota["limit_per_hour"],
                "reset_in_seconds": quota["reset_in_seconds"],
                "hint": "Add an X-API-Key header for a higher quota.",
            },
            status_code=429,
            headers={"Retry-After": str(quota["reset_in_seconds"])},
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Tier"] = quota["tier"]
    response.headers["X-RateLimit-Limit"] = str(quota["limit_per_hour"])
    response.headers["X-RateLimit-Remaining"] = str(quota["remaining"])
    if identity["valid_key"]:
        keys.record_usage(identity["key"]["key"])
    return response

from panel import router as panel_router  # noqa: E402
app.include_router(panel_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"


@app.post("/api/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        return JSONResponse({"ok": False, "error": "file too large (max 25MB)"}, 413)

    c2pa = scan_c2pa(data)
    exif = read_exif(data)
    sigs = scan_signatures(exif, data)
    ela_r = ela(data)
    heur = ai_heuristics(data, exif, sigs)
    fused = fuse(c2pa, exif, sigs, ela_r, heur)

    try:
        img = Image.open(io.BytesIO(data))
        dims = f"{img.size[0]}x{img.size[1]}"
        fmt = img.format
    except Exception:
        dims, fmt = None, None

    return {
        "ok": True,
        "filename": file.filename,
        "size_bytes": len(data),
        "dimensions": dims,
        "format": fmt,
        "c2pa": c2pa,
        "exif": exif,
        "signatures": sigs,
        "ela": ela_r,
        "noise": noise_profile(data),
        "heuristics": heur,
        "verdict": fused,
        "reverse_search": {
            "note": "Upload the image to these to find its earliest appearance:",
            "links": [
                "https://lens.google.com/",
                "https://yandex.com/images/",
                "https://www.bing.com/visualsearch",
                "https://tineye.com/",
            ],
        },
    }


@app.post("/api/check-text")
async def api_check_text(text: str = Form(...), lang: str = Form("")):
    return check_text(text, lang or None)


@app.post("/api/analyze-audio")
async def analyze_audio(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        return JSONResponse({"ok": False, "error": "file too large (max 25MB)"}, 413)
    return analyze_audio_bytes(data, file.filename or "audio")


@app.post("/api/analyze-video")
async def analyze_video(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_VIDEO_UPLOAD:
        return JSONResponse({"ok": False, "error": "file too large (max 100MB)"}, 413)
    return analyze_video_bytes(data, file.filename or "video")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "factcheck_key": bool(FACTCHECK_KEY),
        "layers": ["c2pa", "exif", "ela", "noise", "heuristics", "text", "audio", "video"],
        "languages": sorted(LEXICONS.keys()),
        "version": VERSION,
    }


@app.get("/api/tiers")
def tiers():
    """Public pricing surface: what each tier gets, so a client can self-serve."""
    return {"ok": True, "tiers": keys.usage_summary()["tiers"], "metered_endpoints": list(keys.METERED_PREFIXES)}


@app.get("/api/usage")
def usage(request: Request):
    """Live quota for the caller - anonymous by IP, keyed callers by key."""
    identity = keys.identify(request.headers.get("x-api-key", "").strip(), _client_ip(request))
    quota = keys.check_rate(identity["bucket"], identity["tier"])
    return {
        "ok": True,
        "tier": identity["tier"],
        "key_name": (identity["key"] or {}).get("name"),
        "valid_key": identity["valid_key"],
        "limit_per_hour": quota["limit_per_hour"],
        "remaining": quota["remaining"],
        "reset_in_seconds": quota["reset_in_seconds"],
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 12000)))
