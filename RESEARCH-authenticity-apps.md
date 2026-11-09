# Authenticity / Verification Apps — Research Report

**Goal:** Apps that check *"is this content real?"* — news, images, video, audio — so
misinformation and deepfakes can be caught. Research done: 2026-11-09.

---

## 1. The problem (why this matters)

Generative AI made it cheap to create fake images, video, audio and text. Three
distinct problems, often confused:

| Problem | Question it answers | Detection approach |
|---|---|---|
| **Provenance** | Where did this come from? Was it edited? | Cryptographic signatures (C2PA) |
| **Synthetic media** | Is this AI-generated / a deepfake? | ML classifiers + watermarking |
| **Misinformation** | Is this *claim* factually true? | Fact-check matching, source rating |

A real product needs **all three**. No single technique covers them.

---

## 2. Provenance — C2PA / Content Credentials (the strongest signal)

**What it is:** An open standard (Coalition for Content Provenance and Authenticity,
now a Linux Foundation / Joint Development Foundation project) that embeds a signed
"manifest" into a file. The manifest records: who created it, what device/app,
what edits happened, and cryptographic hashes of the content.

**Key concepts (from CAI docs):**
- **Manifest** = assertions + claim + signature
- **Assertion** = structured fact (e.g. "cropped", "created by camera X")
- **Hard binding** = cryptographic hash of content → any edit breaks it
- **Soft binding** = watermark / perceptual fingerprint → survives metadata stripping
- **Trust list** = C2PA-maintained certificate anchors; a valid signature is not
  automatically a *trusted* signer

**Important limitation (quote):** validation proves *integrity* and *signer identity*.
It does **not** prove the content is true. And *"Missing Content Credentials do not,
by themselves, indicate that content is false."*

**Open-source tooling:**
| Repo | What | Stars |
|---|---|---|
| `contentauth/c2pa-rs` | Rust SDK (core), C FFI, Python/JS/Node bindings | 444 |
| `c2pa-org/specifications` | Public spec | 214 |
| CAI open-source SDK | Python, JS, Node, C++, mobile libs | — |

Latest release observed: `c2pa-c-ffi-v0.91.11` (2026-11-04).

**Storage options:** embedded in file / sidecar `.c2pa` file / remote (URL reference).
**"Durable Content Credentials"** = stored manifests + soft binding + lookup service,
so provenance can be recovered even after metadata is stripped.

**Who backs it:** Adobe, Microsoft, Google, OpenAI, Leica, Nikon, Sony, BBC, AP, etc.

---

## 3. AI watermarking (complementary to C2PA)

| Tool | Owner | Covers | Notes |
|---|---|---|---|
| **SynthID** | Google DeepMind | image, video, audio, text | Imperceptible; survives crop, filter, frame-rate change, lossy compression, MP3, speed change |
| **SynthID Detector** | Google | verification portal | Public; detects Google + partners (OpenAI, NVIDIA, Kakao, soon Apple) |

**Critical caveat:** watermark-removal is a real, popular open-source category.
Examples found on GitHub: `guillaumemeyer/watermarks-remover` (26.8k stars),
`wiltodelta/remove-ai-watermarks` (6.3k), `mertizci/noai-watermark` (224).
→ Watermarks alone are **not** a reliable detection strategy. Use as one signal.

---

## 4. Synthetic-media detection — open models & benchmarks

**Detection models (HuggingFace):**
| Model | Downloads |
|---|---|
| `dima806/deepfake_vs_real_image_detection` | 4,310 |
| `dima806/ai_vs_human_generated_image_detection` | 2,067 |
| `Wvolf/ViT_Deepfake_Detection` | 910 |
| `aaronkantrowitz/ai-human-generated-image-detection` | 653 |
| `onnx-community/ai-human-generated-image-detection-ONNX` | browser-ready |

**Benchmarks / datasets:**
| Repo | Stars | What |
|---|---|---|
| `SCLBD/DeepfakeBench` | 1,138 | Comprehensive deepfake detection benchmark |
| `Daisy-Zhang/Awesome-Deepfakes-Detection` | 1,851 | Paper/code list |
| `laiyingxin2/DADF` | 461 | Segment-Anything + face-forgery |
| `dessa-oss/fake-voice-detection` | 390 | Audio deepfake (temporal conv) |
| `YZY-stack/DF40` | 353 | Next-gen dataset (40 methods) |

**Reference product:** **TrueMedia** (Georgetown University) — non-partisan, open
source, free. Assesses text, images, audio for manipulation. Good model to study.

---

## 5. Misinformation / fact-check layer

**Google Fact Check Tools API** (free):
```
GET https://factchecktools.googleapis.com/v1alpha1/claims:search?query=<text>
```
Searches a database of fact-checked claims (ClaimReview). Params: `query`,
`languageCode`, `reviewPublisherSiteFilter`, `maxAgeDays`, `pageSize`, `pageToken`.
Also `v1alpha1/pages:list` and `pages:get`. This is the cheapest way to add
"has this claim already been fact-checked?" to an app.

**Source reliability rating:** NewsGuard (commercial) rates news sources on 9
criteria and publishes a "Nutrition Label". Model worth copying for a free version.

**Open datasets:**
| Dataset | Downloads |
|---|---|
| `GonzaloA/fake_news` | 1,367 |
| `jcblaise/fake_news_filipino` | 889 |
| `community-datasets/fake_news_english` | 246 |
| `community-datasets/urdu_fake_news` | 239 |
| `daviddaubner/misinformation-detection` | 84 |

**Notable multilingual gap:** Indian languages (Hindi, Urdu) have very few datasets.
`community-datasets/urdu_fake_news` is one of the few.

**Multimodal / research projects:**
- `ICTMCG/FakeSV` (185) — multimodal benchmark
- `MischaQI/Sniffer` (88) — explainable out-of-context detection
- `liuxuannan/MMFakeBench` (ICLR 2025) — mixed-source multimodal
- `safe-graph/GNN-FakeNews` (557) — graph-based detection

---

## 6. Reverse search & forensics (the journalist toolkit)

**InVID / WeVerify Verification Plugin** (MIT licence, open source, free):
`github.com/AFP-Medialab/invid-verification-plugin`
"Swiss army knife" for journalists. Tabs:
- **Analysis** — metadata for YouTube/FB/Twitter videos + location
- **Keyframes** — split video into keyframes → reverse image search
- **Magnifier** — zoom/enhance to read signs, banners
- **Metadata** — EXIF viewer, geolocation on map
- **Video Rights** — copyright/reuse conditions
- **Forensic** — still-image forensics (CERTH-ITI)
- Reverse image search on Google, Yandex, Bing, Baidu, TinEye

**Reverse image search** = content-based image retrieval. Finds derivatives and
manipulated versions. Free APIs: Google Lens, Yandex, Bing Visual Search, TinEye.

---

## 7. Regulatory landscape

**EU AI Act — Article 50 (Transparency Obligations):**
Providers/deployers of certain AI systems must disclose that content is
AI-generated or manipulated. Deepfake content must be **marked and detectable**.
This makes detection/watermarking a *legal requirement* in the EU, not a nice-to-have.

**India:** No dedicated deepfake statute yet; IT Act 2000 (Sec 43, 66, 66C, 66D)
covers unauthorized access/fraud, and IT Rules amendments add takedown duties for
synthetic media. MeitY has issued deepfake advisories. A gap → opportunity for a
compliance-focused product.

**Implication for a product:** build to Article 50 semantics now; the same UI can
serve India's emerging rules later.

---

## 8. Competitive / reference landscape

| Product | Type | Notes |
|---|---|---|
| C2PA Content Credentials | Standard + SDK | The provenance backbone |
| Google SynthID / Detector | Watermark + portal | Covers Google + partners |
| TrueMedia (Georgetown) | Platform | Open source, free, non-partisan |
| NewsGuard | Commercial | Source reliability ratings |
| InVID / WeVerify | Browser plugin | Journalist verification toolkit |
| Hive AI | Commercial API | Deepfake/NSFW detection API |

**Gap observed:** nothing free + multilingual (esp. Hindi/Urdu) + provenance-aware
+ explainable in one place. That is the white space.

---

## 9. Recommended architecture (if building the app)

```
┌─────────────────────────────────────────────────────────┐
│  INPUT: image / video / audio / text / URL               │
└────────────────────────┬────────────────────────────────┘
                         ▼
     ┌───────────────────────────────────────────┐
     │ 1. PROVENANCE LAYER (strongest signal)     │
     │    c2pa-rs / CAI SDK → read manifest       │
     │    → valid | invalid | missing + trust     │
     └───────────────────┬───────────────────────┘
                         ▼
     ┌───────────────────────────────────────────┐
     │ 2. WATERMARK CHECK                          │
     │    SynthID Detector / partner watermarks    │
     └───────────────────┬───────────────────────┘
                         ▼
     ┌───────────────────────────────────────────┐
     │ 3. ML CLASSIFIER                            │
     │    DeepfakeBench models, ViT image/audio    │
     │    → probability + heatmap (explainable)    │
     └───────────────────┬───────────────────────┘
                         ▼
     ┌───────────────────────────────────────────┐
     │ 4. CONTEXT LAYER                            │
     │    Reverse image search (earliest use)      │
     │    EXIF / metadata timeline                 │
     │    Fact Check API for text claims           │
     │    Source reliability rating                │
     └───────────────────┬───────────────────────┘
                         ▼
     ┌───────────────────────────────────────────┐
     │ 5. FUSION + EXPLANATION                     │
     │    Single confidence score + reasons        │
     │    "Why" panel, never a bare yes/no         │
     └───────────────────────────────────────────┘
```

**Design principles that matter:**
1. **Never output a bare verdict.** Show *why* (provenance valid? watermark? model score? earliest appearance?). False confidence is worse than "unclear".
2. **Absence ≠ fake.** Missing credentials is normal (most cameras don't sign yet).
3. **Adversarial-aware.** Watermarks get stripped; classifiers get fooled. Weight provenance highest because it is cryptographic.
4. **Privacy-first.** Verify on-device where possible; don't upload user media to a server by default.
5. **Multilingual from day one.** Hindi/Urdu/regional — the gap nobody serves.

---

## 10. Quick-start stack (all free / open source)

| Need | Pick |
|---|---|
| Provenance read/verify | `c2pa-rs` + Python binding |
| Image AI-detection | `dima806/ai_vs_human_generated_image_detection` |
| Deepfake (video) | `SCLBD/DeepfakeBench` models |
| Audio deepfake | `dessa-oss/fake-voice-detection` |
| Claim fact-check | Google Fact Check Tools API |
| Reverse image | Google Lens / Yandex / Bing Visual Search |
| Browser forensics | InVID plugin (reference, MIT) |
| Backend | FastAPI (you already know it — see ApnaVault) |
| Frontend | plain HTML/JS or React |

---

## 11. Sources

- C2PA: https://c2pa.org/
- Content Authenticity Initiative: https://contentauthenticity.org/
- CAI open-source docs: https://opensource.contentauthenticity.org/docs/getting-started
- Google Fact Check Tools API: https://developers.google.com/fact-check/tools/api/reference/rest
- Google SynthID: https://deepmind.google/models/synthid/
- EU AI Act Art. 50: https://artificialintelligenceact.eu/article/50/
- InVID plugin: https://www.invid-project.eu/tools-and-services/invid-verification-plugin/
- TrueMedia: https://truemedia.org/
- NewsGuard: https://www.newsguardtech.com/
- HuggingFace models/datasets: https://huggingface.co/models , https://huggingface.co/datasets
- GitHub repos: `contentauth/c2pa-rs`, `SCLBD/DeepfakeBench`, `ICTMCG/FakeSV`, `dessa-oss/fake-voice-detection`
