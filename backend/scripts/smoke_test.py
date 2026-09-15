"""End-to-end smoke test against a running server.

Exercises the whole stack the way the frontend will: log in, submit a bid, wait
for the background pipeline, read the verification results and the consistency
report, then drive the admin clarification loop and the bidder's resubmission.
It also checks the authorization boundary that matters most — one bidder must
never be able to read another bidder's document.

Unit tests cover the engine in isolation. This covers everything the engine
cannot: SQLAlchemy mappings, the background task, cookie sessions, routing and
the status transitions.

Usage:
    # terminal 1
    .\\.venv\\Scripts\\python.exe -m app.seed.seed --reset --with-bids
    .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000

    # terminal 2
    .\\.venv\\Scripts\\python.exe scripts\\smoke_test.py

Exits 0 if everything passed, 1 otherwise.
"""

from __future__ import annotations

import sys
import time

import httpx

BASE = "http://localhost:8000/api"
ADMIN = ("admin@gemverify.local", "Admin123!")
PASSWORD = "Password123!"

# email -> (expected bid status, the per-document check that must flag, the
# cross-document verdict that must appear). None means "nothing expected here".
EXPECTED = {
    # clean
    "contact@abcindustrialsystems.example": ("VERIFIED", None, None),
    "contact@xyzelectromech.example": ("VERIFIED", None, None),
    "contact@pqrengineeringworks.example": ("VERIFIED", None, None),
    # field-level defects — caught in pass 1
    "contact@lmnpowersolutions.example": ("MANUAL_REVIEW", "GSTIN_CHECKSUM", None),
    "contact@deftechnoequipments.example": (
        "MANUAL_REVIEW", "PAN_NAME_MATCH", "POTENTIAL_INCONSISTENCY",
    ),
    "contact@ghiautomation.example": ("MANUAL_REVIEW", "AADHAAR_VERHOEFF", None),
    # every field valid; the defect exists only between documents. Pass 1 finds
    # nothing in any of these four — that is the point of the product.
    "contact@sterlinghydrosystems.example": ("MANUAL_REVIEW", None, "VARIATION"),
    "contact@meridianprocesscontrols.example": ("MANUAL_REVIEW", None, "VARIATION"),
    "contact@orionthermalengineering.example": ("MANUAL_REVIEW", None, "INCONSISTENT"),
    "contact@vertexfluidsystems.example": ("MANUAL_REVIEW", None, "INCONSISTENT"),
}

#: Bidders whose every per-document check must pass.
PURE_CROSS_DOCUMENT = {
    "contact@sterlinghydrosystems.example",
    "contact@meridianprocesscontrols.example",
    "contact@orionthermalengineering.example",
    "contact@vertexfluidsystems.example",
}

passed, failed = 0, 0


def check(label: str, condition: bool, detail: str = "") -> bool:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f"  -- {detail}" if detail else ""))
    return condition


def section(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


def login(client: httpx.Client, email: str, password: str) -> dict | None:
    response = client.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        print(f"  login failed for {email}: {response.status_code} {response.text[:200]}")
        return None
    return response.json()


def wait_for_verification(client: httpx.Client, bid_id: int, timeout: float = 90.0) -> dict:
    """Poll exactly as the frontend will."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        bid = client.get(f"{BASE}/bids/{bid_id}").json()
        if bid.get("status") != "PROCESSING":
            return bid
        time.sleep(1.0)
    return {"status": "TIMEOUT"}


def main() -> int:
    section("Server")
    try:
        health = httpx.get("http://localhost:8000/api/health", timeout=5)
    except Exception as exc:  # noqa: BLE001
        print(f"  Cannot reach the server: {exc}")
        print("  Start it with: .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000")
        return 1
    check("health endpoint responds", health.status_code == 200)

    # ---------------------------------------------------------------- admin
    section("Authentication and roles")
    admin = httpx.Client(timeout=30, follow_redirects=True)
    account = login(admin, *ADMIN)
    if not check("admin can log in", account is not None):
        # Everything downstream is an admin call. Continuing past this point
        # produces a cascade of failures that hide the one real cause.
        print(
            "\n  Cannot continue without an admin session.\n"
            "  Re-seed first:  .\\.venv\\Scripts\\python.exe -m app.seed.seed --reset --verify"
        )
        return 1
    check("role comes from the database", account["role"] == "ADMIN", str(account))
    check(
        "session cookie is httpOnly",
        "gv_session" in admin.cookies,
        "no session cookie was set",
    )

    bad = httpx.Client(timeout=10)
    wrong = bad.post(f"{BASE}/auth/login", json={"email": ADMIN[0], "password": "wrong"})
    check("wrong password is rejected", wrong.status_code == 401)
    check(
        "rejection does not reveal whether the email exists",
        "Incorrect email or password" in wrong.text,
        wrong.text[:120],
    )

    anonymous = httpx.Client(timeout=10)
    check(
        "unauthenticated request is refused",
        anonymous.get(f"{BASE}/admin/overview").status_code == 401,
    )

    section("Narration backend")
    ai = admin.get(f"{BASE}/ai/status").json()
    print(f"  Ollama: {ai.get('detail')}")
    check("ai status endpoint responds", "ready" in ai)

    section("Tender")
    tenders = admin.get(f"{BASE}/tenders").json()
    # A list is expected. An error envelope is a dict, and indexing it raises a
    # confusing KeyError instead of reporting the real problem.
    if not check(
        "at least one seeded tender",
        isinstance(tenders, list) and len(tenders) >= 1,
        f"expected a list of tenders, got {tenders!r:.160}",
    ):
        return 1
    tender = admin.get(f"{BASE}/tenders/{tenders[0]['id']}").json()
    check(
        "tender declares 12 required documents",
        len(tender.get("required_documents", [])) == 12,
        str(len(tender.get("required_documents", []))),
    )

    # ------------------------------------------------------------- pipeline
    section("Verification pipeline")
    results: dict[str, dict] = {}
    clients: dict[str, httpx.Client] = {}

    for email, (expected_status, expected_check, expected_verdict) in EXPECTED.items():
        client = httpx.Client(timeout=30)
        user = login(client, email, PASSWORD)
        if not user:
            check(f"{email} can log in", False)
            continue
        clients[email] = client

        bids = client.get(f"{BASE}/bids").json()
        if not isinstance(bids, list) or not bids:
            check(
                f"{email} has a seeded bid",
                False,
                f"run the seed with --verify (got {bids!r:.120})",
            )
            continue

        bid_id = bids[0]["id"]
        # Works against either seed mode: --with-bids leaves drafts to submit,
        # --verify leaves them already verified.
        current = bids[0].get("status")
        if current in ("DRAFT", "CLARIFICATION_REQUIRED"):
            submit = client.post(f"{BASE}/bids/{bid_id}/submit")
            if submit.status_code not in (200, 202):
                check(f"{email} can submit", False, f"{submit.status_code} {submit.text[:200]}")
                continue
            bid = wait_for_verification(client, bid_id)
        elif current == "PROCESSING":
            bid = wait_for_verification(client, bid_id)
        else:
            bid = client.get(f"{BASE}/bids/{bid_id}").json()
        results[email] = bid
        company = (bid.get("bidder_company") or email)[:38]
        print(
            f"  {company:<40} {bid.get('status','?'):<15} "
            f"score {bid.get('verification_score')}"
        )
        check(
            f"{company} reaches {expected_status}",
            bid.get("status") == expected_status,
            f"got {bid.get('status')}",
        )

        verification = client.get(f"{BASE}/bids/{bid_id}/verification").json()
        flagged = {
            r["check_type"]
            for d in verification["documents"]
            for r in d["results"]
            if r["result"] in ("FAIL", "REVIEW")
        }
        if expected_check:
            check(
                f"{company} raises {expected_check}",
                expected_check in flagged,
                f"raised {flagged or 'nothing'}",
            )
        if email in PURE_CROSS_DOCUMENT:
            check(
                f"{company} passes every per-document check",
                flagged == set(),
                f"pass 1 should find nothing, raised {flagged}",
            )
        if expected_verdict:
            report = client.get(f"{BASE}/bids/{bid_id}/consistency").json()
            verdicts = {f["verdict"] for f in report.get("flags", [])}
            check(
                f"{company} raises a {expected_verdict} flag",
                expected_verdict in verdicts,
                f"got {verdicts or 'no flags'}",
            )

    section("Cross-document consistency")
    target_email = "contact@deftechnoequipments.example"
    if target_email in results:
        bid_id = results[target_email]["id"]
        client = clients[target_email]
        report = client.get(f"{BASE}/bids/{bid_id}/consistency").json()
        check("consistency report is served", "dimensions" in report, str(report)[:200])
        check(
            "all five dimensions present",
            len(report.get("dimensions", [])) == 5,
            str([d["dimension"] for d in report.get("dimensions", [])]),
        )
        flags = report.get("flags", [])
        check("the stale PAN name is flagged", len(flags) >= 1, "no flags raised")
        if flags:
            print(f"  flag: {flags[0]['title']} [{flags[0]['verdict']}]")

    section("Authorization boundary")
    emails = list(clients)
    if len(emails) >= 2:
        owner, intruder = clients[emails[0]], clients[emails[1]]
        own_bid = owner.get(f"{BASE}/bids").json()[0]
        document_id = owner.get(f"{BASE}/bids/{own_bid['id']}").json()["documents"][0]["id"]

        check(
            "owner can read their own document",
            owner.get(f"{BASE}/documents/{document_id}").status_code == 200,
        )
        forbidden = intruder.get(f"{BASE}/documents/{document_id}")
        check(
            "another bidder is refused (403)",
            forbidden.status_code == 403,
            f"got {forbidden.status_code} — THIS IS A SECURITY BUG",
        )
        check(
            "an administrator may read it",
            admin.get(f"{BASE}/documents/{document_id}").status_code == 200,
        )

    # ------------------------------------------------ clarification round-trip
    section("Clarification and resubmission")
    if target_email in results:
        bid_id = results[target_email]["id"]
        client = clients[target_email]
        detail = admin.get(f"{BASE}/bids/{bid_id}").json()
        pan_doc = next(d for d in detail["documents"] if d["document_type"] == "PAN")

        response = admin.post(
            f"{BASE}/admin/bids/{bid_id}/clarification",
            json={
                "document_ids": [pan_doc["id"]],
                "message": "The name on your PAN card differs from your registered legal name.",
            },
        )
        check("admin can request clarification", response.status_code == 200, response.text[:200])
        check(
            "bid moves to CLARIFICATION_REQUIRED",
            response.status_code == 200
            and response.json()["status"] == "CLARIFICATION_REQUIRED",
        )

        notifications = client.get(f"{BASE}/notifications?unread_only=true").json()
        check(
            "bidder receives a persisted notification",
            notifications.get("unread_count", 0) > 0,
            str(notifications)[:200],
        )
        if notifications.get("items"):
            print(f"  notification: {notifications['items'][0]['title']}")

        # Resubmit the same file: the point is that a new version is created and
        # the previous row is preserved, not that the content changed.
        pdf = admin.get(f"{BASE}/documents/{pan_doc['id']}").content
        resubmit = client.post(
            f"{BASE}/documents/{pan_doc['id']}/resubmit",
            files={"file": ("revised-pan.pdf", pdf, "application/pdf")},
        )
        check("bidder can resubmit", resubmit.status_code in (200, 201), resubmit.text[:200])
        if resubmit.status_code in (200, 201):
            revision = resubmit.json()
            check("revision is version 2", revision["version"] == 2, str(revision["version"]))
            check(
                "revision supersedes the original, which is kept",
                revision["supersedes_id"] == pan_doc["id"],
            )
            after = wait_for_verification(client, bid_id)
            check("re-verification runs", after.get("status") != "TIMEOUT", str(after)[:120])
            print(f"  after resubmission: {after.get('status')} score {after.get('verification_score')}")

    section("Upload validation")
    if clients:
        client = list(clients.values())[0]
        bid_id = client.get(f"{BASE}/bids").json()[0]["id"]
        doc_id = client.get(f"{BASE}/bids/{bid_id}").json()["documents"][0]["id"]
        response = client.post(
            f"{BASE}/documents/{doc_id}/resubmit",
            files={"file": ("evil.pdf", b"not a pdf at all", "application/pdf")},
        )
        check(
            "a non-PDF claiming to be a PDF is rejected",
            response.status_code == 400,
            f"got {response.status_code} — magic-byte check may not be running",
        )

    section("AI explanation")
    if target_email in results:
        bid_id = results[target_email]["id"]
        for _ in range(20):
            response = admin.get(f"{BASE}/bids/{bid_id}/explanation?kind=ADMIN_SUMMARY")
            if response.status_code == 200:
                break
            time.sleep(1.5)
        if check("admin summary is generated", response.status_code == 200, response.text[:160]):
            body = response.json()
            source = "templated fallback" if body["is_fallback"] else body["model"]
            print(f"  [{source}] {body['text'][:220]}")

        bidder = clients[target_email]
        refused = bidder.get(f"{BASE}/bids/{bid_id}/explanation?kind=ADMIN_SUMMARY")
        check("bidders cannot read the officer's summary", refused.status_code == 403)

    # --------------------------------------------- scores are admin-only
    section("Score visibility")
    if target_email in results:
        bid_id = results[target_email]["id"]
        bidder = clients[target_email]

        as_bidder = bidder.get(f"{BASE}/bids/{bid_id}").json()
        check(
            "bidder's own bid carries no verification score",
            as_bidder.get("verification_score") is None,
            f"got {as_bidder.get('verification_score')} — THIS LEAKS THE SCORE",
        )
        listed = bidder.get(f"{BASE}/bids").json()
        check(
            "no bid in the bidder's list carries a score",
            all(b.get("verification_score") is None for b in listed),
        )
        dash = bidder.get(f"{BASE}/dashboard").json()
        check(
            "the bidder dashboard carries no scores",
            all(
                b.get("verification_score") is None
                for key in ("recent_bids", "action_required")
                for b in dash.get(key, [])
            ),
        )

        bidder_report = bidder.get(f"{BASE}/bids/{bid_id}/consistency").json()
        check(
            "bidder's consistency report has no overall score",
            bidder_report.get("overall_score") is None
            and bidder_report.get("document_score") is None
            and bidder_report.get("consistency_score") is None,
        )
        check(
            "no dimension percentage reaches the bidder",
            all(d.get("score") is None for d in bidder_report.get("dimensions", [])),
        )
        check(
            "no per-document similarity reaches the bidder",
            all(
                o.get("similarity") is None
                for d in bidder_report.get("dimensions", [])
                for o in d.get("observations", [])
            ),
        )
        check(
            "the bidder still sees the verdicts and findings",
            len(bidder_report.get("dimensions", [])) == 5,
            "the findings must stay — only the numbers are withheld",
        )

        as_admin = admin.get(f"{BASE}/bids/{bid_id}").json()
        check(
            "an administrator still sees the score",
            as_admin.get("verification_score") is not None,
        )
        admin_report = admin.get(f"{BASE}/bids/{bid_id}/consistency").json()
        check(
            "an administrator still sees every percentage",
            admin_report.get("overall_score") is not None
            and any(d.get("score") is not None for d in admin_report.get("dimensions", [])),
        )

    # --------------------------------------------------- withdraw / reapply
    section("Withdraw and reapply")
    spare = [e for e in results if e != target_email]
    if spare:
        email = spare[-1]
        bidder = clients[email]
        bid_id = results[email]["id"]

        withdrawn = bidder.post(f"{BASE}/bids/{bid_id}/withdraw")
        check("a submitted bid can be withdrawn", withdrawn.status_code == 200,
              f"got {withdrawn.status_code}: {withdrawn.text[:160]}")
        check(
            "the bid is now WITHDRAWN",
            withdrawn.status_code == 200 and withdrawn.json()["status"] == "WITHDRAWN",
        )
        again = bidder.post(f"{BASE}/bids/{bid_id}/withdraw")
        check("withdrawing twice is refused", again.status_code == 400)

        decided = admin.post(f"{BASE}/admin/bids/{bid_id}/approve", json={"note": "no"})
        check(
            "an administrator cannot approve a withdrawn bid",
            decided.status_code == 400,
            f"got {decided.status_code} — a withdrawn bid must not be decidable",
        )

        intruder = clients[target_email]
        check(
            "another bidder cannot withdraw it",
            intruder.post(f"{BASE}/bids/{bid_id}/withdraw").status_code in (403, 404),
        )

        fresh = bidder.post(f"{BASE}/bids/{bid_id}/reapply")
        check("a withdrawn bid can be reapplied for", fresh.status_code == 201,
              f"got {fresh.status_code}: {fresh.text[:160]}")
        if fresh.status_code == 201:
            new_bid = fresh.json()
            check("reapplying opens a new bid", new_bid["id"] != bid_id)
            check("the new bid is a draft", new_bid["status"] == "DRAFT")
            check(
                "the documents were carried over",
                new_bid["document_count"] > 0,
                str(new_bid["document_count"]),
            )
            carried = bidder.get(f"{BASE}/bids/{new_bid['id']}").json()
            check(
                "carried documents start unverified",
                all(d["status"] == "PENDING" for d in carried["documents"]),
                str({d["status"] for d in carried["documents"]}),
            )
            stale = bidder.get(f"{BASE}/bids/{bid_id}").json()
            check(
                "the withdrawn bid is kept on record",
                stale["status"] == "WITHDRAWN",
            )

    section("Audit trail")
    logs = admin.get(f"{BASE}/admin/audit-logs?limit=200").json()
    actions = {item["action"] for item in logs.get("items", [])}
    for action in (
        "USER_LOGGED_IN",
        "BID_SUBMITTED",
        "VERIFICATION_COMPLETED",
        "ADMIN_VIEWED_DOCUMENT",
        "ADMIN_REQUESTED_CLARIFICATION",
        "DOCUMENT_RESUBMITTED",
        "BID_WITHDRAWN",
        "BID_REAPPLIED",
    ):
        check(f"{action} is recorded", action in actions)

    print(f"\n{'=' * 60}\n  {passed} passed, {failed} failed\n{'=' * 60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
