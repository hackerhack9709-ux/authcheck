"""Billing: Razorpay payment links, webhook fulfilment, plan catalogue.

Flow
----
1. Buyer picks a plan on the landing page.
2. We open a Razorpay payment link (or a hosted checkout) with the plan baked
   into the notes.
3. Razorpay calls our webhook on payment. We verify the HMAC signature, then
   issue an API key on the matching tier and record the purchase.

Everything degrades gracefully: with no credentials the module still returns a
plan catalogue, and the checkout endpoint explains exactly what is missing
instead of pretending a payment happened.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import keys

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()

DB_PATH = Path(os.environ.get("AUTHCHECK_DB", "./data/authcheck.db"))
_lock = threading.Lock()

# Monthly plans. Prices in INR; Razorpay wants the smallest unit (paise).
PLANS = {
    "pro": {
        "name": "Pro desk",
        "amount_inr": 499,
        "interval": "monthly",
        "tier": "desk",
        "limit_per_hour": keys.TIERS["desk"]["limit"],
        "blurb": "For a busy solo desk or a small newsroom tool.",
    },
    "starter": {
        "name": "Starter",
        "amount_inr": 99,
        "interval": "monthly",
        "tier": "pro",
        "limit_per_hour": keys.TIERS["pro"]["limit"],
        "blurb": "For a personal project that outgrew the free quota.",
    },
}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id            TEXT PRIMARY KEY,
            plan          TEXT NOT NULL,
            amount_inr    INTEGER NOT NULL,
            email         TEXT,
            payment_id    TEXT,
            order_ref     TEXT,
            issued_key    TEXT,
            created_at    TEXT NOT NULL,
            status        TEXT NOT NULL
        )
        """
    )
    return conn


def razorpay_ready() -> bool:
    return bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)


def plans_public() -> list[dict]:
    return [
        {
            "id": pid,
            "name": p["name"],
            "amount_inr": p["amount_inr"],
            "interval": p["interval"],
            "tier": p["tier"],
            "limit_per_hour": p["limit_per_hour"],
            "blurb": p["blurb"],
        }
        for pid, p in PLANS.items()
    ]


def _razorpay(path: str, body: dict) -> dict:
    """POST to Razorpay's REST API with basic auth."""
    url = f"https://api.razorpay.com/v1{path}"
    token = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def create_payment_link(plan_id: str, email: str = "", base_url: str = "") -> dict:
    """Create a Razorpay Payment Link for a plan. Returns {ok, url, ...}."""
    plan = PLANS.get(plan_id)
    if not plan:
        return {"ok": False, "error": f"unknown plan: {plan_id}"}
    if not razorpay_ready():
        return {
            "ok": False,
            "error": "payments are not configured on this server",
            "missing": [n for n, v in (
                ("RAZORPAY_KEY_ID", RAZORPAY_KEY_ID),
                ("RAZORPAY_KEY_SECRET", RAZORPAY_KEY_SECRET),
            ) if not v],
        }

    reference = f"authcheck-{plan_id}-{uuid.uuid4().hex[:10]}"
    body = {
        "amount": plan["amount_inr"] * 100,
        "currency": "INR",
        "description": f"AuthCheck {plan['name']} — {plan['limit_per_hour']} checks/hour",
        "reference_id": reference,
        "notes": {"plan": plan_id, "tier": plan["tier"]},
    }
    if email:
        body["customer"] = {"email": email}
    if base_url:
        body["callback_url"] = f"{base_url.rstrip('/')}/billing/success"
        body["callback_method"] = "get"

    try:
        data = _razorpay("/payment_links", body)
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"razorpay HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    _record(reference, plan_id, plan["amount_inr"], email, status="link_created")
    return {"ok": True, "url": data.get("short_url"), "reference": reference, "amount_inr": plan["amount_inr"]}


# --------------------------------------------------------------------------- #
# webhook fulfilment
# --------------------------------------------------------------------------- #
def verify_webhook(raw_body: bytes, signature: str) -> bool:
    if not RAZORPAY_WEBHOOK_SECRET:
        return False
    expected = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def _record(ref: str, plan_id: str, amount: int, email: str, payment_id: str = "",
            issued_key: str = "", status: str = "pending") -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO purchases "
            "(id, plan, amount_inr, email, payment_id, order_ref, issued_key, created_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ref, plan_id, amount, email, payment_id, ref, issued_key,
             datetime.now(timezone.utc).isoformat(timespec="seconds"), status),
        )


def _lookup_reference(ref: str) -> dict | None:
    try:
        with _lock, _connect() as conn:
            row = conn.execute(
                "SELECT plan, email, amount_inr, status, issued_key FROM purchases WHERE order_ref = ?",
                (ref,),
            ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    return {"plan": row[0], "email": row[1], "amount_inr": row[2], "status": row[3], "issued_key": row[4]}


def fulfil_payment(reference: str, payment_id: str, email: str = "") -> dict:
    """Issue a key for a paid reference. Idempotent: re-running returns the same key."""
    existing = _lookup_reference(reference)
    if existing and existing["issued_key"]:
        return {"ok": True, "already_issued": True, "key": existing["issued_key"], "plan": existing["plan"]}

    plan_id = (existing or {}).get("plan")
    if not plan_id:
        # Razorpay notes carry the plan; a bare reference still maps by prefix
        for pid in PLANS:
            if f"-{pid}-" in reference:
                plan_id = pid
                break
    plan = PLANS.get(plan_id or "")
    if not plan:
        return {"ok": False, "error": f"cannot map reference to a plan: {reference}"}

    record = keys.create_key(name=f"razorpay:{plan['name']}:{email or 'buyer'}", tier=plan["tier"])
    _record(reference, plan_id, plan["amount_inr"], email or (existing or {}).get("email", ""),
            payment_id=payment_id, issued_key=record["key"], status="paid")
    return {"ok": True, "key": record["key"], "plan": plan_id, "tier": plan["tier"]}


def handle_webhook(raw_body: bytes, signature: str, headers: dict) -> dict:
    if not verify_webhook(raw_body, signature):
        return {"ok": False, "error": "invalid webhook signature"}
    try:
        event = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"bad json: {e}"}

    event_type = event.get("event", "")
    payload = (event.get("payload") or {}).get("payment_link", {}).get("entity") or {}
    if not payload:
        payload = (event.get("payload") or {}).get("payment", {}).get("entity") or {}
    reference = payload.get("reference_id") or (payload.get("notes") or {}).get("reference_id") or ""
    payment_id = payload.get("id", "")
    email = ((payload.get("customer") or {}).get("email")) or ""

    if event_type in {"payment_link.paid", "payment.captured", "order.paid"} and reference:
        return {"ok": True, "event": event_type, **fulfil_payment(reference, payment_id, email)}
    return {"ok": True, "event": event_type, "ignored": True}


def issued_key_for(reference: str) -> str | None:
    """The key issued for a reference, for the post-payment success page to poll."""
    row = _lookup_reference(reference)
    return row["issued_key"] if row else None


def recent_purchases(limit: int = 20) -> list[dict]:
    try:
        with _lock, _connect() as conn:
            rows = conn.execute(
                "SELECT id, plan, amount_inr, email, status, issued_key, created_at "
                "FROM purchases ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    except Exception:
        return []
    return [
        {"reference": r[0], "plan": r[1], "amount_inr": r[2], "email": r[3], "status": r[4],
         "issued_key": (r[5][:9] + "…" + r[5][-4:]) if r[5] else None, "created_at": r[6]}
        for r in rows
    ]


def billing_summary() -> dict:
    return {
        "provider": "razorpay",
        "configured": razorpay_ready(),
        "webhook_configured": bool(RAZORPAY_WEBHOOK_SECRET),
        "plans": plans_public(),
    }
