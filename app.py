"""AuthCheck web app - HTTP layer over the framework-free analysis core."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from PIL import Image

import keys
import billing
import leads

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


@app.get("/api/plans")
def api_plans():
    """Public plan catalogue with prices, so the landing page can render itself."""
    return {"ok": True, **billing.billing_summary()}


@app.post("/api/request-key")
async def request_key(
    name: str = Form(...),
    email: str = Form(...),
    org: str = Form(""),
    use_case: str = Form(""),
    plan: str = Form("free"),
    website: str = Form(""),
):
    """Capture a free-key request from the /for-teams page.

    `website` is a honeypot: it is hidden in the form, so a value means a bot.
    Nothing is issued here — an operator reviews the list and mints a key.
    """
    if website.strip():
        return {"ok": True, "queued": True, "note": "thanks"}
    return leads.create_request(name, email, org=org, use_case=use_case, wanted_tier=plan)


@app.post("/billing/checkout")
async def billing_checkout(plan: str = Form(...), email: str = Form("")):
    """Open a Razorpay payment link for a plan and hand the URL back to the browser."""
    base = os.environ.get("AUTHCHECK_PUBLIC_URL", "").strip()
    return billing.create_payment_link(plan, email=email.strip(), base_url=base)


@app.post("/billing/webhook")
async def billing_webhook(request: Request):
    """Razorpay callback. Verified by HMAC before anything is issued."""
    raw = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    result = billing.handle_webhook(raw, signature, dict(request.headers))
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


@app.post("/billing/renew")
async def billing_renew(renew_key: str = Form(...)):
    """Open a payment link that renews the subscription behind a renew_key."""
    base = os.environ.get("AUTHCHECK_PUBLIC_URL", "").strip()
    return billing.create_renewal_link(renew_key.strip(), base_url=base)


@app.get("/billing/status")
def billing_status(ref: str = "", settle: bool = False):
    """Polled by the success page until the key is issued.

    With `settle=1` and no key yet, we ask Razorpay directly what the reference
    is worth and issue the key if it was paid. That keeps a buyer from being
    stranded when the dashboard webhook is missing or delayed.
    """
    issued = billing.issued_key_for(ref) if ref else None
    if not issued and ref and settle:
        result = billing.reconcile_reference(ref)
        issued = result.get("key") or (billing.issued_key_for(ref) if result.get("ok") else None)
    return {"ok": True, "reference": ref, "issued": bool(issued), "key": issued or ""}


@app.get("/billing/success", response_class=HTMLResponse)
def billing_success(ref: str = "", key: str = ""):
    """Post-payment landing. The key arrives here when the webhook already ran."""
    safe_key = key if key.startswith("ac_") else ""
    body = f"""
    <!doctype html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>AuthCheck — payment received</title>
    <style>
      body{{background:#0a0b0d;color:#e7e5e0;font-family:Georgia,serif;margin:0;
        display:flex;min-height:100vh;align-items:center;justify-content:center;padding:24px}}
      .card{{max-width:640px;border:1px solid #272c34;background:#101215;padding:40px}}
      .tag{{font-family:ui-monospace,monospace;font-size:.62rem;letter-spacing:.24em;
        text-transform:uppercase;color:#ffc63d}}
      h1{{font-size:1.9rem;margin:14px 0 8px}}
      p{{color:#8b8f98;line-height:1.7;font-size:.95rem}}
      pre{{background:#171a1f;border:1px solid #343a44;padding:16px;overflow:auto;
        font-family:ui-monospace,monospace;font-size:.8rem;color:#3ecf8e}}
      .note{{font-family:ui-monospace,monospace;font-size:.68rem;color:#5f646d;margin-top:18px}}
      a{{color:#ffc63d}}
    </style></head><body><div class="card">
      <div class="tag">AuthCheck · Payment received</div>
      <h1>Thank you.</h1>
      {"<p>Your API key is below. Keep it safe — treat it like a password.</p><pre>" + safe_key + "</pre>"
       if safe_key else
       "<p>We are confirming the payment with Razorpay. Your API key will be issued "
       "to this page in a moment — refresh in a few seconds.</p>"}
      <p>Use it as an <span style="font-family:ui-monospace,monospace">X-API-Key</span> header:</p>
      <pre>curl -H "X-API-Key: {'&lt;key&gt;' if not safe_key else safe_key}" {'&lt;base&gt;'}/api/usage</pre>
      <div class="note">Reference: {ref or '—'}</div>
      <p><a href="/">Back to the desk →</a></p>
    </div>
    <script>
      const ref = {json.dumps(ref)};
      const haveKey = {str(bool(safe_key)).lower()};
      if (ref && !haveKey) {{
        const t = setInterval(async () => {{
          try {{
            const r = await fetch('/billing/status?settle=1&ref=' + encodeURIComponent(ref));
            const d = await r.json();
            if (d.issued) {{ clearInterval(t); location.search = '?ref=' + encodeURIComponent(ref) + '&key=' + encodeURIComponent(d.key); }}
          }} catch (e) {{}}
        }}, 3000);
        setTimeout(() => clearInterval(t), 120000);
      }}
    </script></body></html>
    """
    return HTMLResponse(body)


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


TEAMS_HTML = STATIC_DIR / "teams.html"


@app.get("/for-teams", response_class=HTMLResponse)
def for_teams():
    return HTMLResponse(TEAMS_HTML.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 12000)))
