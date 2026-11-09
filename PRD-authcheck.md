# AuthCheck — Product Requirements Document (PRD)

**Version:** 0.1 (working prototype live)
**Date:** 2026-11-09
**Status:** Prototype deployed on port 12000

---

## 1. Problem

Anyone with a phone can now generate convincing fake images, audio and video, and
misinformation spreads faster than corrections. Ordinary people have no tool that
answers *"is this real?"* with a reason. Journalists have InVID, enterprises have
Hive/NewsGuard — but there is **nothing free, multilingual, and explainable** for
the general public, especially in Hindi/Urdu/regional languages.

## 2. Goal

A free, open, multilingual web tool that takes an **image** or a **claim (text)**
and returns a **trust score plus the reasons**, never a bare yes/no.

## 3. Non-goals

- We do not claim to prove truth. We surface *signals*.
- Not a moderation API for platforms (yet).
- Not storing user uploads beyond the request.

## 4. Users

| User | Need |
|---|---|
| Common citizen (WhatsApp forward) | "Is this photo/claim real?" |
| Journalist / fact-checker | Fast first-pass triage + provenance check |
| Student / researcher | Understandable explanation of the signals |
| Platform trust & safety | Bulk API (future) |

## 5. Requirements

### P0 (in prototype — done)
- **R1** Image upload → multi-layer analysis
- **R2** C2PA / Content Credentials presence + manifest completeness
- **R3** EXIF extraction: camera, software, GPS, date
- **R4** AI-tool signature detection (Midjourney, DALL·E, Firefly, SD, …)
- **R5** Error Level Analysis (edit hot-spot visualisation)
- **R6** AI-generation heuristics (dimensions, missing metadata, noise)
- **R7** Fused trust score 0–100 + band + reason list
- **R8** Reverse-image-search links (Google/Yandex/Bing/TinEye)
- **R9** Text claim checker with misinformation language flags
- **R10** Explicit disclaimer ("absence ≠ fake")

### P1 (next)
- **R11** Google Fact Check Tools API integration (key already supported via env)
- **R12** Audio deepfake detection (`dessa-oss/fake-voice-detection`)
- **R13** Video: keyframe extraction + per-frame deepfake score
- **R14** Hindi/Urdu language packs for the text checker
- **R15** Source-reliability rating (NewsGuard-style nutrition label, free)
- **R16** Browser extension (right-click → check)

### P2 (later)
- **R17** Public REST API + rate limits
- **R18** On-device (WASM/ONNX) inference for privacy
- **R19** Provenance signing for creators (C2PA create side)
- **R20** EU AI Act Article 50 compliance reporting

## 6. Success metrics

- Time-to-verdict < 5s per image
- Reason list present on 100% of verdicts
- False-confidence rate (says "real" on a known fake) tracked and minimised
- Adoption: weekly checks, returning users

## 7. Architecture

```
Upload → C2PA scan → EXIF/signatures → ELA → heuristics
                                              ↓
                     Fact-check API ← Text path
                                              ↓
                                  Fusion (score + reasons)
                                              ↓
                                        UI / JSON
```

**Stack:** FastAPI + Pillow + piexif (prototype). Roadmap: c2pa-rs binding,
HF ViT models, ONNX for on-device.

## 8. Design principles

1. Never a bare verdict — always "why".
2. Absence of credentials ≠ fake.
3. Provenance weighted highest (cryptographic).
4. Privacy-first; no upload retention.
5. Multilingual from day one.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Classifiers fooled by adversarial AI | Weight provenance highest; show uncertainty |
| Watermarks stripped (26k★ remover exists) | Treat as one signal only |
| Over-trust in the score | Always show reasons + disclaimer |
| No C2PA adoption yet | "Missing" is neutral, explained in UI |
| Indian-language data scarcity | Partner with fact-check orgs; community labels |

## 10. Open questions

- Which language packs first? (Hindi + Urdu proposed)
- Self-host the ML models or call APIs?
- Free forever or freemium for API tier?
