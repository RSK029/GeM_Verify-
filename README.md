# GeMVerify

Bid document verification for government e-procurement — SIH 2026, problem
statement **SIH26100**.

A bidder submits twelve supporting documents against a tender. GeMVerify reads
them, checks each one against a stand-in for the government registries, and then
asks the question that per-document checking cannot: **do these twelve documents
tell a consistent story about the same entity?** A human administrator makes the
final call, with every step recorded.

---

## The design principle

Responsibilities are kept apart, in the codebase as well as in the UI:

| Layer | Responsibility |
|---|---|
| SQLite | system data |
| Private file storage | the actual PDFs |
| Extraction | pull structured fields out of documents |
| Mock registry | stand in for trusted external records |
| Deterministic rules | factual matching — checksums, formats, thresholds |
| Consistency engine | cross-document agreement, scored against fixed bands |
| Ollama | explain the decision in plain language |
| Administrator | make the decision |

**The decision layer is fully deterministic.** Normalisation, fuzzy matching and
threshold bands produce every verdict, so the same bid always yields the same
result and every number traces to a formula in `app/config.py`.

**Ollama never decides anything.** It reads the finished decision record and
writes the prose a human needs: why a bid is in review, what an administrator
should look at, what a bidder must fix. If Ollama is unavailable, templated text
is used and verification is unaffected.

---

## Running it

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate      # macOS / Linux

pip install -r requirements.txt

python -m app.seed.seed --reset --verify
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: <http://localhost:8000/docs>

### Seed accounts

| Role | Email | Password |
|---|---|---|
| Admin | `admin@gemverify.local` | `Admin123!` |
| Bidders | `contact@abcindustrialsystems.example` and five more (printed by the seed command) | `Password123!` |

### Tests

```bash
cd backend
pytest -q
```

The extraction suite runs the parser over all 72 specimen documents and asserts
every identifier against the dataset's own `manifest.json`.

---

## The specimen dataset

`backend/data/specimen/` holds 72 synthetic PDFs — six bidders × twelve document
types — against tender `GEM/2026/B/4471902`. Every page is watermarked
SPECIMEN; all companies, people and identifiers are fictitious.

| Dataset | Company | Injected defect |
|---|---|---|
| d1–d3 | ABC Industrial, XYZ Electromech, PQR Engineering | none |
| d4 | LMN Power Solutions | GSTIN mod-36 check character wrong |
| d5 | DEF Techno Equipments | PAN card shows a stale legal name |
| d6 | GHI Automation | Aadhaar Verhoeff check digit wrong |

The mock registries are **derived from these documents at seed time**, so the
registry and the documents agree by construction. Where a defect was injected,
the registry holds the *correct* value — that asymmetry is what makes the defect
detectable rather than merely asserted.

### One extraction detail worth knowing

The watermark's glyphs sit in the same content stream as the real text, so a
plain `page.extract_text()` interleaves them into values:

```
Address : Plot 14, SIDCO InduNstrial Estate, ...
Period of Validity (To) : Not AMpplicable
```

Silently corrupted fields would produce confident wrong verdicts. Rotated glyphs
are identifiable by their text matrix, so `app/verification/extraction.py`
filters them out and keeps only upright text. `test_watermark_is_stripped` locks
that behaviour in.

No OCR is needed: these are text-layer PDFs with `Label : Value` structure.

---

## Layout

```
backend/
  app/
    config.py            all tunable constants, including the similarity bands
    database.py          engine, session, SQLite WAL setup
    security.py          Argon2id hashing, session tokens
    deps.py              current user, role gates, ownership checks
    models/              ORM: application tables + mock_* registry tables
    schemas.py           API request/response shapes
    routers/             auth, tenders, bids, documents, notifications, admin
    services/            storage, audit, notifications
    verification/
      extraction.py      watermark-safe text + per-type field parsers
      validators.py      Verhoeff, GSTIN mod-36, PAN/CIN/Udyam (from the dataset)
      registry.py        RegistryGateway — the seam for real government APIs
      orchestrator.py    the pipeline
    seed/seed.py         users, tender, registries, demo bids
  data/specimen/         the 72 synthetic PDFs + manifest + ground truth
  uploads/               private document storage (git-ignored)
  tests/
docs/
  API_CONTRACT.md        frozen interface between backend and frontend
```

---

## Security posture

What is actually implemented:

- Passwords hashed with **Argon2id**. There is no column that could hold a
  plaintext password.
- Role comes from the database. There is no role selector at login.
- Uploads live outside any static route. `/uploads` is never served. The only
  path to a document is `GET /api/documents/{id}`, which authorizes the caller
  against the owning bid and writes an audit entry before returning bytes.
- Stored filenames are random UUIDs; the original name is a display label only,
  so a crafted filename cannot influence the path on disk.
- Uploads are validated by magic bytes, not by the declared content type, and
  capped at 10 MB.
- A bidder can only ever reach rows tracing back to their own user id. The file
  path is never the security mechanism.
- Revisions never overwrite evidence: a resubmitted document is a new row with
  `supersedes_id` set, and the previous row is kept.

What is **not** implemented, and should not be claimed: encryption at rest,
TLS termination, key management, retention policies. Those belong to a
production deployment on encrypted object storage.

---

## Status

- [x] API contract frozen
- [x] Schema, auth, authorization, audit trail
- [x] Tenders, bids, secure upload and document serving
- [x] Extraction — 72/72 specimen documents, every identifier exact
- [x] Mock registry gateway and seed
- [x] Deterministic rules engine — 20 check types, no LLM in any verdict
- [x] Cross-document consistency engine — five dimensions, canonical comparison
- [ ] Ollama narration layer

See `PROGRESS.md` for the running status of both tracks.
