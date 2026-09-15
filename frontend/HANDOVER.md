# GeMVerify frontend — handover

React 18 + Vite 5 + TypeScript, both portals, built against the live backend
(no mock at any point). `npm run typecheck` and `npm run build` are clean.

```bash
cp .env.example .env     # VITE_API_BASE=http://localhost:8000/api
npm install
npm run dev              # http://localhost:5173
```

---

## 1. Backend issues found

### 1.1 The seeded administrator cannot log in — blocks the whole admin portal

`POST /api/auth/login` with `admin@gemverify.local` returns **422**:

```json
{"detail":"email: value is not a valid email address: The part after the @-sign
is a special-use or reserved name that cannot be used with email.",
 "code":"VALIDATION_ERROR"}
```

`LoginRequest.email` is `EmailStr` (`app/schemas.py`), and `email-validator`
2.2.0 — the pinned version — permanently rejects `.local` as a special-use
domain. It cannot be turned off; even `test_environment=True` still rejects
`.local`.

The seeder writes the user straight to the database, so the row is created
fine. Only the login path rejects it. **The admin portal is unreachable on a
clean checkout**, and `scripts/smoke_test.py` fails its first six assertions
for this reason alone.

Scope: `.local` only. `.example` validates fine, so all ten bidder logins work
as documented. This is a one-account problem with a total-blocker effect.

Suggested fix, in your preference order:

1. `LoginRequest.email: str` — login should look up a credential, not validate
   a new address. `RegisterRequest` can keep `EmailStr`.
2. Seed the admin at a non-reserved domain.

**Locally I did neither to your source.** I inserted a *second* ADMIN row
(`admin@gemverify.co`, same Argon2 hash, same role) directly into
`gemverify.db` and left `admin@gemverify.local` untouched. Nothing in the
frontend hardcodes either address — the login form has no demo credentials —
so once you fix this, the documented seed logins work with no frontend change.
I also ran a patched *copy* of `smoke_test.py` from outside `backend/` rather
than editing the original; with a loginnable admin it goes from 16 passed /
10 failed to passing its auth, tender and authorisation sections.

### 1.2 Timestamps have no timezone designator — every time is wrong by the viewer's offset

`API_CONTRACT.md` says ISO-8601 UTC: `"2026-09-15T10:32:04Z"`. The server
sends naive strings with no `Z` and no offset:

```json
"created_at": "2026-09-15T12:25:23.842600"
```

`new Date("2026-09-15T12:25:23.842600")` is parsed by JavaScript as **local
time**, so every timestamp in the UI silently shifts by the viewer's offset —
IST would show everything 5½ hours out.

Worked around in `src/lib/format.ts::parseApiDate`, which appends `Z` when no
designator is present. Please make the server emit `Z` (or a real offset) and
I will delete that branch — a client-side guess about what a timestamp means
is the wrong place for this.

### 1.3 `seed --with-bids` produces bids that can never be verified through the API

The seeder creates each bid at `status=SUBMITTED` and prints "run verification
from the API". But verification is only ever queued from
`POST /bids/{id}/submit` (`routers/bids.py:236`) and
`POST /documents/{id}/resubmit` (`routers/documents.py:143`), and submit
rejects anything that is not `DRAFT`:

```
400 {"detail":"A bid in state SUBMITTED cannot be submitted","code":"BID_NOT_EDITABLE"}
```

So a fresh `--reset --with-bids` database has ten bids, no verification
results, no consistency reports, and no API-reachable way to produce them.
`smoke_test.py` hits exactly this and fails its whole "Verification pipeline"
section.

Either seed at `DRAFT`, or run the orchestrator inline in the seeder, or add
an admin-only re-verify endpoint (which would be independently useful — there
is currently no way to re-run verification on a bid without a bidder
resubmitting a document).

Locally I set the seeded bids back to `DRAFT` and drove all ten through the
real `POST /bids/{id}/submit`. The outcomes match §7 of the brief within
rounding (d4 97.3 vs 97.2, d5 98.9 vs 98.8; the rest exact).

---

## 2. Contract vs. what the server actually returns

Not bugs, but `API_CONTRACT.md` does not mention these. I typed them optional
so the UI degrades if they go away. I have not edited the contract.

| Where | Field | Observed |
|---|---|---|
| `Tender` (both shapes) | `required_document_count` | `12` — used on the tenders list |
| `BidDetail` | `decision_note` | Populated after verification and after approve/reject; rendered as a banner |
| `Document` | `extraction_error` | `null` normally; rendered as an error banner when set |
| — | `GET /api/ai/status` | `{"ready":false,"detail":"Ollama is not reachable…"}` — undocumented endpoint, wired to `client.ai.status()` but not currently surfaced |

`AiExplanation.model` is `null` whenever `is_fallback` is `true`. The contract
example shows a model string, so `model: string | null` — the AI panel reads
"Written from a template" in that case.

---

## 3. Endpoint shapes that did not fit the UI

### 3.1 `ConsistencyFlag.values` is not keyed by `DocumentType`

The contract's example implies `values` maps document types to values, and
that a flag compares a canonical source against one diverging document. Two of
the ten seeded bids break that assumption:

```json
// d10, Vertex Fluid Systems
{"id": "LINKAGE-GSTIN-PAN",
 "documents_involved": ["CONTRACT", "CONTRACT"],
 "values": {"GSTIN": "27AAACV3434C1ZP",
            "PAN embedded in GSTIN": "AAACV3434C",
            "PAN on record": "AAACV1212C"}}
```

Three values, keys that are prose rather than enum members, and
`documents_involved` naming the same document twice. Other flags key `values`
by registry (`PAN_REGISTRY`) rather than by document.

`FlagCard` therefore renders `values` generically and only uses the
two-column "source of truth vs. divergent" treatment when there are exactly
two entries *and* one matches the dimension's `canonical_source`. It dedupes
`documents_involved` before offering "open this document" links. No change
needed server-side — but the contract should say `values` is an open
string→string map, because anyone reading it as `Record<DocumentType, string>`
will write a component that breaks on d10.

### 3.2 `canonical_source` is three different kinds of thing

Observed values: a `DocumentType` (`CONTRACT`, `AADHAAR`), a registry
(`PAN_REGISTRY`, `GST_REGISTRY`), and the free-text string
`"most attested across documents"`. Handled by `lib/labels.ts::sourceLabel`.
Worth documenting as free text so nobody types it as an enum.

### 3.3 No batch consistency endpoint

Compare Bids fetches `GET /bids/{id}/consistency` once per selected bid — up
to three parallel requests. Fine at this size; a `?bid_ids=` filter would be
tidier if compare ever grows.

### 3.4 `dimensions` never contained a null score

The contract says a dimension with nothing to compare has `score: null`. Across
all ten seeded bids every dimension scored. `DimensionMeter` implements the
"Not applicable" state anyway (never 0%), but it is untested against real data.

---

## 4. The four traps, verified in a real browser

Driven with Playwright against the live stack, not reasoned about:

- **Cookie auth.** `gv_session` present with `httpOnly=true`; `localStorage`
  keys `[]` after login. Every request sends `credentials: 'include'`. No role
  selector on the login form (0 `<select>` elements); the role comes from
  `user.role` in the login response. A bidder hitting `/admin/bids` lands on
  `/bidder`.
- **PDF viewer.** Fetched with credentials and wrapped in a blob URL, rendered
  by react-pdf to a canvas — measured 1 canvas at 726×1026, **0 iframes** in
  the workspace. `URL.revokeObjectURL` runs on id change and on unmount
  (`useDocumentBlob`).
- **404 explanation.** `GET /bids/{id}/explanation` 404s until narration runs;
  `AiAssessment` renders a "narration is being written" state with a spinner
  and polls at 4s, never an error. Confirmed live: `FLAG_EXPLANATION` and
  `CLARIFICATION_DRAFT` 404 on bid 5 while `ADMIN_SUMMARY` and
  `DECISION_REASONING` return 200.
- **Flags over scores.** `lib/severity.ts::compareBids` ranks by status, then
  by documents flagged, and only then by score. The admin list shows all seven
  `MANUAL_REVIEW` bids above all three `VERIFIED` ones, with d10 (100.0) above
  two `VERIFIED` bids that also score 100.0. Measured on the d10 page: the
  largest percentage on the intelligence panel renders at **12px** against a
  15px finding title.

One deliberate consequence worth knowing: **d4 (LMN) gets an explicit
callout.** Its cross-document panel is a clean green "no disagreement", which
on its own reads as "nothing wrong" for a bid that is in `MANUAL_REVIEW`. The
panel therefore adds a note saying the finding is in the per-document layer,
and the header strip separates "Per-document checks: 2 need attention" from
"Cross-document: No disagreement". That pairing is the argument for having both
layers, so it is stated rather than left to be inferred.

---

## 5. Stubbed or not wired

- **`GET /ai/status`** is in the client but not rendered. It would be a good
  caption for the AI panel ("running on templates — Ollama unavailable"), but
  it is not in the contract and I did not want to depend on it.
- **`FLAG_EXPLANATION`** is typed and reachable but never requested. There is
  no obvious per-flag trigger in the current UI; a "why is this flagged?"
  control on each `FlagCard` would be the natural home.
- **Notifications are read-only in the admin portal.** The bell routes to
  `/admin/bids`; admins get notifications from the API but have no list screen.
  The bidder portal has the full screen with mark-read and mark-all-read.
- **No test suite.** Verification was done by driving the real app in Chromium
  (§4). Given the time, that bought more than unit tests would have. If this
  goes further, the ordering logic in `lib/severity.ts` and the normalisers in
  `lib/format.ts` are the parts worth pinning down first.
- **Ollama was never reachable**, so every explanation rendered is the
  templated fallback with `is_fallback: true`. The panel handles both paths but
  the model path is untested against real model output — in particular, long
  multi-paragraph prose will need `white-space: pre-wrap` on `.ai-text`, which
  the single-paragraph fallback does not reveal.

---

## 6. Layout

```
src/
  api/          types.ts (transcribed from the contract), client.ts, errors.ts
  auth/         AuthContext — session state, global 401 handling
  hooks/        usePolling (pauses on document.hidden), useAsync, useDocumentBlob
  lib/          format (incl. the UTC coercion), labels, severity (ordering)
  components/   AppShell, Primitives, BidTable, Modal
  features/
    consistency/  IntelligencePanel, FlagCard, DimensionMeter   ← the centrepiece
    documents/    DocumentChecklist, PdfViewer, EvidencePanel
    ai/           AiAssessment
  pages/        Login, Register, bidder/*, admin/*
```

Polling intervals are as specified: bid 3s while `PROCESSING`, notifications
8s, dashboards 10s — all through one `usePolling` hook that pauses on
`document.hidden`, clears on unmount, and will not queue a second request
behind a slow one.
