"""AuthCheck web app - HTTP layer over the framework-free analysis core."""
from __future__ import annotations

import io
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from PIL import Image

from core import (
    FACTCHECK_KEY,
    LEXICONS,
    MAX_UPLOAD,
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


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "factcheck_key": bool(FACTCHECK_KEY),
        "layers": ["c2pa", "exif", "ela", "noise", "heuristics", "text", "audio"],
        "languages": sorted(LEXICONS.keys()),
        "version": "0.3",
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 12000)))
