# GeMVerify — Demo Script

For the SIH presentation. Roughly eight minutes of demo plus questions.

---

## Before you start

```
.\.venv\Scripts\python.exe -m app.seed.seed --reset --verify
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Checks worth doing while nobody is watching:

- `GET /api/ai/status` — says whether narration will use the model or the
  templated fallback. Either is fine; know which, so you are not surprised.
- `python scripts\smoke_test.py` — if this is green, the demo will work.
- Two browser windows, side by side: bidder left, admin right. Logged in
  already. **Do not log in on stage** — it burns thirty seconds and proves
  nothing.
- Zoom to ~125%. Judges are reading from a distance.

Have these bids pre-verified and ready to open:

| For | Bidder | Why |
|---|---|---|
| Act 2 | LMN Power Solutions (d4) | field defect, caught in pass 1 |
| Act 3 | Vertex Fluid Systems (d10) | **the whole argument** |
| Act 4 | DEF Techno Equipments (d5) | the clarification loop |

---

## The one sentence

If you say nothing else, say this:

> Checking each document against a registry is the easy half. The hard half is
> asking whether twelve documents describe the same company — and that is where
> both fraud and clerical error actually live.

---

## Act 1 — The problem (60 seconds, no screen)

A bidder submits twelve documents: GST certificate, PAN card, Udyam, incorporation,
OEM authorisation, turnover, experience, EPFO, and so on. An officer has to decide
whether this is a real, qualified company.

Every existing approach validates documents one at a time. That catches a bad
checksum. It does not catch a company whose PAN card carries a name it stopped
using two years ago, or a contract signed by someone who is not on the board —
because each of those documents is individually perfect.

**GeMVerify adds the second pass: reconciliation across the set.**

---

## Act 2 — Pass one works (90 seconds)

Admin window. Open **LMN Power Solutions**.

Point at the document checklist: eleven green, one red.

> The GST certificate failed. Not because a model thought it looked wrong —
> because the GSTIN's mod-36 check character is arithmetically incorrect. The
> system expected '1' and the certificate says '2'.

Open the evidence panel beside the document.

> Submitted value, registry value, the reason. An officer can act on this
> without trusting us.

**Then pre-empt the obvious question:**

> Now — notice the cross-document consistency score is 100%. Every one of the
> twelve documents repeats this same wrong GSTIN. They agree with each other
> perfectly. Consistency checking alone would have passed this bid.

That sets up the reversal.

---

## Act 3 — Pass two, the reversal (3 minutes — this is the demo)

Open **Vertex Fluid Systems**.

Let them look at the checklist first. Twelve green. Score 100.0 on every metric.

> Document verification: 100%. Consistency: 100%. Overall: 100%. Every field
> valid, every registry lookup passing, every threshold met. By any per-document
> standard this is a clean bid.

Pause. Then scroll to the cross-document intelligence panel.

> And it is in manual review, because of this.

Read the two flags aloud:

**GSTIN does not embed the PAN shown on the PAN card.**

> A GSTIN contains the holder's PAN in characters three to twelve. This one
> embeds `AAACV3434C`. The PAN card reads `AAACV1212C`. Both identifiers are
> individually valid — the GSTIN's checksum is correct *for the GSTIN as
> written*, and the PAN's format is correct. Neither document is wrong on its
> own. Only the relationship between them is.

**GSTIN and CIN place the company in different states.**

> The GSTIN registers them in Maharashtra. The CIN registers them in Karnataka.
> Again, both well-formed.

> No single-document check can find either of these, and no amount of OCR
> accuracy helps. You have to hold the documents up against each other.

If you have time, contrast with **Sterling Hydro Systems (d7)** — same 100%
document score, but its finding is a *benign* one: the Udyam certificate drops
"Private Limited". Flagged as a variation, amber not red.

> The system does not treat every textual difference as fraud. It says: I noticed
> this, and here is why I think it is harmless. That distinction is what makes it
> usable — a tool that flags everything gets ignored.

---

## Act 4 — The human loop (2 minutes)

Open **DEF Techno Equipments**. Its PAN card carries a stale legal name.

> Twelve documents, every registry lookup passing. The PAN card says "DEF
> Technocraft"; every other document and the registry say "DEF Techno
> Equipments". Rated *potential inconsistency*, not inconsistent — they share a
> distinctive element, so a former name or a typo is more likely than two
> different companies.

Show the AI assessment panel.

> This paragraph is generated. It did not decide anything — it read the finished
> result and wrote it in plain English. If the model were switched off, the
> verdict and the score would be identical.

Click **Request Clarification**. Switch to the bidder window.

> The notification is already there. It is in the database, so a bidder who was
> offline still sees it.

Upload a revised document. Switch back.

> New version, and the previous one is kept — the audit trail never loses
> evidence. Verification re-runs automatically.

Finish on the **Audit Log**.

> Every view, every decision, every re-upload, timestamped and attributed.

---

## Anticipated questions

**"Isn't this just OCR plus a database lookup?"**

No — that is the first pass, and it is the part that was already solved. The
second pass compares the twelve documents against one another across five
dimensions. Vertex Fluid Systems scores 100% on every per-document metric and
is still flagged.

**"How do you know the AI isn't hallucinating the result?"**

It cannot. Every verdict is produced by deterministic code — checksums,
normalisation rules, fixed similarity thresholds. The same bid always produces
the same verdict and the same score. The model is given the finished result and
asked to write it in English. Turn it off and nothing about the decision
changes.

**"What is the score, exactly?"**

Half the document-check pass rate, half the mean cross-document similarity, both
computed from named constants in `app/config.py`. And it is an internal
prototype metric, not an official risk score — we would not present it as one.
Note that the flags, not the score, carry the finding: our most serious case
scores 100%.

**"You have no real government APIs."**

Correct, and none were available for the prototype. Everything the verification
engine knows about external records goes through one interface,
`RegistryGateway`. Today it reads a mock registry; in production you replace
that one class with API clients and nothing else changes. That boundary is real
in the code, not just on a slide.

**"Are the uploaded documents safe?"**

They are treated as sensitive. Stored in private server-side storage, never in
a public directory; the database holds only metadata and a reference. The only
route to a document is an authenticated endpoint that checks ownership and logs
the access. Stored filenames are random, so a crafted filename cannot influence
the path. Uploads are validated by magic bytes, not by the declared type.

For production we would add encrypted object storage, TLS, key management and
retention policies — those are **not** implemented here and we would not claim
otherwise.

**"How are passwords stored?"**

Argon2id hashes. There is no column in the schema that could hold a plaintext
password.

**"What if a bidder just has a typo?"**

Then the officer sees a variation flagged amber with an explanation of why it is
probably benign, and can request clarification in one click. Nothing is
auto-rejected — a single flagged document escalates a bid to human review, it
never rejects it. That is a deliberate design rule.

**"Does it scale?"**

The prototype runs on SQLite because it is a prototype. The verification engine
is pure computation with no external calls, so it parallelises trivially; the
architecture separates storage, extraction, rules and narration precisely so
each can be scaled or replaced independently.

**"What about scanned documents?"**

The specimen set is text-layer PDFs and extraction is exact on all 120. Scanned
input would need an OCR stage ahead of the parser — the pipeline has the seam
for it, and an unreadable field routes to human review rather than failing the
bidder.

---

## If something breaks

- **Ollama slow or unavailable** — narration falls back to templated prose,
  automatically. Verification is unaffected. Say "the explanation layer is on
  its fallback" and keep going; do not debug on stage.
- **A bid stuck in PROCESSING** — verification runs in the background and the UI
  polls. Open a different pre-verified bid and come back.
- **Anything else** — the API docs at `/docs` will answer a factual question
  faster than the UI will.

The safest possible demo is the one where every bid is already verified before
you walk in. Submit a live bid only if the timing is comfortable.

---

## What to leave them with

> Document authentication, registry verification, cross-document consistency,
> AI-assisted explanation, human decision, full auditability. The AI assists the
> officer. It does not replace them, and it does not decide.
