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
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import db
import keys

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()

DB_PATH = db.SQLITE_PATH
_lock = threading.Lock()

# Monthly plans. Prices in INR; Razorpay wants the smallest unit (paise).
PLANS = {
    "pro": {
        "name": "Pro desk",
        "amount_inr": 499,
        "interval": "monthly",
        "days": 30,
        "tier": "desk",
        "limit_per_hour": keys.TIERS["desk"]["limit"],
        "blurb": "For a busy solo desk or a small newsroom tool.",
    },
    "starter": {
        "name": "Starter",
        "amount_inr": 99,
        "interval": "monthly",
        "days": 30,
        "tier": "pro",
        "limit_per_hour": keys.TIERS["pro"]["limit"],
        "blurb": "For a personal project that outgrew the free quota.",
    },
}


_schema_engine: str | None = None


def _ensure_schema(conn) -> None:
    global _schema_engine
    engine = db.backend()
    if _schema_engine == engine:
        return
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
            status        TEXT NOT NULL,
            renew_key     TEXT
        )
        """
    )
    if "renew_key" not in db.table_columns(conn, "purchases"):
        conn.execute("ALTER TABLE purchases ADD COLUMN renew_key TEXT")
    _schema_engine = engine


@contextmanager
def _connect():
    with db.connect() as conn:
        _ensure_schema(conn)
        yield conn


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
    return _payment_link(f"authcheck-{plan_id}-{uuid.uuid4().hex[:10]}", plan, email, base_url)


def _payment_link(reference: str, plan: dict, email: str, base_url: str) -> dict:
    if not razorpay_ready():
        return {
            "ok": False,
            "error": "payments are not configured on this server",
            "missing": [n for n, v in (
                ("RAZORPAY_KEY_ID", RAZORPAY_KEY_ID),
                ("RAZORPAY_KEY_SECRET", RAZORPAY_KEY_SECRET),
            ) if not v],
        }

    body = {
        "amount": plan["amount_inr"] * 100,
        "currency": "INR",
        "description": f"AuthCheck {plan['name']} — {plan['limit_per_hour']} checks/hour",
        "reference_id": reference,
        "notes": {"plan": plan_id_from(plan), "tier": plan["tier"]},
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

    if not reference.startswith("renew-"):
        _record(reference, plan_id_from(plan), plan["amount_inr"], email, status="link_created")
    return {"ok": True, "url": data.get("short_url"), "reference": reference, "amount_inr": plan["amount_inr"]}


def plan_id_from(plan: dict) -> str:
    for pid, p in PLANS.items():
        if p is plan:
            return pid
    return ""


# --------------------------------------------------------------------------- #
# webhook fulfilment
# --------------------------------------------------------------------------- #
def verify_webhook(raw_body: bytes, signature: str) -> bool:
    if not RAZORPAY_WEBHOOK_SECRET:
        return False
    expected = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def _record(ref: str, plan_id: str, amount: int, email: str, payment_id: str = "",
            issued_key: str = "", status: str = "pending", renew_key: str = "") -> None:
    columns = ["id", "plan", "amount_inr", "email", "payment_id", "order_ref",
               "issued_key", "created_at", "status", "renew_key"]
    values = (ref, plan_id, amount, email, payment_id, ref, issued_key,
              datetime.now(timezone.utc).isoformat(timespec="seconds"), status, renew_key)
    with _lock, _connect() as conn:
        conn.execute(db.upsert("purchases", columns, conflict="id"), values)


def _lookup_reference(ref: str) -> dict | None:
    try:
        with _lock, _connect() as conn:
            row = conn.execute(
                "SELECT plan, email, amount_inr, status, issued_key, renew_key "
                "FROM purchases WHERE order_ref = ?",
                (ref,),
            ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    return {"plan": row[0], "email": row[1], "amount_inr": row[2], "status": row[3],
            "issued_key": row[4], "renew_key": row[5]}


def _lookup_by_renew(renew_key: str) -> dict | None:
    try:
        with _lock, _connect() as conn:
            row = conn.execute(
                "SELECT plan, email, issued_key FROM purchases WHERE renew_key = ? ORDER BY created_at DESC",
                (renew_key,),
            ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    return {"plan": row[0], "email": row[1], "issued_key": row[2]}


def fulfil_payment(reference: str, payment_id: str, email: str = "") -> dict:
    """Issue a key for a paid reference. Idempotent: re-running returns the same key.

    A reference of the form `renew-<renew_key>` extends the existing subscription
    instead of minting a new key, so a renewal keeps the customer's key working.
    """
    if reference.startswith("renew-"):
        return renew_payment(reference[len("renew-"):], payment_id)

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

    renew_key = uuid.uuid4().hex
    record = keys.create_key(
        name=f"razorpay:{plan['name']}:{email or 'buyer'}",
        tier=plan["tier"],
        days=plan.get("days", 30),
    )
    _record(reference, plan_id, plan["amount_inr"], email or (existing or {}).get("email", ""),
            payment_id=payment_id, issued_key=record["key"], status="paid", renew_key=renew_key)
    return {"ok": True, "key": record["key"], "plan": plan_id, "tier": plan["tier"],
            "expires_at": record.get("expires_at"), "renew_key": renew_key}


def renew_payment(renew_key: str, payment_id: str = "") -> dict:
    """Extend the subscription behind a renew_key by the plan's period."""
    found = _lookup_by_renew(renew_key)
    if not found or not found["issued_key"]:
        return {"ok": False, "error": f"unknown renewal key: {renew_key}"}
    plan = PLANS.get(found["plan"] or "")
    if not plan:
        return {"ok": False, "error": f"unknown plan for renewal: {found['plan']}"}
    new_expiry = keys.extend_key(found["issued_key"], plan.get("days", 30))
    if not new_expiry:
        return {"ok": False, "error": "could not extend the key"}
    return {"ok": True, "renewed": True, "key": found["issued_key"],
            "plan": found["plan"], "expires_at": new_expiry}


def create_renewal_link(renew_key: str, base_url: str = "") -> dict:
    """Open a payment link that renews an existing subscription."""
    found = _lookup_by_renew(renew_key)
    if not found:
        return {"ok": False, "error": "unknown renewal key"}
    plan = PLANS.get(found["plan"] or "")
    if not plan:
        return {"ok": False, "error": "unknown plan"}
    return _payment_link(f"renew-{renew_key}", plan, found["email"] or "", base_url)


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
                "SELECT id, plan, amount_inr, email, status, issued_key, created_at, renew_key "
                "FROM purchases ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    except Exception:
        return []
    return [
        {"reference": r[0], "plan": r[1], "amount_inr": r[2], "email": r[3], "status": r[4],
         "issued_key": (r[5][:9] + "…" + r[5][-4:]) if r[5] else None, "created_at": r[6],
         "renew_key": r[7]}
        for r in rows
    ]


def billing_summary() -> dict:
    return {
        "provider": "razorpay",
        "configured": razorpay_ready(),
        "webhook_configured": bool(RAZORPAY_WEBHOOK_SECRET),
        "plans": plans_public(),
    }


def expiring_soon(days: int = 7) -> list[dict]:
    """Paid keys lapsing within `days`, so the panel can flag renewals."""
    cutoff = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(timespec="seconds")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = []
    for k in keys.list_keys():
        exp = k.get("expires_at")
        if exp and now < exp <= cutoff and not k.get("revoked"):
            out.append({"masked": k["masked"], "tier": k["tier"], "expires_at": exp, "name": k["name"]})
    return out
