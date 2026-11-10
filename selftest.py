"""AuthCheck daily self-test.

Deterministic, no LLM. Regenerates the known-good fixtures, runs them through
the analysis core, and verifies the engine still produces the expected verdicts.
Exits non-zero and reports the diff when a regression is detected.

Environment:
  AUTOMATION_CALLBACK_URL / AUTOMATION_RUN_ID / AUTOMATION_CALLBACK_API_KEY
      set by the automation service; used to signal run completion.
  AUTHCHECK_BASE_URL
      optional; when set, the health endpoint is polled too.
"""
from __future__ import annotations

import array
import io
import json
import math
import os
import sys
import tempfile
import urllib.request
import uuid
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Keep the self-test off the live key store: point both modules at a scratch DB
# before they read AUTHCHECK_DB at import time.
os.environ.setdefault("AUTHCHECK_DB", os.path.join(tempfile.gettempdir(), "authcheck_selftest.db"))

import core  # noqa: E402
import keys  # noqa: E402
import leads  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def get_secret(name):
    url = os.environ.get("AGENT_SERVER_URL", "").rstrip("/")
    key = os.environ.get("SESSION_API_KEY") or os.environ.get("OH_SESSION_API_KEYS_0", "")
    if url:
        target = f"{url}/api/settings/secrets/{name}"
    else:
        api = os.environ.get("OPENHANDS_CLOUD_API_URL", "").rstrip("/")
        if not api or not os.environ.get("SANDBOX_ID"):
            return None
        target = f"{api}/api/v1/sandboxes/{os.environ['SANDBOX_ID']}/settings/secrets/{name}"
    try:
        req = urllib.request.Request(target, headers={"X-Session-API-Key": key})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode().strip()
    except Exception:
        return None


def fire_callback(status="COMPLETED", error=None):
    url = os.environ.get("AUTOMATION_CALLBACK_URL", "")
    if not url:
        return
    body = {"status": status, "run_id": os.environ.get("AUTOMATION_RUN_ID", "")}
    if error:
        body["error"] = error
    try:
        urllib.request.urlopen(urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ.get('AUTOMATION_CALLBACK_API_KEY', '')}",
            },
        ))
    except Exception as e:  # pragma: no cover
        print(f"Callback error: {e}")


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def wav_bytes(sample_rate: int, seconds: int, gen) -> bytes:
    n = sample_rate * seconds
    samples = array.array("h", [int(max(-1, min(1, gen(i / sample_rate))) * 32000) for i in range(n)])
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(samples.tobytes())
    return buf.getvalue()


def png_bytes(size=(1024, 1024)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 60, 120)).save(buf, "PNG")
    return buf.getvalue()


def mp4_bytes() -> bytes | None:
    """A 2s synthetic clip, or None when no ffmpeg binary is available."""
    import subprocess
    import tempfile
    ff = core._ffmpeg_path()
    if not ff:
        return None
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        frame = os.path.join(td, "f.png")
        clip = os.path.join(td, "c.mp4")
        Image.new("RGB", (320, 240), (30, 60, 120)).save(frame)
        r = subprocess.run(
            [ff, "-y", "-loop", "1", "-i", frame, "-t", "2", "-pix_fmt", "yuv420p",
             "-r", "10", clip],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0 or not os.path.exists(clip):
            return None
        with open(clip, "rb") as fh:
            return fh.read()


# --------------------------------------------------------------------------- #
# expectations
# --------------------------------------------------------------------------- #
CHECKS = []


def check(name, got, expect, tol=0):
    ok = abs(got - expect) <= tol if isinstance(expect, (int, float)) else got == expect
    CHECKS.append({"name": name, "got": got, "expect": expect, "ok": ok})
    return ok


def run_checks() -> tuple[bool, list[dict]]:
    CHECKS.clear()  # module-level list, so repeated calls must not accumulate
    # 1. AI-shaped image: square 1024 canvas, no EXIF -> low trust
    img = png_bytes()
    exif = core.read_exif(img)
    sigs = core.scan_signatures(exif, img)
    heur = core.ai_heuristics(img, exif, sigs)
    verdict = core.fuse(core.scan_c2pa(img), exif, sigs, core.ela(img), heur)
    check("synthetic 1024x1024 scores low", verdict["score"], 7, tol=3)

    # 2. Multilingual detection
    check("hindi script detected", core.detect_language("चौंकाने वाली खबर"), "hi")
    check("urdu script detected", core.detect_language("چونکا دینے والی خبر"), "ur")
    check("english fallback", core.detect_language("plain english text"), "en")

    # 3. Hindi forward-bait must be flagged
    hi = core.check_text("चौंकाने वाली खबर!! जरूर शेयर करो, डिलीट होने से पहले!!")
    check("hindi forward flagged", hi["score"] < 70, True)
    check("hindi has flags", len(hi["flags"]) >= 2, True)

    # 4. Neutral English with a source must score clean
    en = core.check_text(
        "The central bank raised rates by 25 basis points, per its statement at https://rbi.org.in"
    )
    check("neutral report clean", en["score"], 100)

    # 5. Stitched audio (alternating silence) must be flagged
    stitched = wav_bytes(16000, 4, lambda t: 0.3 * math.sin(2 * math.pi * 220 * t) if int(t * 2) % 2 == 0 else 0.0)
    av = core.analyze_audio_bytes(stitched, "stitched.wav")
    check("stitched audio flagged", av["verdict"]["score"] < 45, True)

    # 6. Clean tone must not be flagged as stitched
    clean = wav_bytes(44100, 3, lambda t: 0.3 * math.sin(2 * math.pi * 220 * t))
    cv = core.analyze_audio_bytes(clean, "clean.wav")
    check("clean tone not flagged", cv["verdict"]["score"] >= 45, True)

    # 7. Key terms extraction is deterministic and drops stopwords
    terms = core.key_terms("The Moon is made of green cheese and NASA confirmed it")
    check("key terms drop stopwords", "the" not in [t.lower() for t in terms], True)
    check("key terms keep nouns", "moon" in [t.lower() for t in terms], True)

    # 8. Video pipeline produces a well-formed report (skipped without ffmpeg)
    clip = mp4_bytes()
    if clip is None:
        CHECKS.append({"name": "video report (skipped: no ffmpeg)", "got": "skip",
                       "expect": "skip", "ok": True})
    else:
        vd = core.analyze_video_bytes(clip, "clip.mp4")
        check("video report ok", vd.get("ok"), True)
        check("video has container facts", bool((vd.get("container") or {}).get("width")), True)
        check("video sampled frames", vd.get("keyframes_analysed", 0) >= 1, True)

    # 9. Keyless reference lookup returns the documented shape
    ref = core.lookup_references("WHO declared the COVID-19 pandemic in March 2020")
    check("references shape", set(("provider", "query", "hit_count")) <= set(ref), True)
    check("references note present", "not make the claim true" in (ref.get("note") or ""), True)

    # 10. API-key tiers and quotas
    check("anonymous tier has a limit", keys.TIERS["anonymous"]["limit"] > 0, True)
    check("pro tier outranks anonymous", keys.TIERS["pro"]["limit"] > keys.TIERS["anonymous"]["limit"], True)
    check("analysis endpoints are metered", keys.is_metered("/api/check-text"), True)
    check("health is not metered", keys.is_metered("/api/health"), False)
    unknown = keys.identify("ac_definitely-not-a-real-key", "10.0.0.1")
    check("bad key falls back to anonymous", unknown["tier"], "anonymous")
    check("bad key is flagged invalid", unknown["valid_key"], False)

    # 11. Billing: plans, signature verification and idempotent fulfilment
    import billing
    plans = {p["id"]: p for p in billing.plans_public()}
    check("pro plan is priced", plans.get("pro", {}).get("amount_inr", 0) > 0, True)
    check("pro plan maps to desk tier", plans.get("pro", {}).get("tier"), "desk")
    check("desk tier outranks pro", keys.TIERS["desk"]["limit"] > keys.TIERS["pro"]["limit"], True)

    bad = billing.handle_webhook(b'{"event":"payment_link.paid"}', "deadbeef", {})
    check("webhook rejects bad signature", bad["ok"], False)

    ref = "authcheck-pro-selftest01"
    billing._record(ref, "pro", 499, "buyer@example.com", status="link_created")
    first = billing.fulfil_payment(ref, "pay_test_1", "buyer@example.com")
    second = billing.fulfil_payment(ref, "pay_test_1", "buyer@example.com")
    check("payment issues a key", first.get("ok") and first["key"].startswith("ac_"), True)
    check("fulfilment is idempotent", second.get("already_issued") and second["key"] == first["key"], True)
    check("paid key carries an expiry", bool(first.get("expires_at")), True)
    check("issued key is on the paid tier", keys.identify(first["key"], "10.0.0.9")["tier"], "desk")
    keys.revoke_key(first["key"])
    check("revoked key drops to anonymous", keys.identify(first["key"], "10.0.0.9")["tier"], "anonymous")

    # 12. Expiry and renewal
    paid = keys.create_key("expiry-test", tier="pro", days=30)
    check("key created with expiry", bool(paid["expires_at"]), True)
    lapsed = keys.create_key("lapsed-test", tier="pro", days=-1)
    check("expired key is rejected", keys.verify_key(lapsed["key"]), None)
    check("expired key explains itself", keys.why_invalid(lapsed["key"]), "expired")
    check("expired key falls back to anonymous", keys.identify(lapsed["key"], "10.0.0.8")["tier"], "anonymous")

    extended = keys.extend_key(paid["key"], 30)
    check("renewal extends the key", extended and extended > paid["expires_at"], True)
    revived = keys.extend_key(lapsed["key"], 30)
    check("renewal revives a lapsed key", keys.verify_key(lapsed["key"]) is not None, True)
    check("revival returns a fresh expiry", bool(revived), True)

    renew_ref = f"renew-{first.get('renew_key', 'nope')}"
    renewed = billing.fulfil_payment(renew_ref, "pay_renew_1")
    check("renew reference extends instead of reissuing", renewed.get("renewed"), True)
    check("renewal keeps the same key", renewed.get("key"), first["key"])
    check("unknown renewal key is refused", billing.fulfil_payment("renew-deadbeef", "p").get("ok"), False)

    # inbound key requests (the /for-teams funnel)
    made = leads.create_request("Test Reporter", "reporter@newsroom.in", org="Test Desk",
                                use_case="triaging tipline photos", wanted_tier="pro")
    check("a valid request is stored", made.get("ok"), True)
    check("bad email is refused", leads.create_request("X", "not-an-email").get("ok"), False)
    check("one-word name is refused", leads.create_request("A", "a@b.co").get("ok"), False)
    unknown_plan = leads.create_request("Yash", "yash@b.co", wanted_tier="gold")
    stored = next(r for r in leads.list_requests(50) if r["id"] == unknown_plan["id"])
    check("an unknown plan falls back to free", stored["wanted_tier"], "free")
    before = leads.counts()["new"]
    check("requests are counted", before >= 1, True)
    check("a request can be marked issued", leads.mark_issued(made["id"], "ac_test_lead"), True)
    after = next(r for r in leads.list_requests(50) if r["id"] == made["id"])
    check("issued request keeps its key", after["status"], "issued")
    check("issuing drops the new count", leads.counts()["new"], before - 1)
    check("a spam request can be deleted", leads.delete_request(unknown_plan["id"]), True)
    check("deleting an unknown request is a no-op", leads.delete_request("nope"), False)

    # plan names must resolve to real key tiers, or the panel would 400
    check("starter plan maps to a real tier", billing.PLANS["starter"]["tier"] in keys.TIERS, True)
    check("pro plan maps to a real tier", billing.PLANS["pro"]["tier"] in keys.TIERS, True)

    # reconciliation is the net for a missing webhook. It short-circuits on a
    # reference that already has a key, so this path needs no network.
    settled = billing.reconcile_reference(ref)
    check("reconcile returns the key already issued", settled.get("key"), first["key"])
    check("reconcile is idempotent", billing.reconcile_reference(ref).get("already_issued"), True)
    swept = billing.reconcile_pending()
    check("reconcile sweep reports ok", swept.get("ok"), True)
    check("a fulfilled purchase is not swept again",
          any(s["reference"] == ref for s in swept["settled"]), False)

    # the public request form is spam-exposed; its throttle must actually bite
    gate_bucket = f"lead:selftest:{uuid.uuid4().hex[:6]}"
    allowed = [keys.check_rate(gate_bucket, "anonymous", limit_override=5)["allowed"] for _ in range(7)]
    check("lead throttle allows the first five", allowed[:5], [True] * 5)
    check("lead throttle blocks the sixth", allowed[5:], [False, False])
    check("the lead throttle is per bucket",
          keys.check_rate(f"lead:other:{uuid.uuid4().hex[:6]}", "anonymous", limit_override=5)["allowed"], True)

    passed = all(c["ok"] for c in CHECKS)
    return passed, CHECKS


def main() -> int:
    try:
        base = os.environ.get("AUTHCHECK_BASE_URL", "").rstrip("/")
        health = None
        if base:
            with urllib.request.urlopen(f"{base}/api/health", timeout=15) as r:
                health = json.load(r)

        passed, results = run_checks()
        for c in results:
            print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['name']}: got={c['got']} expect={c['expect']}")
        if health:
            print(f"live health: version={health.get('version')} layers={len(health.get('layers', []))}")

        failed = [c for c in results if not c["ok"]]
        if failed:
            print(f"\nREGRESSION: {len(failed)} check(s) failed")
            fire_callback("FAILED", "; ".join(c["name"] for c in failed))
            return 1
        print(f"\nAll {len(results)} checks passed")
        fire_callback("COMPLETED")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        fire_callback("FAILED", str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
