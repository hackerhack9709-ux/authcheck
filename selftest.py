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
import urllib.request
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core  # noqa: E402


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
