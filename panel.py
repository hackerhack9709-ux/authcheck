"""One-click control room ("dukaan").

Every button on the panel calls one endpoint here, and each endpoint does real
work: run the self-test, check the live site, dispatch the automation, export a
bundle. No button is decorative.
"""
from __future__ import annotations

import io
import json
import os
import platform
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response

import selftest
import core
import keys
import billing
import leads

ROOT = Path(__file__).resolve().parent
STARTED = time.time()

OPENHANDS_HOST = os.environ.get("OPENHANDS_HOST", "https://app.all-hands.dev").rstrip("/")
OPENHANDS_API_KEY = os.environ.get("OPENHANDS_API_KEY", "").strip()
AUTOMATION_ID = os.environ.get(
    "AUTHCHECK_AUTOMATION_ID", "080c36db-4e0c-44fe-81bd-63db40db09ab"
)
# Set PANEL_PIN before exposing this publicly. Empty = no gate (local dev only).
PANEL_PIN = os.environ.get("PANEL_PIN", "").strip()

router = APIRouter()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _automation_request(method: str, path: str, body: dict | None = None) -> dict:
    if not OPENHANDS_API_KEY:
        return {"ok": False, "error": "OPENHANDS_API_KEY is not set in this environment"}
    url = f"{OPENHANDS_HOST}/api/automation/v1{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {OPENHANDS_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return {"ok": True, "data": json.load(r)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _public_base() -> str:
    return os.environ.get("AUTHCHECK_PUBLIC_URL", "").rstrip("/") or f"http://127.0.0.1:{os.environ.get('PORT', '12000')}"


def _authorised(pin: str) -> bool:
    return (not PANEL_PIN) or (pin == PANEL_PIN)


def _denied() -> JSONResponse:
    return JSONResponse({"ok": False, "error": "wrong or missing PIN"}, status_code=401)


# --------------------------------------------------------------------------- #
# 1. status
# --------------------------------------------------------------------------- #
@router.get("/panel/api/status")
def status():
    import app as webapp  # noqa: PLC0415 - avoid a circular import at module load

    files = {
        p.name: p.stat().st_size
        for p in sorted(ROOT.glob("*.py")) if p.is_file()
    }
    return {
        "ok": True,
        "checked_at": _now(),
        "app": {"version": core.VERSION, "uptime_seconds": round(time.time() - STARTED)},
        "routes": sorted({r.path for r in webapp.app.routes if getattr(r, "path", "").startswith("/api")}),
        "python": platform.python_version(),
        "files": files,
        "automation": {
            "id": AUTOMATION_ID,
            "api_key_present": bool(OPENHANDS_API_KEY),
            "host": OPENHANDS_HOST,
        },
        "public_url": _public_base(),
        "pin_required": bool(PANEL_PIN),
        "keys": keys.usage_summary(),
        "billing": billing.billing_summary(),
    }


# --------------------------------------------------------------------------- #
# 2. self-test
# --------------------------------------------------------------------------- #
@router.post("/panel/api/selftest")
def run_selftest():
    t0 = time.time()
    try:
        passed, results = selftest.run_checks()
    except Exception as e:
        return JSONResponse(
            {"ok": False, "error": f"{type(e).__name__}: {e}"}, status_code=500
        )
    return {
        "ok": True,
        "passed": passed,
        "total": len(results),
        "failed": [r["name"] for r in results if not r["ok"]],
        "results": results,
        "took_ms": round((time.time() - t0) * 1000),
        "ran_at": _now(),
    }


# --------------------------------------------------------------------------- #
# 3. live site check
# --------------------------------------------------------------------------- #
@router.post("/panel/api/livecheck")
def livecheck(url: str = Form("")):
    target = (url or _public_base()).rstrip("/")
    out = {"ok": True, "target": target, "checks": []}

    def probe(path, expect_json=False):
        t0 = time.time()
        try:
            with urllib.request.urlopen(f"{target}{path}", timeout=15) as r:
                body = r.read()
                entry = {"path": path, "status": r.status, "ms": round((time.time() - t0) * 1000)}
                if expect_json:
                    try:
                        entry["json"] = json.loads(body)
                    except Exception:
                        entry["json"] = None
                out["checks"].append(entry)
                return entry
        except Exception as e:
            out["checks"].append({"path": path, "status": None, "error": f"{type(e).__name__}: {e}"})
            return None

    probe("/")
    probe("/api/health", expect_json=True)
    out["all_ok"] = all(c.get("status") == 200 for c in out["checks"])
    out["checked_at"] = _now()
    return out


# --------------------------------------------------------------------------- #
# 4. automation control
# --------------------------------------------------------------------------- #
@router.get("/panel/api/automation")
def automation_info():
    info = _automation_request("GET", f"/{AUTOMATION_ID}")
    runs = _automation_request("GET", f"/{AUTOMATION_ID}/runs?limit=5")
    return {
        "ok": info.get("ok", False),
        "error": info.get("error"),
        "automation": info.get("data"),
        "runs": (runs.get("data") or {}).get("runs", []),
        "checked_at": _now(),
    }


@router.post("/panel/api/automation/dispatch")
def automation_dispatch(pin: str = Form("")):
    if not _authorised(pin):
        return _denied()
    res = _automation_request("POST", f"/{AUTOMATION_ID}/dispatch")
    if res.get("ok"):
        return {"ok": True, "run": res["data"], "dispatched_at": _now()}
    return JSONResponse({"ok": False, "error": res.get("error")}, status_code=502)


@router.post("/panel/api/automation/toggle")
def automation_toggle(enabled: str = Form("true"), pin: str = Form("")):
    if not _authorised(pin):
        return _denied()
    want = enabled.lower() in ("1", "true", "yes", "on")
    res = _automation_request("PATCH", f"/{AUTOMATION_ID}", {"enabled": want})
    if res.get("ok"):
        return {"ok": True, "state": res["data"].get("state"), "enabled": res["data"].get("enabled")}
    return JSONResponse({"ok": False, "error": res.get("error")}, status_code=502)


# --------------------------------------------------------------------------- #
# 5. export everything
# --------------------------------------------------------------------------- #
@router.get("/panel/api/export")
def export_bundle(pin: str = ""):
    if not _authorised(pin):
        return _denied()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT)
            # build environments live inside the project dir on some hosts
            if any(part in {"__pycache__", ".git", ".venv", "venv", "data"} for part in rel.parts):
                continue
            if p.suffix in {".log", ".gz", ".pyc", ".db"}:
                continue
            # never bundle secrets or runtime state into a shareable archive
            if p.name in {".panel_pin", ".authcheck.pid", ".env"}:
                continue
            # build systems stamp files with pre-1980 mtimes, which zipfile rejects
            info = zipfile.ZipInfo(str(rel), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(p, "rb") as src:
                z.writestr(info, src.read())
        z.writestr("EXPORT-INFO.txt", f"AuthCheck export\ncreated: {_now()}\nfiles bundled from: {ROOT}\n")
    buf.seek(0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="authcheck-{stamp}.zip"'},
    )


# --------------------------------------------------------------------------- #
# 6. API keys (monetisation: free vs pro tiers)
# --------------------------------------------------------------------------- #
@router.get("/panel/api/keys")
def list_api_keys(pin: str = ""):
    if not _authorised(pin):
        return _denied()
    return {"ok": True, "keys": keys.list_keys(), "usage": keys.usage_summary(), "checked_at": _now()}


@router.post("/panel/api/keys")
def create_api_key(name: str = Form(""), tier: str = Form("pro"), pin: str = Form("")):
    if not _authorised(pin):
        return _denied()
    if tier not in keys.TIERS:
        return JSONResponse({"ok": False, "error": f"unknown tier: {tier}"}, status_code=400)
    if not keys.storage_available():
        return JSONResponse(
            {
                "ok": False,
                "error": "no writable disk - set AUTHCHECK_API_KEYS in the environment instead",
            },
            status_code=503,
        )
    record = keys.create_key(name, tier)
    return {"ok": True, "key": record, "created_at": _now()}


@router.post("/panel/api/keys/revoke")
def revoke_api_key(key: str = Form(...), pin: str = Form("")):
    if not _authorised(pin):
        return _denied()
    return {"ok": keys.revoke_key(key), "revoked_at": _now()}


@router.post("/panel/api/keys/renew")
def renew_api_key(key: str = Form(...), days: int = Form(30), pin: str = Form("")):
    if not _authorised(pin):
        return _denied()
    expires = keys.extend_key(key, days)
    if not expires:
        return JSONResponse({"ok": False, "error": "key not found or bad period"}, status_code=404)
    return {"ok": True, "expires_at": expires, "renewed_at": _now()}


@router.get("/panel/api/billing")
def billing_overview(pin: str = ""):
    if not _authorised(pin):
        return _denied()
    return {
        "ok": True,
        "billing": {**billing.billing_summary(), "expiring_soon": billing.expiring_soon(7)},
        "purchases": billing.recent_purchases(20),
        "checked_at": _now(),
    }


@router.get("/panel/api/requests")
def list_key_requests(pin: str = ""):
    """Free-key requests captured by the /for-teams page."""
    if not _authorised(pin):
        return _denied()
    return {"ok": True, "requests": leads.list_requests(), "counts": leads.counts(), "checked_at": _now()}


@router.post("/panel/api/requests/issue")
def issue_from_request(request_id: str = Form(...), tier: str = Form(""), days: int = Form(30),
                       pin: str = Form("")):
    """Mint a key for a request and mark it issued.

    The form asks for a *plan* (free/starter/pro); keys are minted on a *tier*
    (free/pro/desk). billing.PLANS holds that mapping, so resolve through it.
    """
    if not _authorised(pin):
        return _denied()
    wanted = next((r for r in leads.list_requests(500) if r["id"] == request_id), None)
    if not wanted:
        return JSONResponse({"ok": False, "error": "unknown request"}, status_code=404)

    chosen_plan = tier or wanted["wanted_tier"]
    resolved = billing.PLANS.get(chosen_plan, {}).get("tier") or chosen_plan
    if resolved not in keys.TIERS:
        return JSONResponse({"ok": False, "error": f"unknown plan: {chosen_plan}"}, status_code=400)
    if not keys.storage_available():
        return JSONResponse({"ok": False, "error": "no storage - set AUTHCHECK_DATABASE_URL"}, status_code=503)

    record = keys.create_key(f"lead:{wanted['name']}", resolved, days=days if resolved != "free" else 0)
    leads.mark_issued(request_id, record["key"])
    return {"ok": True, "key": record, "tier": resolved, "for": wanted["email"], "issued_at": _now()}


@router.post("/panel/api/requests/delete")
def delete_key_request(request_id: str = Form(...), pin: str = Form("")):
    """Clear a request — the form is public, so spam will reach it eventually."""
    if not _authorised(pin):
        return _denied()
    return {"ok": leads.delete_request(request_id), "deleted_at": _now()}


@router.post("/panel/api/billing/renew")
def billing_renew_link(renew_key: str = Form(...), pin: str = Form("")):
    """Mint a Razorpay renewal link for an existing subscription."""
    if not _authorised(pin):
        return _denied()
    base = os.environ.get("AUTHCHECK_PUBLIC_URL", "").strip()
    return billing.create_renewal_link(renew_key, base_url=base)


@router.post("/panel/api/billing/issue")
def billing_issue(reference: str = Form(...), pin: str = Form("")):
    """Manually issue a key for a paid reference (webhook fallback)."""
    if not _authorised(pin):
        return _denied()
    result = billing.fulfil_payment(reference, payment_id="manual", email="")
    return result


@router.post("/panel/api/billing/reconcile")
def billing_reconcile(pin: str = Form("")):
    """Sweep pending purchases and fulfil the ones Razorpay says are paid.

    The webhook can only be added by hand in the Razorpay dashboard, so this is
    the operator's net: a paid link that never reached the webhook still gets
    its key, and the buyer is not left waiting.
    """
    if not _authorised(pin):
        return _denied()
    if not billing.razorpay_ready():
        return JSONResponse({"ok": False, "error": "razorpay keys are not configured"}, status_code=503)
    return billing.reconcile_pending()


# --------------------------------------------------------------------------- #
# 7. share text (WhatsApp / copy)
# --------------------------------------------------------------------------- #
@router.post("/panel/api/share")
def share(url: str = Form("")):
    target = (url or _public_base()).rstrip("/")
    msg = (
        "AuthCheck - check if a photo, voice note or claim is real. "
        f"It gives a trust score and the reasons. {target}"
    )
    from urllib.parse import quote
    return {
        "ok": True,
        "url": target,
        "message": msg,
        "whatsapp": f"https://wa.me/?text={quote(msg)}",
        "telegram": f"https://t.me/share/url?url={quote(target)}&text={quote('Check if it is real')}",
        "copy": msg,
    }


# --------------------------------------------------------------------------- #
# panel page
# --------------------------------------------------------------------------- #
@router.get("/panel", response_class=HTMLResponse)
def panel_page():
    return HTMLResponse((ROOT / "static" / "panel.html").read_text(encoding="utf-8"))
