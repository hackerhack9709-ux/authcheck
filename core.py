"""AuthCheck analysis core - framework-free.

Pure functions over bytes/str so the same engine can be used by the web app,
the CLI and automations. No FastAPI, no I/O beyond optional HTTP calls.
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat
from PIL.ExifTags import TAGS

try:
    import piexif
except Exception:  # pragma: no cover
    piexif = None

VERSION = "0.5"
FACTCHECK_KEY = os.environ.get("FACTCHECK_API_KEY", "").strip()
MAX_UPLOAD = 25 * 1024 * 1024
MAX_VIDEO_UPLOAD = 100 * 1024 * 1024



# --------------------------------------------------------------------------- #
# 1. Provenance - C2PA / Content Credentials
# --------------------------------------------------------------------------- #
C2PA_MARKERS = [b"c2pa", b"jumb", b"jumbf", b"contentauth", b"cai:", b"urn:c2pa"]


def scan_c2pa(data: bytes) -> dict:
    low = data[: 4 * 1024 * 1024].lower()
    hits = [m.decode() for m in C2PA_MARKERS if m.lower() in low]
    present = bool(hits)
    # A real manifest also carries an X.509 chain + signature
    has_cert = b"-----begin certificate" in low or b"\x30\x82" in data[: 2 * 1024 * 1024]
    has_sig = b"c2pa.signature" in low or b"claim_signature" in low or b"c2pa.claim" in low
    return {
        "present": present,
        "markers": hits,
        "looks_like_full_manifest": bool(present and (has_cert or has_sig)),
        "note": (
            "C2PA/Content Credentials found - provenance data is attached."
            if present
            else "No C2PA Content Credentials found. Most cameras and apps still do "
            "not sign, so this alone does NOT mean the content is fake."
        ),
    }


# --------------------------------------------------------------------------- #
# 2. Metadata / EXIF
# --------------------------------------------------------------------------- #
AI_SIGNATURES = [
    "midjourney", "stable diffusion", "stablediffusion", "sdxl", "dall-e", "dall·e",
    "dalle", "firefly", "generative fill", "ai generated", "ai-generated", "comfyui",
    "automatic1111", "invokeai", "leonardo", "ideogram", "flux", "novelai", "playground ai",
    "made with google ai", "imagen", "grok", "bing image creator", "nightcafe",
]
EDIT_SIGNATURES = [
    "photoshop", "gimp", "lightroom", "snapseed", "picsart", "canva", "affinity",
    "pixelmator", "capture one", "darktable", "inkscape", "figma", "paint.net",
]


def read_exif(data: bytes) -> dict:
    out: dict[str, Any] = {"tags": {}, "has_exif": False, "software": None,
                           "camera": None, "gps": None, "datetime": None}
    try:
        img = Image.open(io.BytesIO(data))
        raw = img.getexif()
        if not raw:
            return out
        tags = {}
        for k, v in raw.items():
            name = TAGS.get(k, str(k))
            if isinstance(v, bytes):
                try:
                    v = v.decode("utf-8", "ignore")
                except Exception:
                    v = repr(v)
            tags[name] = v
        out["tags"] = {k: str(v)[:200] for k, v in tags.items()}
        out["has_exif"] = bool(tags)
        out["software"] = str(tags.get("Software", "")).strip() or None
        make = str(tags.get("Make", "")).strip()
        model = str(tags.get("Model", "")).strip()
        out["camera"] = (make + " " + model).strip() or None
        out["datetime"] = str(tags.get("DateTime", tags.get("DateTimeOriginal", ""))).strip() or None
        gps = tags.get("GPSInfo")
        if gps:
            out["gps"] = "present"
    except Exception as e:
        out["error"] = str(e)
    return out


def scan_signatures(exif: dict, data: bytes) -> dict:
    blob = (json.dumps(exif.get("tags", {})) + " " +
            (exif.get("software") or "")).lower()
    # also peek at XMP / trailing metadata
    blob += data[-65536:].decode("utf-8", "ignore").lower()
    ai = sorted({s for s in AI_SIGNATURES if s in blob})
    edit = sorted({s for s in EDIT_SIGNATURES if s in blob})
    return {"ai_tools": ai, "editors": edit}


# --------------------------------------------------------------------------- #
# 3. Forensics - Error Level Analysis
# --------------------------------------------------------------------------- #
def ela(data: bytes) -> dict:
    try:
        orig = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        return {"ok": False, "error": str(e)}

    buf = io.BytesIO()
    orig.save(buf, "JPEG", quality=90)
    buf.seek(0)
    recomp = Image.open(buf).convert("RGB")

    diff = ImageChops.difference(orig, recomp)
    stat = ImageStat.Stat(diff)
    mean = sum(stat.mean) / len(stat.mean)
    extrema = diff.getextrema()
    max_diff = max(e[1] for e in extrema) or 1

    scale = 255.0 / max_diff
    viz = diff.point(lambda p: p * scale)
    out = io.BytesIO()
    viz.save(out, "PNG")
    b64 = base64.b64encode(out.getvalue()).decode()

    # fraction of pixels with high error = likely edited regions
    gray = diff.convert("L")
    hist = gray.histogram()
    total = sum(hist) or 1
    hot = sum(hist[60:]) / total

    if mean < 1.2 and hot < 0.01:
        reading = "uniform - consistent with a single-pass original"
    elif hot > 0.06:
        reading = "hot spots - possible local edits / pasted regions"
    else:
        reading = "mixed - mild recompression or global edit"

    return {
        "ok": True,
        "mean": round(mean, 2),
        "max": int(max_diff),
        "hot_ratio": round(hot, 4),
        "reading": reading,
        "viz": "data:image/png;base64," + b64,
    }


def noise_profile(data: bytes) -> dict:
    """High-frequency energy + channel correlation as an AI-vs-camera tell."""
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return {}
    small = img.resize((256, 256))
    gray = small.convert("L")
    edge = gray.filter(__import__("PIL.ImageFilter", fromlist=["FIND_EDGES"]).FIND_EDGES)
    stat = ImageStat.Stat(edge)
    hf = sum(stat.mean) / len(stat.mean)
    # channel correlation: AI images often have very smooth channels
    r, g, b = small.split()
    def corr(a, b):
        sa, sb = ImageStat.Stat(a), ImageStat.Stat(b)
        ma, mb = sa.mean[0], sb.mean[0]
        da = ImageStat.Stat(a, mask=None)
        return round(1 - abs(ma - mb) / 255.0, 3)
    return {
        "high_freq_energy": round(hf, 2),
        "channel_balance": {"rg": corr(r, g), "gb": corr(g, b)},
    }


# --------------------------------------------------------------------------- #
# 4. AI-generation heuristics
# --------------------------------------------------------------------------- #
AI_DIMS = {(512, 512), (768, 768), (1024, 1024), (1024, 1792), (1792, 1024),
           (896, 1152), (1152, 896), (1344, 768), (768, 1344), (1536, 1024),
           (1024, 1536), (2048, 2048), (1152, 1152)}


def ai_heuristics(data: bytes, exif: dict, sigs: dict) -> list[dict]:
    signals: list[dict] = []
    try:
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        fmt = img.format
    except Exception:
        return signals

    if sigs["ai_tools"]:
        signals.append({"level": "high", "weight": 45,
                        "text": f"AI tool signature in metadata: {', '.join(sigs['ai_tools'])}"})
    if (w, h) in AI_DIMS:
        signals.append({"level": "medium", "weight": 18,
                        "text": f"Dimensions {w}x{h} match common AI generator output"})
    if w == h and w >= 768:
        signals.append({"level": "low", "weight": 10,
                        "text": f"Perfect square {w}x{h} - common for AI, rare for cameras"})
    if not exif.get("has_exif"):
        signals.append({"level": "medium", "weight": 15,
                        "text": "No EXIF at all - stripped or never present (social media, "
                                "AI generators, screenshots all do this)"})
    if not exif.get("camera") and exif.get("has_exif"):
        signals.append({"level": "low", "weight": 8,
                        "text": "EXIF present but no camera make/model"})
    if sigs["editors"]:
        signals.append({"level": "low", "weight": 5,
                        "text": f"Edited with: {', '.join(sigs['editors'])} - editing is normal, "
                                "but the file is not a straight-out-of-camera original"})
    if exif.get("gps"):
        signals.append({"level": "info", "weight": -5,
                        "text": "GPS coordinates present - consistent with a real capture device"})
    if exif.get("camera"):
        signals.append({"level": "info", "weight": -12,
                        "text": f"Camera metadata present: {exif['camera']}"})
    return signals


# --------------------------------------------------------------------------- #
# 5. Text / claim checks
# --------------------------------------------------------------------------- #
SENSATIONAL = [
    "shocking", "breaking", "urgent", "must share", "forward this", "viral",
    "exposed", "they don't want you to know", "wake up", "share before deleted",
    "100% proof", "cure", "miracle", "secret", "conspiracy", "banned",
]
ABSOLUTIST = ["always", "never", "everyone", "no one", "all", "none", "proves", "guaranteed"]

# Multilingual red-flag lexicons. Keys are ISO-ish language codes.
LEXICONS: dict[str, dict[str, list[str]]] = {
    "en": {"sensational": SENSATIONAL, "absolutist": ABSOLUTIST},
    "hi": {
        "sensational": [
            "चौंकाने", "चौकाने", "वायरल", "जरूर शेयर", "ज़रूर शेयर", "सच्चाई", "बेनकाब",
            "खतरनाक", "सनसनी", "शेयर करो", "फॉरवर्ड करो", "डिलीट", "अभी शेयर",
            "बड़ा खुलासा", "किसी को न बताएं", "इलाज", "चमत्कार", "गुप्त", "साजिश",
            "प्रतिबंध", "व्हायरल", "देखो", "जल्दी करो", "आगे भेजो",
        ],
        "absolutist": ["हमेशा", "कभी नहीं", "सब", "कोई नहीं", "साबित", "पक्का", "100%"],
    },
    "ur": {
        "sensational": [
            "چونکا دینے", "وائرل", "ضرور شیئر", "حقیقت", "بے نقاب", "خطرناک", "سنسنی",
            "شیئر کریں", "فارورڈ کریں", "ڈیلیٹ", "ابھی شیئر", "بڑا انکشاف", "کسی کو نہ بتائیں",
            "علاج", "معجزہ", "خفیہ", "سازش", "پابندی",
        ],
        "absolutist": ["ہمیشہ", "کبھی نہیں", "سب", "کوئی نہیں", "ثابت", "پکا"],
    },
    "bn": {
        "sensational": ["ভাইরাল", "শেয়ার করুন", "ফরওয়ার্ড করুন", "সত্যি", "বেপর্দা",
                        "বিপজ্জনক", "চাঞ্চল্যকর", "গোপন", "চক্রান্ত", "নিষিদ্ধ"],
        "absolutist": ["সবসময়", "কখনও নয়", "সবাই", "কেউ না", "প্রমাণ"],
    },
    "mr": {
        "sensational": ["व्हायरल", "शेअर करा", "फॉरवर्ड करा", "सत्य", "उघड",
                        "धोकादायक", "गुप्त", "कट", "बंदी"],
        "absolutist": ["नेहमी", "कधीच नाही", "सर्व", "कोणीही नाही"],
    },
    "ta": {
        "sensational": ["வைரல்", "பகிரவும்", "உண்மை", "அம்பலம்", "ஆபத்தான", "ரகசியம்"],
        "absolutist": ["எப்போதும்", "ஒருபோதும்", "அனைவரும்"],
    },
    "es": {
        "sensational": ["impactante", "urgente", "comparte", "viral", "expuesto",
                        "no quieren que sepas", "despierta", "cura", "milagro",
                        "secreto", "conspiración", "prohibido", "100% prueba"],
        "absolutist": ["siempre", "nunca", "todos", "nadie", "prueba", "garantizado"],
    },
}

# Script / script-range detection so we can pick a lexicon without a language model.
SCRIPT_RANGES = {
    "hi": [(0x0900, 0x097F)],       # Devanagari
    "mr": [(0x0900, 0x097F)],       # Devanagari (Marathi)
    "ur": [(0x0600, 0x06FF), (0x0750, 0x077F)],  # Arabic script
    "bn": [(0x0980, 0x09FF)],       # Bengali
    "ta": [(0x0B80, 0x0BFF)],       # Tamil
    "te": [(0x0C00, 0x0C7F)],       # Telugu
    "gu": [(0x0A80, 0x0AFF)],       # Gujarati
    "kn": [(0x0C80, 0x0CFF)],       # Kannada
    "pa": [(0x0A00, 0x0A7F)],       # Gurmukhi
}


def detect_language(text: str) -> str:
    """Cheap script-based language guess. Falls back to 'en'."""
    counts: dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        for lang, ranges in SCRIPT_RANGES.items():
            if any(lo <= cp <= hi for lo, hi in ranges):
                counts[lang] = counts.get(lang, 0) + 1
                break
    if not counts:
        return "en"
    return max(counts, key=counts.get)


def check_text(text: str, lang: str | None = None, include_references: bool = True) -> dict:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty text"}

    lang = lang or detect_language(text)
    lex = LEXICONS.get(lang, LEXICONS["en"])
    lower = text.lower()
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    n = max(len(words), 1)
    caps = sum(1 for c in text if c.isupper())
    letters = sum(1 for c in text if c.isalpha()) or 1
    exclaims = text.count("!") + text.count("।") + text.count("؟")
    qmarks = text.count("?") + text.count("؟")

    flags: list[dict] = []

    hits = [s for s in lex["sensational"] if s in lower]
    if hits:
        flags.append({"level": "high", "weight": 22,
                      "text": f"Sensational / forward-bait language: {', '.join(hits[:5])}"})
    ab = [a for a in lex["absolutist"] if a in lower]
    if ab:
        flags.append({"level": "medium", "weight": 12,
                      "text": f"Absolutist words: {', '.join(ab[:5])}"})
    if letters and caps / letters > 0.4 and len(words) > 4:
        flags.append({"level": "medium", "weight": 12,
                      "text": f"Heavy capitalisation ({round(caps/letters*100)}% of letters)"})
    if exclaims >= 2:
        flags.append({"level": "medium", "weight": 10,
                      "text": f"{exclaims} exclamation marks"})
    if re.search(r"\b(study|research|scientists|experts|sources?)\b", lower) and \
       not re.search(r"(https?://|www\.|\b(19|20)\d{2}\b|journal|university|doi)", lower):
        flags.append({"level": "medium", "weight": 14,
                      "text": "Appeals to unnamed 'experts/studies' but cites no source"})
    if not re.search(r"(https?://|www\.)", lower) and len(words) > 25:
        flags.append({"level": "low", "weight": 8,
                      "text": "No link or source given"})
    if re.search(r"\b(share|forward|circulate)\b", lower) or \
       any(k in lower for k in ("शेयर", "फॉरवर्ड", "شیئر", "فارورڈ", "শেয়ার", "পাঠান",
                                "comparte", "reenvía", "पाठवा")):
        flags.append({"level": "medium", "weight": 10,
                      "text": "Asks you to share/forward - classic viral-misinfo pattern"})

    score = max(0, min(100, 100 - sum(f["weight"] for f in flags)))

    verdict = ("likely-misleading" if score < 40 else
               "caution" if score < 70 else "no red flags")

    factcheck = None
    if FACTCHECK_KEY:
        factcheck = query_factcheck(text)

    references = lookup_references(text) if include_references else None

    return {
        "ok": True,
        "score": score,
        "verdict": verdict,
        "language": lang,
        "language_supported": lang in LEXICONS,
        "flags": flags,
        "factcheck": factcheck,
        "factcheck_available": bool(FACTCHECK_KEY),
        "references": references,
        "word_count": len(words),
    }


def query_factcheck(text: str) -> dict:
    q = urllib.parse.quote(text[:300])
    url = ("https://factchecktools.googleapis.com/v1alpha1/claims:search"
           f"?query={q}&pageSize=5&key={FACTCHECK_KEY}")
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.load(r)
        claims = data.get("claims", [])
        return {
            "count": len(claims),
            "matches": [
                {
                    "text": c.get("text", "")[:200],
                    "claimant": c.get("claimant", ""),
                    "reviews": [
                        {
                            "publisher": (rv.get("publisher") or {}).get("name", ""),
                            "rating": rv.get("textualRating", ""),
                            "url": rv.get("url", ""),
                        }
                        for rv in c.get("claimReview", [])
                    ],
                }
                for c in claims
            ],
        }
    except Exception as e:
        return {"error": str(e)}


# --------------------------------------------------------------------------- #
# 4b. Keyless reference lookup (no API key needed)
# --------------------------------------------------------------------------- #
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "of", "to",
    "in", "on", "at", "by", "for", "with", "about", "as", "into", "like", "through",
    "after", "over", "between", "out", "against", "during", "without", "before",
    "under", "around", "among", "and", "but", "or", "if", "then", "than", "that",
    "this", "these", "those", "it", "its", "he", "she", "they", "them", "his", "her",
    "their", "we", "you", "i", "me", "my", "our", "your", "who", "what", "which",
    "when", "where", "why", "how", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "too", "very", "can", "will", "just", "should", "now", "says", "said",
}


def key_terms(text: str, limit: int = 6) -> list[str]:
    """Pull the most informative words out of a claim for a reference search."""
    words = re.findall(r"[^\W\d_]{3,}", text, flags=re.UNICODE)
    seen, out = set(), []
    for w in words:
        lw = w.lower()
        if lw in STOPWORDS or lw in seen:
            continue
        seen.add(lw)
        out.append(w)
    return out[:limit]


def _http_json(url: str, timeout: float = 8.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "AuthCheck/0.4 (authenticity desk)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def lookup_references(text: str) -> dict:
    """Keyless cross-check: Wikipedia pages + DuckDuckGo instant answers.

    This is context, not a verdict. A hit means 'here is background on this',
    never 'this claim is true' - that distinction is stated in the payload.
    """
    terms = key_terms(text)
    query = " ".join(terms) or text[:120]
    out: dict[str, Any] = {
        "provider": "wikipedia+duckduckgo",
        "query": query,
        "terms": terms,
        "note": "Background references only. A hit does not make the claim true.",
        "wikipedia": [],
        "instant_answers": [],
        "errors": [],
    }

    if not query.strip():
        return out

    term_set = {t.lower() for t in terms}

    def relevance(*chunks: str) -> int:
        """How many search terms appear; title matches weigh more than body."""
        score = 0
        for i, chunk in enumerate(chunks):
            low = (chunk or "").lower()
            weight = 3 if i == 0 else 1
            score += weight * sum(1 for t in term_set if t in low)
        return score

    try:
        wp = _http_json(
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={urllib.parse.quote(query)}&format=json&srlimit=8"
        )
        ranked = []
        for hit in (wp.get("query", {}).get("search") or []):
            title = hit.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", hit.get("snippet", ""))
            score = relevance(title, snippet)
            if score == 0:
                continue
            ranked.append((score, {
                "title": title,
                "snippet": snippet,
                "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                "relevance": score,
            }))
        ranked.sort(key=lambda x: -x[0])
        out["wikipedia"] = [r[1] for r in ranked[:4]]
    except Exception as e:
        out["errors"].append(f"wikipedia: {type(e).__name__}: {e}")

    try:
        ddg = _http_json(
            "https://api.duckduckgo.com/?q=" + urllib.parse.quote(query)
            + "&format=json&no_html=1&skip_disambig=1"
        )
        candidates = []
        if ddg.get("AbstractText"):
            candidates.append({
                "heading": ddg.get("Heading", ""),
                "text": ddg.get("AbstractText", "")[:400],
                "url": ddg.get("AbstractURL", ""),
                "source": ddg.get("AbstractSource", ""),
            })
        for topic in (ddg.get("RelatedTopics") or []):
            if topic.get("Text"):
                candidates.append({
                    "heading": topic.get("Text", "").split(" - ")[0][:80],
                    "text": topic.get("Text", "")[:300],
                    "url": (topic.get("FirstURL") or ""),
                    "source": "DuckDuckGo",
                })
        scored = [(relevance(c["heading"], c["text"]), c) for c in candidates]
        scored = [(s, c) for s, c in scored if s > 0]
        scored.sort(key=lambda x: -x[0])
        out["instant_answers"] = [c for _, c in scored[:3]]
    except Exception as e:
        out["errors"].append(f"duckduckgo: {type(e).__name__}: {e}")

    out["hit_count"] = len(out["wikipedia"]) + len(out["instant_answers"])
    if not out["errors"]:
        out.pop("errors")
    return out


# --------------------------------------------------------------------------- #
# 5b. Audio analysis (no ML - signal + metadata heuristics)
# --------------------------------------------------------------------------- #
AUDIO_AI_SIGNATURES = ["suno", "udio", "elevenlabs", "descript", "murf", "resemble",
                       "play.ht", "speechify", "rvc", "so-vits", "vits", "tortoise",
                       "bark", "coqui", "tacotron", "ai voice", "text-to-speech"]


def analyze_audio_bytes(data: bytes, filename: str) -> dict:
    c2pa = scan_c2pa(data)
    low = data[: 2 * 1024 * 1024].lower()
    ai_hits = sorted({s for s in AUDIO_AI_SIGNATURES if s.encode() in low})

    # container sniffing
    container = "unknown"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        container = "wav"
    elif data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        container = "mp3"
    elif data[4:8] == b"ftyp":
        container = "m4a/mp4"
    elif data[:4] == b"OggS":
        container = "ogg"
    elif data[:4] == b"fLaC":
        container = "flac"

    info: dict[str, Any] = {"container": container, "size_bytes": len(data)}
    signals: list[dict] = []
    score = 50

    # WAV header parse for sample rate / channels / bit depth
    if container == "wav" and len(data) > 44:
        import struct
        try:
            ch, sr, _, _, bits = struct.unpack("<HIIHH", data[22:36])
            info.update(channels=ch, sample_rate=sr, bit_depth=bits)
            if bits and bits >= 24:
                signals.append({"level": "info", "weight": -6,
                                "text": f"High bit depth ({bits}-bit) - typical of real recordings"})
            if sr and sr not in (8000, 11025, 16000, 22050, 24000, 44100, 48000, 96000, 192000):
                signals.append({"level": "low", "weight": 6,
                                "text": f"Unusual sample rate {sr} Hz - often from a TTS/upsampler"})
        except Exception:
            pass

    if ai_hits:
        signals.append({"level": "high", "weight": 40,
                        "text": f"AI voice / TTS tool signature in file: {', '.join(ai_hits)}"})
    if not c2pa["present"]:
        signals.append({"level": "info", "weight": 0,
                        "text": "No C2PA credentials (normal for most audio)"})

    # amplitude / silence / clipping analysis on decoded PCM if we can decode it
    try:
        import wave
        w = wave.open(io.BytesIO(data))
        n = min(w.getnframes(), w.getframerate() * 60)
        raw = w.readframes(n)
        import array
        samples = array.array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if samples:
            peak = max(abs(s) for s in samples) or 1
            rms = math.sqrt(sum(s * s for s in samples) / len(samples))
            # clipping: samples pinned near full scale
            clip = sum(1 for s in samples if abs(s) > 31000) / len(samples)
            # silence runs
            win = max(1, w.getframerate() // 50)
            sil = 0
            for i in range(0, len(samples) - win, win):
                seg = samples[i:i + win]
                if max(abs(x) for x in seg) < 200:
                    sil += 1
            silence_ratio = sil / max(1, len(samples) // win)
            info.update(peak=peak, rms=round(rms, 1),
                        clipping_ratio=round(clip, 5),
                        silence_ratio=round(silence_ratio, 4))
            if clip > 0.002:
                signals.append({"level": "medium", "weight": 10,
                                "text": f"Hard clipping in {round(clip*100,2)}% of samples - "
                                        "re-encoded or over-amplified"})
            if silence_ratio > 0.35:
                signals.append({"level": "medium", "weight": 12,
                                "text": f"Long silent stretches ({round(silence_ratio*100)}%) - "
                                        "stitched / generated segments"})
            if rms < 50:
                signals.append({"level": "low", "weight": 6,
                                "text": "Very low overall level - possibly synthesised quietly then normalised"})
    except Exception as e:
        info["decode_note"] = f"PCM analysis skipped: {type(e).__name__}"

    for s in signals:
        score -= s["weight"]
    score = max(0, min(100, score))
    band = "lower risk" if score >= 70 else "unclear - check sources" if score >= 45 else "higher risk"

    return {
        "ok": True,
        "filename": filename,
        "c2pa": c2pa,
        "audio": info,
        "signatures": {"ai_voice_tools": ai_hits},
        "heuristics": signals,
        "verdict": {
            "score": score,
            "band": band,
            "reasons": [s["text"] for s in signals],
            "disclaimer": "Audio heuristics are weaker than image provenance. A clean result "
                          "is not proof of authenticity, and a flagged one is not proof of faking.",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------- #
# 5c. Video analysis (keyframe sampling, no ML)
# --------------------------------------------------------------------------- #
VIDEO_AI_SIGNATURES = AUDIO_AI_SIGNATURES + [
    "runway", "pika", "luma", "sora", "kling", "hailuo", "veo", "gen-2", "gen-3",
    "stable video", "svd", "animatediff", "deforum", "kaiber", "pictory", "synthesia",
    "heygen", "d-id", "deepfake", "face swap", "faceswap", "roop", "simswap",
]


def _ffmpeg_path() -> str | None:
    """Locate an ffmpeg binary: env override, PATH, or the pip-bundled static build."""
    override = os.environ.get("FFMPEG_BIN", "").strip()
    if override and Path(override).exists():
        return override
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def probe_video(data: bytes) -> dict:
    """Read container/stream facts without decoding frames."""
    ff = _ffmpeg_path()
    if not ff:
        return {"available": False, "error": "ffmpeg not found"}
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tf:
        tf.write(data)
        path = tf.name
    try:
        r = subprocess.run([ff, "-i", path], capture_output=True, text=True, timeout=30)
        err = r.stderr
        out: dict[str, Any] = {"available": True, "raw_ok": r.returncode == 0}
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", err)
        if m:
            h, mi, s, cs = (int(x) for x in m.groups())
            out["duration_seconds"] = round(h * 3600 + mi * 60 + s + cs / 100, 2)
        vm = re.search(r"Video:\s*([a-z0-9]+).*?(\d{2,5})x(\d{2,5})", err)
        if vm:
            out["codec"], out["width"], out["height"] = vm.group(1), int(vm.group(2)), int(vm.group(3))
        am = re.search(r"Audio:\s*([a-z0-9]+)", err)
        if am:
            out["audio_codec"] = am.group(1)
        fr = re.search(r"(\d+(?:\.\d+)?)\s*fps", err)
        if fr:
            out["fps"] = float(fr.group(1))
        bm = re.search(r"bitrate:\s*(\d+)\s*kb/s", err)
        if bm:
            out["bitrate_kbps"] = int(bm.group(1))
        out["has_audio_track"] = bool(am)
        out["tool_signature_hits"] = [s for s in VIDEO_AI_SIGNATURES if s in err.lower()]
        return out
    except Exception as e:
        return {"available": True, "error": f"{type(e).__name__}: {e}"}
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def extract_keyframes(data: bytes, max_frames: int = 6) -> list[bytes]:
    """Sample evenly spaced frames as PNG bytes, scaled down for speed."""
    ff = _ffmpeg_path()
    if not ff:
        return []
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tf:
        tf.write(data)
        path = tf.name
    tmpdir = tempfile.mkdtemp(prefix="acframes")
    try:
        # fps filter at a low rate gives evenly spaced frames without a full decode pass
        r = subprocess.run(
            [ff, "-i", path, "-vf", "fps=1/2,scale=640:-1", "-frames:v", str(max_frames),
             "-f", "image2", f"{tmpdir}/f%02d.png"],
            capture_output=True, text=True, timeout=60,
        )
        frames = []
        for p in sorted(Path(tmpdir).glob("f*.png")):
            frames.append(p.read_bytes())
        if not frames:
            # very short clip: grab a single first frame
            single = f"{tmpdir}/single.png"
            subprocess.run([ff, "-i", path, "-frames:v", "1", "-vf", "scale=640:-1", single],
                           capture_output=True, text=True, timeout=30)
            if Path(single).exists():
                frames.append(Path(single).read_bytes())
        return frames
    except Exception:
        return []
    finally:
        import shutil
        try:
            os.unlink(path)
        except Exception:
            pass
        shutil.rmtree(tmpdir, ignore_errors=True)


def analyze_video_bytes(data: bytes, filename: str) -> dict:
    """Container facts + per-keyframe image analysis, blended into one verdict."""
    info = probe_video(data)
    if not info.get("available"):
        return {"ok": False, "error": info.get("error", "ffmpeg unavailable"),
                "hint": "Install ffmpeg, or pip install imageio-ffmpeg"}

    frames = extract_keyframes(data)
    frame_reports = []
    for i, fb in enumerate(frames):
        exif = read_exif(fb)
        sigs = scan_signatures(exif, fb)
        heur = ai_heuristics(fb, exif, sigs)
        v = fuse(scan_c2pa(fb), exif, sigs, ela(fb), heur)
        frame_reports.append({"index": i, "score": v["score"], "band": v["band"],
                              "reasons": v["reasons"][:4]})

    signals: list[dict] = []
    score = 50

    if info.get("tool_signature_hits"):
        hits = info["tool_signature_hits"]
        signals.append({"level": "high", "weight": 26,
                        "text": f"Container metadata names generative/editing tools: {', '.join(hits[:5])}"})
        score -= 26

    fps = info.get("fps")
    if fps and (fps < 8 or fps > 120):
        signals.append({"level": "medium", "weight": 10,
                        "text": f"Unusual frame rate ({fps} fps)"})
        score -= 10

    w, h = info.get("width"), info.get("height")
    if w and h:
        ratio = w / h
        common = [(16, 9), (9, 16), (4, 3), (3, 4), (1, 1), (21, 9), (9, 21)]
        if not any(abs(ratio - a / b) < 0.02 for a, b in common):
            signals.append({"level": "low", "weight": 6,
                            "text": f"Non-standard aspect ratio ({w}x{h})"})
            score -= 6

    if not info.get("has_audio_track"):
        signals.append({"level": "low", "weight": 5,
                        "text": "No audio track (common in generated clips, but also in silent footage)"})
        score -= 5

    if info.get("duration_seconds") is not None and info["duration_seconds"] < 2:
        signals.append({"level": "medium", "weight": 8,
                        "text": f"Very short clip ({info['duration_seconds']}s) - hard to verify"})
        score -= 8

    if frame_reports:
        avg = sum(f["score"] for f in frame_reports) / len(frame_reports)
        # keyframes carry half the weight; container facts carry the rest
        score = round(0.5 * score + 0.5 * avg)
        worst = min(frame_reports, key=lambda f: f["score"])
        if worst["score"] < 45:
            signals.append({"level": "high", "weight": 12,
                            "text": f"Keyframe {worst['index']} scores low ({worst['score']}): "
                                    f"{'; '.join(worst['reasons'][:2])}"})
            score -= 12
    else:
        signals.append({"level": "medium", "weight": 10,
                        "text": "Could not decode frames - verdict relies on container facts only"})
        score -= 10

    score = max(0, min(100, score))
    band = "lower risk" if score >= 70 else "unclear" if score >= 45 else "higher risk"

    return {
        "ok": True,
        "filename": filename,
        "size_bytes": len(data),
        "container": info,
        "keyframes_analysed": len(frame_reports),
        "keyframes": frame_reports,
        "heuristics": signals,
        "verdict": {
            "score": score,
            "band": band,
            "reasons": [s["text"] for s in signals] or ["No container or keyframe anomalies found"],
            "disclaimer": "Video checks read container metadata and sampled frames. They do not "
                          "run a lip-sync or temporal-consistency model, so a clean result is "
                          "weaker evidence than for images.",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------- #
# 6. Fusion
# --------------------------------------------------------------------------- #
def fuse(c2pa: dict, exif: dict, sigs: dict, ela_r: dict, heur: list[dict]) -> dict:
    # Score = trust. Positive weight = risk signal (lowers trust);
    # negative weight = authenticity evidence (raises trust).
    score = 50
    reasons: list[str] = []

    if c2pa.get("present"):
        score += 30
        reasons.append("C2PA Content Credentials present (+30)")
        if c2pa.get("looks_like_full_manifest"):
            reasons.append("Manifest looks complete with cert/signature")
    else:
        reasons.append("No provenance credentials (neutral - most content has none)")

    for h in heur:
        score -= h["weight"]
        reasons.append(f"{h['text']} ({-h['weight']:+d})")

    if ela_r.get("ok"):
        if ela_r["hot_ratio"] > 0.06:
            score -= 10
            reasons.append(f"ELA shows edit hot-spots ({ela_r['hot_ratio']}) (-10)")

    score = max(0, min(100, score))
    if score >= 70:
        band = "lower risk"
    elif score >= 45:
        band = "unclear - check sources"
    else:
        band = "higher risk"

    return {"score": score, "band": band, "reasons": reasons,
            "disclaimer": "No automated tool can prove content is true. Missing "
                          "credentials do not mean fake. Always check the original source."}

