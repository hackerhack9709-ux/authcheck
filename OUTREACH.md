# Outreach kit

Everything needed to get the first paying customers for AuthCheck. Work top to
bottom: fix the blocker, get ten free keys out, then ask for money.

Owner: **Aarav**.
Live product: <https://authcheck-u1e8.onrender.com>
Teams page to send people to: <https://authcheck-u1e8.onrender.com/for-teams>

> Send from Aarav's name. Replace the bracketed placeholders (`[your name]`,
> `[email]`) with his before sending anything.

---

## 0. Fix this first — you cannot take money yet

Nothing below converts while the account is in Razorpay test mode. Complete
activation before outreach, or you will collect interest and then lose it.

1. Razorpay Dashboard → **Account & Settings → Activate Account**
2. Documents: PAN, Aadhaar (or Digilocker), bank account number + IFSC.
   A cancelled cheque helps only if the penny-drop verification fails.
3. Once approved: **API Keys → Generate Live Keys** (`rzp_live_...`).
4. Register the webhook: **Settings → Webhooks**, URL
   `https://authcheck-u1e8.onrender.com/billing/webhook`, event
   `payment_link.paid`, secret = the `RAZORPAY_WEBHOOK_SECRET` already set on Render.
   Razorpay will not let a script create this, so it must be done by hand. Until
   it exists, **Payments → Reconcile** in the control room is the safety net: it
   issues keys for paid links the webhook missed.
5. Put the live keys on Render and redeploy.

Then test one real ₹99 payment end to end before sending a single email.

---

## 1. Who to approach, and in what order

Do not spray. Work the first ten personally.

| Order | Segment | Why they bite | Where they are |
|---|---|---|---|
| 1 | Indian fact-check desks | Their whole job is this problem | BOOM, Alt News, Factly, Newschecker, Vishvas News, India Today Fact Check, The Quint WebQoof |
| 2 | Regional-language newsrooms | Fake forwards arrive in Hindi/Tamil/Bengali; most tools are English-only | Local-language portals, district news sites |
| 3 | OSINT / cyber investigators | Need an evidence trail for reports | Security researchers on X and LinkedIn |
| 4 | Developer / builder audience | Will self-serve if the API is clean | GitHub, r/developersIndia, Hacker News, Dev.to |
| 5 | Student / campus media labs | Journalism schools run fact-check labs | IIMC, ACJ, JNU, Symbiosis media schools |

## 2. Target list (contact pages verified reachable)

Open each, use the contact form or the email listed there. Do **not** guess
addresses — a bounced mail burns the name.

- BOOM Live — <https://www.boomlive.in/contact-us>
- Alt News — <https://www.altnews.in> (contact link in the footer)
- Factly — <https://factly.in> (contact link in the footer)
- Newschecker — <https://www.newschecker.in/contact>
- Vishvas News — <https://www.vishvasnews.com/contact-us/>
- The Quint WebQoof — <https://www.thequint.com/news/webqoof>
- India Today Fact Check — <https://www.indiatoday.in/fact-check>
- PIB Fact Check — <https://www.pib.gov.in/factcheck.aspx>
- The News Minute — <https://www.thenewsminute.com>
- Scroll.in — <https://scroll.in>

For the developer segment, post where builders already gather:

- GitHub: publish the API as a small public demo repo with a README and a live link
- Reddit: r/developersIndia, r/india, r/webdev
- Hacker News: one "Show HN" post
- Dev.to / Medium: one article, "How I built an explainable fake-content detector"

---

## 3. The one-line pitch

Use this everywhere, adapted to the channel:

> AuthCheck is an API that checks whether an image, voice clip, video or written
> claim is likely fake — and returns the reasons, not just a score. Ten signals
> including C2PA provenance, EXIF, error-level analysis and language
> heuristics. Free tier to try, ₹99/month after.

The differentiator is **explainable**. Lead with it every time. Editors cannot
publish "the model said 87%".

---

## 4. Cold email (newsroom / fact-check desk)

Subject: `A free API key for [outlet]'s verification desk`

```
Hello [name],

I built AuthCheck, an API that helps a verification desk triage suspected
fake content before an editor spends an afternoon on it.

Send it a photo, a voice note, a video clip or a written claim and it returns a
0–100 trust score with every reason behind it — a broken C2PA hash, a stripped
EXIF block, an ELA hot-spot, forward-bait language. It does not just say
"fake". It says why, so the finding can go into a story or a report.

It reads image, audio, video and text through one endpoint, and it stores
nothing — analysis happens per request.

I would like to give [outlet] a free key to test against your own backlog.
No card, no commitment. If it earns a place in your workflow, Starter is
₹99/month and the Pro desk tier is ₹499/month.

Try the engine in the browser: https://authcheck-u1e8.onrender.com
For the API: https://authcheck-u1e8.onrender.com/for-teams

Happy to set it up over a short call if useful.

[your name]
```

## 5. WhatsApp / DM (short, personal)

```
Hi [name] — I built a fake-content checker API. Send it a photo, voice clip or
a claim; it returns a trust score plus every reason behind it (C2PA, EXIF,
pixel forensics, language). Image, audio, video and text in one call.

Free key to try against your backlog, no card:
https://authcheck-u1e8.onrender.com/for-teams

Would love your read on whether it is useful for [outlet].
```

## 6. LinkedIn message (OSINT / investigators)

```
Hi [name] — you write about verification, so this may be relevant.

I built AuthCheck: an API that returns an explainable authenticity score for
images, audio, video and claims. Each result carries its reasoning, so it can
sit in an evidence trail rather than being a black box.

I would like to give you a free key to test on your own material:
https://authcheck-u1e8.onrender.com/for-teams
```

## 7. Show HN post (developer audience)

Title: `Show HN: AuthCheck – explainable fake-content detection API (image/audio/video/text)`

```
Most detectors return a number and ask you to trust it. I wanted the opposite:
a verdict that carries its reasoning.

AuthCheck runs ten signals over a submission — C2PA content credentials, EXIF
and camera metadata, AI-tool signatures, error-level analysis, noise profile,
generator dimensions, and language heuristics for written claims — and returns
a 0–100 score with every flag that moved it.

One API, four inputs: image, audio, video, text. Nothing is retained.

Try it in the browser (no key): https://authcheck-u1e8.onrender.com
API and pricing: https://authcheck-u1e8.onrender.com/for-teams

Built on C2PA and the Google Fact Check Tools. Honest limitation: a missing
credential is not proof of faking, and a reference hit is not proof of truth —
the payload says so. Feedback welcome.
```

---

## 8. Handling the reply

**"Send me a key"** — issue it from the Control Room: `/panel` → Requests →
Issue. The tier resolves automatically from the plan they asked for. Email them
the key plus the four endpoints and the `/api/usage` call.

**"What does it cost?"** — Free tier first, then ₹99/month (Starter, 2,000
checks/hour) or ₹499/month (Pro desk, 10,000 checks/hour). Send the pricing page.

**"How accurate is it?"** — Do not overclaim. Say what it does: it surfaces
provenance, tampering and language signals with reasons, and it never claims to
prove truth. That honesty is what earns trust with a newsroom.

**"Can it handle [language]?"** — Check `/api/health` for the live language list
before answering.

**"We need more than 10,000/hour"** — Take it to a call and quote it. Do not
invent a price on the spot.

---

## 9. Weekly rhythm

- **Mon** — send 5 cold emails from the target list.
- **Tue** — post once in a developer community (rotate: Reddit, Dev.to, X).
- **Wed** — follow up on last week's non-replies, once, politely.
- **Thu** — issue keys from the Control Room and check `/panel` for new requests.
- **Fri** — write down what each reply actually asked for, and fix the page or
  the payload where the answer was awkward.

Two numbers to watch: **free keys issued** and **first paid signup**. Nothing
else matters until both are above zero.

---

## 10. Honest expectation

The first paying customer usually takes four to eight weeks of steady outreach,
not four days. The free keys come easily; the money follows the second time
someone uses it on real work. Get it into ten desks, listen, and let the
explainability sell itself.
