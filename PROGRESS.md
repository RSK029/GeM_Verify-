# GeMVerify — Progress

**Updated:** 15 September 2026 (rev 12)
**Repo:** `D:\sih`

---

## Where things stand

The backend is feature-complete: extraction, the deterministic rules layer, the
cross-document consistency engine, structural linkage checks and the Ollama
narration layer are all built and validated against the specimen dataset's own
ground truth. Narration currently runs on its templated fallback because no
model has been pulled yet; that is a one-command fix and changes no verdict.

The backend runs on Windows, the v2 dataset is integrated, and the stack is
verified end to end: **286 unit tests pass and the smoke test reaches 53/54
against a live server** — submit, verify, consistency, clarification,
resubmission, authorization and the audit trail all confirmed over HTTP. The one
remaining failure is fixed and awaiting a re-run.

| Track | State |
|---|---|
| Backend — foundation | Done |
| Backend — verification engine | Done |
| Backend — Ollama narration | Done (running on templated fallback until a model is pulled) |
| Frontend — built and integrated | Done — `frontend/`, 62 files, wired to the live API |
| Dataset — v2, ten bidders | Integrated and passing |

---

## Done

### Contract and foundation
- [x] `docs/API_CONTRACT.md` — frozen v1. Every endpoint, enum spelling and
      object shape. Both tracks build against this.
- [x] Repo scaffold, `requirements.txt`, `.gitignore`
- [x] SQLAlchemy models: application tables and `mock_*` registry tables
- [x] SQLite with WAL + busy timeout, so background verification writes do not
      collide with dashboard polling
- [x] Argon2id password hashing; no column exists that could hold a plaintext
      password
- [x] Session JWT in an httpOnly cookie; role read from the database, never
      chosen at login
- [x] Ownership authorization — a bidder can only reach rows tracing back to
      their own user id; the file path is never the security mechanism
- [x] Single audit choke point (`services/audit.py`), so the trail cannot
      develop holes
- [x] Tenders, bids, multi-document upload, authenticated document streaming
- [x] Notifications, bidder dashboard, admin overview/list/approve/reject/
      clarification, audit log endpoint
- [x] Resubmission keeps evidence: a revision is a new row with `supersedes_id`,
      never an overwrite

### Verification
- [x] **Extraction** — watermark-safe. The rotated SPECIMEN glyphs share the
      content stream with the real text; unfiltered they corrupt values
      (`SIDCO InduNstrial Estate`). Rotated glyphs are dropped by text matrix.
      **120/120 documents, every identifier exact, zero missing fields.**
- [x] `validators.py` imported from the dataset — real Verhoeff, real GSTIN
      mod-36, PAN/CIN/Udyam formats
- [x] **Registry gateway** — the only thing that touches `mock_*` tables. Swap
      the implementation to move to live government APIs.
- [x] Registries **derived from the specimen documents at seed time**, so
      registry and documents agree by construction. Where a defect was injected
      the registry holds the *correct* value — that asymmetry is what makes the
      defect detectable rather than merely asserted.
- [x] **Normalisation and similarity** — stdlib only (`difflib`), no rapidfuzz.
      Identical scores on every machine; the demo cannot drift.
- [x] **Deterministic rules engine** — 20 check types across the 12 document
      types. No language model participates in any verdict.
- [x] **Cross-document consistency engine** — canonical-entity comparison over
      five dimensions (identity, address, PAN, registration, signatory).
      12 comparisons per dimension, not 330 pairwise.
- [x] Pipeline wired; bid status, scores and decision record persisted
- [x] **Structural linkage checks** (`linkage.py`) — GSTIN-embedded PAN vs the
      PAN card, GSTIN state vs CIN state, signatory vs the board. Each can break
      while every field passes its own check.
- [x] **Ollama narration layer** — admin summary, flag explanation, bidder
      clarification draft, decision reasoning. Runs *after* the verdict is
      committed, at `temperature: 0` with a fixed seed, and degrades to
      templated prose when Ollama is unreachable or has no model.
- [x] `GET /bids/{id}/explanation`, the regenerate endpoint, and `GET /ai/status`
      (says in one call whether narration will use the model or the fallback)
- [x] Test suites: `test_extraction.py`, `test_verification_engine.py` —
      **286 passing on Windows** against all ten bidders
- [x] `docs/DEMO_SCRIPT.md` — the rehearsed walkthrough: four acts, which bidder
      demonstrates which point, anticipated judge questions with answers, and
      what to do if something breaks on stage
- [x] `scripts/smoke_test.py` — end-to-end check against a running server:
      submit, poll, consistency, clarification round-trip, resubmission
      versioning, upload validation, the cross-bidder authorization boundary,
      and the audit trail

### Engine output vs. ground truth

| | Status | Overall | Docs | Consistency | Finding |
|---|---|---|---|---|---|
| d1 | VERIFIED | 100.0 | 100.0 | 100.0 | — |
| d2 | VERIFIED | 100.0 | 100.0 | 100.0 | — |
| d3 | VERIFIED | 99.9 | 100.0 | 99.8 | — |
| d4 | MANUAL_REVIEW | 97.2 | 94.4 | 100.0 | GSTIN mod-36 failed; GSTIN absent from registry |
| d5 | MANUAL_REVIEW | 98.8 | 98.6 | 99.1 | PAN card name diverges from registered legal name (`POTENTIAL_INCONSISTENCY`) |
| d6 | MANUAL_REVIEW | 98.7 | 97.3 | 100.0 | Aadhaar Verhoeff failed |
| d7 | MANUAL_REVIEW | 100.0 | **100.0** | 99.9 | Udyam omits the corporate suffix — `VARIATION` |
| d8 | MANUAL_REVIEW | 99.8 | **100.0** | 99.5 | Udyam address differs in form — `VARIATION` |
| d9 | MANUAL_REVIEW | 99.9 | **100.0** | 99.8 | Signatory is not on the board — `INCONSISTENT` |
| d10 | MANUAL_REVIEW | 100.0 | **100.0** | 100.0 | GSTIN embeds a different PAN; GSTIN and CIN disagree on state — `INCONSISTENT` |

**d7–d10 score 100.0 on document checks.** Every field is valid, every registry
lookup passes, every threshold is met. Pass 1 finds nothing. Only reconciliation
across the twelve documents sees anything at all — which is the entire argument
for the product.

All three clean datasets pass with no flags; all three defects are caught by the
check the dataset says should catch them. **No bid is ever auto-rejected** — the
pipeline decides whether a human needs to look, and says why.

d4 is worth noting: it repeats the same corrupt GSTIN in every document, so
cross-document agreement is a perfect 100% and only the deterministic checksum
catches it. d5 is the mirror image — every identifier is individually valid and
only cross-document comparison finds the problem. That pair is the argument for
having both layers.

---

## Left to do

### Backend
- [ ] Pull a model: `ollama pull qwen2.5:7b-instruct` (Ollama is running,
      **zero models pulled** — narration works meanwhile via templates)
- [ ] **Re-run `scripts/smoke_test.py`** — now 54 + 22 new cases covering score
      visibility and withdraw/reapply
- [ ] **Re-run `pytest -q`** — expect 286 (the engine was not touched by rev 12)
- [ ] `npm run build` in `frontend/` after rev 12's UI changes

- [x] v2 dataset integrated; bands calibrated against all ten

### Frontend
- [x] Built on laptop 2 against the live backend and integrated into `frontend/`
      — React 18 + Vite 5 + TypeScript, both portals, 62 files
- [x] All four traps verified in a real browser by that track: httpOnly cookie
      with empty `localStorage`, PDF via blob URL (0 iframes), 404-tolerant
      explanation panel, flags ranked above scores
- [ ] `npm install && npm run build` on `D:\sih\frontend` — not yet run here
      (npm is blocked by egress policy in the cloud sandbox)
- [ ] Wire `GET /ai/status` into the AI panel caption (client method exists,
      not rendered)
- [ ] `FLAG_EXPLANATION` is typed and reachable but has no UI trigger
- [ ] Admin notifications have no list screen (bell routes to `/admin/bids`)
- [ ] `white-space: pre-wrap` on `.ai-text` once a real model produces
      multi-paragraph prose

### Dataset
- [x] v2 integrated: 120 PDFs, ten datasets, extraction exact on all 120
- [ ] Delete the stale 6-dataset `sih26100-specimen-datasets.zip` on the Mac so
      nobody unpacks it over the current work.

### Demo readiness
- [x] Demo script written
- [ ] Rehearse it once end to end with the frontend in place
- [ ] Decide whether to submit a bid live or open pre-verified bids only
      (pre-verified is safer)

### Before the demo
- [x] Bands calibrated against all ten datasets
- [x] pdfplumber does **not** drop hyphens at line breaks — the other track's
      pdftotext bug does not affect us; d8's wrapped addresses extract intact
- [ ] Rehearse the scripted path: submit → verify → admin review → request
      clarification → bidder resubmits → re-verify

---

## Decisions locked in

| Decision | Rationale |
|---|---|
| Ollama explains, never decides | Reproducible verdicts, defensible scores, demo cannot break on a slow model |
| Shared distinctive token floors a name at review | "DEF Technocraft" vs "DEF Techno Equipments" is a plausible rename, not a different company |
| Structural relations checked separately from fields | A GSTIN can be individually valid and still embed the wrong PAN |
| Signatory checked by board membership, not name similarity | "Not a director" is a different problem from "spelled differently" |
| Similarity via `difflib`, not rapidfuzz | Identical results on every machine; one less dependency |
| Canonical-entity comparison | 12 comparisons per dimension instead of 330; readable in the UI |
| Registry canonical where available | A single stale document cannot drag the canonical value with it |
| Text-layer extraction, no OCR | The specimens have a real text layer; OCR would add error, not capability |
| httpOnly cookie sessions | Keeps the PDF viewer simple — no blob-URL dance |
| Admins are seed-only | Self-registration always creates a BIDDER |
| Resubmission versions, never overwrites | The audit trail is a judging point; overwriting evidence undercuts it |
| 12 document types, tender `GEM/2026/B/4471902` | Taken from the dataset, not the original spec |

---

## Bugs the smoke test found

Four, none of which 286 unit tests could reach, because all of them live in the
HTTP and seeding layers the engine never touches.

**Admin could never log in.** `LoginRequest.email` was `EmailStr`, and
`email-validator` rejects `.local` as a reserved special-use TLD — so
`admin@gemverify.local` returned 422 at the schema layer before any credential
was checked. The account existed and its hash was correct; the request never
reached it.

Two fixes, both worth having independently of the seed email:

- `LoginRequest.email` is now a plain string. Registration still validates
  properly — that is the right place for it — but at login a malformed address
  is simply a failed login and must return **401**, not a 422 explaining why the
  address was rejected. The old behaviour was also a small information leak.
- The smoke test aborts immediately when admin login fails, rather than
  continuing and producing a cascade of failures that hide the cause. It now
  also checks that list endpoints returned a list, instead of indexing an error
  envelope and raising `KeyError: 0`.

**Seeded bids were in a dead state.** The seed filed them as `SUBMITTED`, but
`submit_bid` only accepts `DRAFT` or `CLARIFICATION_REQUIRED` — so nothing could
advance them and they would never be verified. The seed now leaves bids in
`DRAFT` (so submitting is a real action), and a new `--verify` flag submits and
runs the pipeline inline, which is what you want before a demo.

**Timestamps had no timezone designator** (found by the frontend track). The
contract promises `"2026-09-15T10:32:04Z"`; the server sent naive
`"2026-09-15T12:25:23.842600"`. JavaScript parses an undesignated string as
*local* time, so every timestamp in the UI silently shifted by the viewer's
offset — five and a half hours in IST. Fixed server-side: `utcnow()` now returns
naive UTC consistently, and a `UtcDatetime` serializer re-attaches `Z` on all 12
response datetime fields. A client cannot know what an undesignated timestamp
means and should not have to guess.

**The seed bypassed the audit trail.** `--verify` set bid status directly, so
verified bids existed with no `BID_SUBMITTED` record — a hole in the claim that
every action is logged. A seeded submission is still a submission, and now
writes its audit entry like one.

---

## Bugs found by submitting a bid from a company outside the dataset

A real end-to-end test — a newly registered LLP, twelve documents from a
different template, no registry entry — surfaced five faults. Every one of them
would have hit a judge trying the same thing.

**An extraction gap cancelled every other check on the document.** `checks_for`
returned early when any expected field was missing, so one unreadable tender
reference silently suppressed the PAN format check, the GSTIN checksum and all
registry lookups. Ten of twelve documents reported one finding each and nothing
else; the screen read "0 of 12 clear". Now the gap is reported as one finding
among the rest, and everything that *can* be checked is.

**The parsers were tuned to one generator's exact label wording.** "Tender
Reference No." vs "Tender Reference", "Name of Company" vs "Name of the entity",
"Account holder name" vs "Name of Account Holder". Fixed by widening the label
vocabulary, adding a second matching tier that finds a label anywhere in a line
rather than only as a prefix, and falling back to the structural shape of an
identifier (`GEM/\d{4}/[A-Z]/\d+`) where no label helps. 11 of 12 now parse.

**A Limited Liability Partnership has no CIN.** It carries an LLPIN, so
demanding a CIN reported a permanent, unfixable gap against a valid entity.
`EXPECTED_FIELDS` now accepts either.

**A valid LLP's PAN was failed for not being a company's.** `validate_pan` was
called with `expect_holder_type="C"`; the fourth character of a firm's PAN is
`F`. That rejected the entity type rather than verifying the document.

**Silence was read as refusal.** An OEM letter with no item table was reported
as "excludes one or more tender line items". Absent coverage information is
unknown, not excluded — that check now skips.

Two of these were introduced by the fix itself and caught before shipping: the
new anywhere-tier matched *mid-word* ("Tender Reference" inside "the tender
referenced above"), and matching a label inside prose swallowed the rest of the
sentence into an identifier. Both now guarded — word boundaries, and
identifiers trimmed to their own pattern.

Result for that bid: registry misses on PAN, GSTIN, Udyam, EPFO and OEM, which
is the correct answer for a company that is not on file.

---

## Known risks

- **The server has started and the suite passes, but no request has been served
  end to end yet.** `scripts/smoke_test.py` closes that gap in one command.
- **Scores cluster at 97–100.** This is a real property of the engine, not a
  placeholder: a bid with eleven clean documents and one divergence *is* mostly
  consistent. The flags, not the score, carry the finding — the UI must lead
  with the flag and treat the percentage as secondary.
- **Abbreviation dictionaries are hand-built** and will have gaps. Fine for a
  prototype; worth naming as a limitation rather than hiding.
- **Extraction is label-driven and therefore template-sensitive.** It now
  handles two unrelated document templates, but an arbitrary real-world PDF
  will still need labels it has never seen. The honest framing for a judge is
  that this is a parsing layer tuned to known formats, not a general document
  understander — and that an unreadable field routes to human review rather
  than failing the bidder.
- **Extraction is now the single point of failure.** A misread field produces a
  confident wrong verdict with no LLM to catch it. Mitigated by routing
  incomplete extraction to REVIEW rather than FAIL.

---

## Rev 12 — scores hidden from bidders, withdraw and reapply

Two changes the user asked for together. Both are enforced on the server first;
the UI changes only remove chrome that would otherwise render a dash.

### Scores are administrator-only

A percentage invites the reading that a bid is "93% valid". What actually
decides the outcome is the individual findings and an officer's judgement — the
principle already written into the demo script: *the flags, not the score, carry
the finding.* So the number is withheld **on the wire**, not hidden in the DOM,
where anyone could read it back out of the network tab.

- `serializers.bid_summary_out(bid, *, include_scores=True)` is the single gate.
  Every bidder-facing route passes `False`: `POST /bids`, `GET /bids`,
  `POST /bids/{id}/submit`, and `GET /bids/{id}` when the caller is not an
  administrator. The bidder dashboard passes `False` too.
- `GET /bids/{id}/consistency` strips `overall_score`, `document_score`,
  `consistency_score`, every dimension `score` and every observation
  `similarity` for a non-admin caller. **The verdicts and flags stay** — a
  bidder is entitled to know what was found in their own documents.
- `ConsistencyReportOut`'s three scores became `float | None` to allow this.
- The narration layer drops the `scores` block from the context for the two
  bidder-facing kinds (`CLARIFICATION_DRAFT`, `DECISION_REASONING`), so the
  model cannot quote a number the API withholds. Instructing it not to would be
  a request, not a guarantee.
- UI: `BidTable` and `IntelligencePanel`/`DimensionMeter` take a `showScores`
  prop, off throughout the bidder portal. The bidder bid page no longer prints
  "overall score …". The admin portal is unchanged.

### Withdraw and reapply

- New `BidStatus.WITHDRAWN` and audit actions `BID_WITHDRAWN`, `BID_REAPPLIED`.
  No migration: status is a string column.
- `POST /bids/{id}/withdraw` — owner only. Allowed from SUBMITTED, PROCESSING,
  VERIFIED, MANUAL_REVIEW, CLARIFICATION_REQUIRED. A draft is *deleted*, not
  withdrawn; an APPROVED or REJECTED bid cannot be withdrawn, or a bidder could
  erase an adverse decision from the officer's queue. Nothing is deleted: the
  bid, its documents and its verification results stay on record, and every
  administrator is notified.
- `POST /bids/{id}/reapply` — owner only, from WITHDRAWN or REJECTED, and only
  while the tender is still OPEN. Opens a **fresh draft**; it never revives the
  old bid, so the earlier attempt and the officer's decision note survive for
  audit. The previously uploaded documents are carried across as new rows
  pointing at the same stored files, reset to PENDING with no extracted fields,
  so the bidder replaces only what needs changing and everything is re-run from
  scratch on the next submit. An existing draft for that tender is returned
  instead of a second one.
- The administrator's approve / reject / clarification endpoints now refuse a
  withdrawn bid with `BID_WITHDRAWN`, and the review page disables those
  controls rather than letting the click fail.
- UI: the bidder bid page gains a "Withdraw bid" button behind an inline
  confirmation that says plainly what withdrawal does, and a "Reapply for this
  tender" button that lands on the new draft's upload screen.

### Design questions settled without asking

Two decisions were needed and both were taken the conservative way, because
either alternative destroys evidence:

1. **Withdrawal is not permitted after a decision.** Letting a bidder withdraw
   a rejected bid would let them clear the record.
2. **Reapply creates a new bid rather than reopening the old one.** A reopened
   bid would overwrite its own verification history.

If the demo wants either loosened, both are one constant: `_WITHDRAWABLE` and
`_REAPPLICABLE` in `app/routers/bids.py`.

### Contract note

`docs/API_CONTRACT.md` is frozen v1 and was **not** edited, per the standing
instruction. Rev 12 adds two endpoints and one enum member to the real API that
the document does not describe, alongside the inaccuracies already listed under
Known risks. Worth one decision before judging.
