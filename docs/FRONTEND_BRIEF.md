# GeMVerify — Frontend Brief

Everything the frontend track needs. Pair this with `API_CONTRACT.md`; between
them there should be no need to see the backend source.

---

## 1. What the backend is, today

Python + FastAPI + SQLite. Feature-complete, with a passing test suite. It is
developed on a different machine, but a copy runs locally alongside your work —
see section 2.

A bidder submits twelve documents against a tender. The backend extracts
structured fields from each PDF, checks them against a stand-in for the
government registries, then compares the twelve documents **against one
another** — which is the product's actual point. A human officer makes the final
call. Nothing is auto-rejected.

Two layers produce findings, and the UI must keep them visually distinct:

| Layer | What it produces | Where it surfaces |
|---|---|---|
| Per-document checks | `VerificationResult` rows, `PASS` / `FAIL` / `REVIEW` | Document checklist, evidence panel |
| Cross-document consistency | `ConsistencyReport` — five dimensions, flags | The intelligence panel |
| AI narration | `AiExplanation` prose | Labelled panel, **beside** the evidence, never instead of it |

The AI never decides anything. It reads the finished decision record and writes
prose. Present it that way — a reader must never be left thinking the verdict
came from a language model.

---

## 2. Run the real backend locally

A copy of the backend ships with this brief. Run it rather than mocking it —
real responses, real timing, real 401s, and no mock to drift out of sync.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed.seed --reset --verify
uvicorn app.main:app --reload --port 8000
```

Interactive API docs at <http://localhost:8000/docs> — every endpoint is
callable there, which is faster than reading the contract for shapes.

Sanity check before building anything: `python scripts/smoke_test.py` in a second
terminal drives the whole pipeline and prints what passed.

**The backend copy is read-only reference.** Do not edit it. It is developed on
the other machine and your copy will be overwritten. If something needs to
change server-side — a missing field, an awkward shape, a bug — put it in the
note described in section 11 rather than patching it locally; a fix that exists
only in your copy will be lost.

```
src/api/
  types.ts     transcribed from API_CONTRACT.md — the single source of truth
  client.ts    the HTTP client, credentials: 'include' on every call
  errors.ts    the { detail, code } envelope mapped to human copy
```

CORS already allows `http://localhost:5173` and `http://localhost:3000` with
credentials, so Vite's default port works untouched. Put the base URL in
`.env.example` as `VITE_API_BASE=http://localhost:8000/api`.

---

## 3. Auth — read this twice

The session is a **JWT in an httpOnly cookie** named `gv_session`. JavaScript
cannot read it and must not try.

- Every request sends `credentials: 'include'`.
- Nothing is ever stored in `localStorage` for auth.
- On boot, call `GET /api/auth/me`. 200 → route on `user.role`. 401 → `/login`.
- **There is no role selector at login.** The backend resolves the role from the
  database. A UI that asks "are you a bidder or an admin?" is wrong.
- Any 401 mid-session clears auth state and redirects to `/login`.

`BIDDER` → `/bidder/*`, `ADMIN` → `/admin/*`. A bidder hitting an admin route
gets redirected, not a blank screen.

---

## 4. The PDF viewer

`GET /api/documents/{id}` returns `application/pdf`, but only to an authorized
caller. A plain `<iframe src="...">` **will 401** — the browser will not attach
the cookie to that cross-origin subresource request.

Fetch it, blob it, revoke it:

```ts
const res = await fetch(`${BASE}/documents/${id}`, { credentials: 'include' })
const url = URL.createObjectURL(await res.blob())
// render with react-pdf, then on unmount:
URL.revokeObjectURL(url)
```

Leaking blob URLs across an admin's review session will chew through memory, so
the revoke is not optional.

---

## 5. Polling

No WebSockets in v1.

| What | Interval | Stop when |
|---|---|---|
| `GET /api/bids/{id}` | 3s | `status !== 'PROCESSING'` |
| `GET /api/notifications?unread_only=true` | 8s | — |
| `GET /api/dashboard` or `/api/admin/overview` | 10s | — |

One `usePolling(fn, ms, enabled)` hook for all of it. It must pause on
`document.hidden` and clear on unmount.

---

## 6. The cross-document intelligence panel

This is the centrepiece of the admin bid review page and the thing judges will
look at. Give it real design attention.

`GET /api/bids/{id}/consistency` returns five `dimensions` — `IDENTITY`,
`ADDRESS`, `PAN`, `REGISTRATION`, `SIGNATORY` — each with `score`, `verdict`,
`canonical_value`, `canonical_source` and per-document `observations`. Plus a
`flags` array.

Render as:

1. **A meter per dimension.** Label, percentage, bar, verdict colour. A
   dimension with `score: null` reads "Not applicable" — **never 0%**.
2. **A flag card per finding**, side by side: the canonical source and its value
   against the diverging document and its value. `canonical_source` is where the
   truth came from — `PAN_REGISTRY`, `GST_REGISTRY`, or "most attested across
   documents". Show it; it is what makes the finding defensible.
3. **The AI assessment underneath**, clearly labelled as generated, with a
   regenerate control.

**Lead with the flags, not the score.** Scores legitimately cluster at 97-100 —
a bid with eleven clean documents and one divergence genuinely *is* mostly
consistent — so the percentage is weak signal and the flags carry the finding.
d10 scores 100.0 across the board while being the most serious case in the set.
Concretely: a bid with flags must read as needing attention regardless of its
score, any bid list sorts by status before score, and a percentage is never the
largest thing on the card.

Verdict colours:

| Verdict | Colour | Meaning |
|---|---|---|
| `CONSISTENT` | green | agrees |
| `VARIATION` | amber | benign difference — abbreviation, dropped suffix |
| `POTENTIAL_INCONSISTENCY` | amber | plausibly the same entity, needs a human |
| `INCONSISTENT` | red | does not correspond |

`VARIATION` and `POTENTIAL_INCONSISTENCY` share a colour but are different
findings — the copy must distinguish them. Neither means rejection.

---

## 7. What your local backend will return

Ten seeded bidders on tender `GEM/2026/B/4471902` — "CPCL Industrial Equipment
Procurement - 2026", Chennai Petroleum Corporation Limited. These are the exact
outcomes your server produces, listed so you know what correct looks like before
you see it.

| # | Company | Status | Overall | Docs | Consistency | Finding |
|---|---|---|---|---|---|---|
| d1 | ABC Industrial Systems Pvt Ltd | `VERIFIED` | 100.0 | 100.0 | 100.0 | — |
| d2 | XYZ Electromech Pvt Ltd | `VERIFIED` | 100.0 | 100.0 | 100.0 | — |
| d3 | PQR Engineering Works Pvt Ltd | `VERIFIED` | 99.9 | 100.0 | 99.8 | — |
| d4 | LMN Power Solutions Pvt Ltd | `MANUAL_REVIEW` | 97.2 | 94.4 | 100.0 | GSTIN checksum failed |
| d5 | DEF Techno Equipments Pvt Ltd | `MANUAL_REVIEW` | 98.8 | 98.6 | 99.1 | PAN name diverges — `POTENTIAL_INCONSISTENCY` |
| d6 | GHI Automation Pvt Ltd | `MANUAL_REVIEW` | 98.7 | 97.3 | 100.0 | Aadhaar checksum failed |
| d7 | Sterling Hydro Systems Pvt Ltd | `MANUAL_REVIEW` | 100.0 | **100.0** | 99.9 | Udyam omits the corporate suffix — `VARIATION` |
| d8 | Meridian Process Controls Pvt Ltd | `MANUAL_REVIEW` | 99.8 | **100.0** | 99.5 | Udyam address differs in form — `VARIATION` |
| d9 | Orion Thermal Engineering Pvt Ltd | `MANUAL_REVIEW` | 99.9 | **100.0** | 99.8 | Signatory is not on the board — `INCONSISTENT` |
| d10 | Vertex Fluid Systems Pvt Ltd | `MANUAL_REVIEW` | 100.0 | **100.0** | 100.0 | GSTIN embeds a different PAN; GSTIN and CIN disagree on state — `INCONSISTENT` |

Three families, and the UI has to make all three legible:

- **d1-d3** clean.
- **d4-d6** a field-level defect — a checksum, a stale name. Caught in pass 1.
- **d7-d10** every field valid, every registry lookup passing, every threshold
  met. **They score 100.0 on document checks and still land in review.** Only
  reconciliation across the twelve documents sees anything. These are the bids
  that justify the product.

**Build the demo around DEF Techno Equipments.** All twelve of its documents pass
their own checks; only the cross-document comparison notices that the PAN card
carries a stale legal name. Its flag:

```json
{
  "id": "IDENTITY-PAN-140",
  "dimension": "IDENTITY",
  "verdict": "POTENTIAL_INCONSISTENCY",
  "title": "Company name on PAN Card differs from the registered legal name",
  "documents_involved": ["PAN_REGISTRY", "PAN"],
  "values": {
    "PAN_REGISTRY": "DEF Techno Equipments Private Limited",
    "PAN": "DEF Technocraft Private Limited"
  }
}
```

Its `PAN_NAME_MATCH` check result:

```json
{
  "check_type": "PAN_NAME_MATCH",
  "result": "REVIEW",
  "submitted_value": "DEF Technocraft Private Limited",
  "registry_value": "DEF Techno Equipments Private Limited",
  "confidence": 0.556,
  "reason": "names share a distinctive element but differ substantially; may be a former or misspelled name"
}
```

And the AI summary it currently produces (templated fallback — a pulled model
will write better prose, same substance):

> 11 of 12 documents passed every individual check. Checks requiring attention:
> PAN_NAME_MATCH on the PAN Card. Cross-document findings: Company name on PAN
> Card differs from the registered legal name (potential inconsistency). Overall
> score 98.9. Status: Manual Review.

Contrast with **LMN Power Solutions (d4)**, whose consistency is a perfect 100%
— it repeats the same corrupt GSTIN in every document — and is caught only by
the deterministic checksum. Those two bids side by side are the argument for
having both layers, so make sure both render well.

And **Vertex Fluid Systems (d10)** is the sharpest case in the set: it scores
**100.0 on every metric** and is still the most serious finding, because the
problem is not in any number. Its GSTIN is individually valid, its PAN is
individually valid; only the relationship between them is wrong. If d10 looks
unremarkable in your UI, the UI is wrong.

**Seed logins** (live mode): `admin@gemverify.local` / `Admin123!`, and
`contact@abcindustrialsystems.example` (plus five more in the same pattern) /
`Password123!`.

---

## 8. Design tokens

Government procurement dashboard: minimal, information-dense, desktop-first. No
hero sections, no marketing polish, no animation beyond 150ms state transitions.

```
background  #F8F9FA   surface     #FFFFFF   border      #E4E7EB
text        #1A1D21   secondary   #5B6470   muted       #8B94A3
accent      #1F4E8C   accent-hover #173D6E
verified    #1B7F4B   review      #B77500   rejected    #C0392B
processing  #5B6470
```

Inter or a system stack, 14px base, **tabular numerals on every identifier,
amount and score**. 6px radius, 1px borders, flat cards — shadows only on
overlays. Spacing scale 4/8/12/16/24/32.

---

## 9. Screens

**Auth** — login, register (bidder only; admins are seed-only, so no role field).

**Bidder** — Overview (4 stat cards, recent bids, notifications, action
required), Available Tenders (list + detail), Bid Submission (12 upload slots
with per-slot status), My Bids, Bid Detail (per-document results +
cross-document panel + explanation), Notifications, Company Profile.

**Admin** — Overview (totals by status, recent submissions, attention required,
pending clarifications), All Bids (filter by status, search by company or tender
number), **Bid Review** (document checklist, split-pane viewer with evidence,
cross-document intelligence panel, AI assessment, action bar), Compare Bids,
Audit Log.

The Bid Review page is where the product lives. Everything else can be
competent; that one should be excellent.

---

## 10. Error handling

Every error is `{ detail, code }`. Map codes to human copy:

| Code | Copy |
|---|---|
| `INVALID_CREDENTIALS` | Incorrect email or password |
| `FORBIDDEN` | You do not have access to this |
| `NOT_FOUND` | Not found |
| `MISSING_REQUIRED_DOCUMENTS` | Show `detail` — it names the missing documents |
| `FILE_TOO_LARGE` | File exceeds the 10 MB limit |
| `UNSUPPORTED_FILE_TYPE` | Only PDF documents are accepted |
| `BID_NOT_EDITABLE` | This bid can no longer be changed |
| `DUPLICATE_EMAIL` | An account with this email already exists |

`GET /api/bids/{id}/explanation` returns **404 until narration has run**. That is
normal, not an error — render a "generating" state.

---

## 11. Delivering it back

The frontend belongs at `frontend/` in the repo root, beside `backend/` and
`docs/`. Send it as a zip **excluding `node_modules`, `dist` and `.vite`** —
source, `package.json`, `package-lock.json`, configs and `.env.example` only.

Include a short note listing: anything in the contract that turned out to be
missing or wrong, any endpoint whose shape did not fit the UI, and anything
stubbed that still needs wiring.

**Do not change `API_CONTRACT.md`.** If something is wrong with it, say so in
the note — the backend is built against it and both sides have to move together.
