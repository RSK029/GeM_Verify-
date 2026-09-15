"""Seed the database.

The mock registries are derived from the specimen documents themselves, so the
registry and the documents agree by construction for every clean dataset. Where
the specimen has a deliberately injected defect, the registry holds the
*correct* value — that asymmetry is what makes the defect detectable:

  d4  GSTIN check character corrupted in the document
      -> registry stores the GSTIN with the correct mod-36 character
  d5  PAN card shows a stale legal name
      -> registry stores the company's current legal name
  d6  Aadhaar check digit corrupted
      -> no registry involved; Verhoeff is a local, deterministic check

Run:  python -m app.seed.seed                       (users, tender, registries)
      python -m app.seed.seed --with-bids           (also files draft bids)
      python -m app.seed.seed --reset --verify      (and verifies them)
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, init_db
from ..models import (
    DOCUMENT_LABELS,
    AuditAction,
    Bid,
    BidStatus,
    Document,
    DocumentStatus,
    DocumentType,
    MockCompanyRegistry,
    MockEpfoRegistry,
    MockFinancialRegistry,
    MockGstRegistry,
    MockOemRegistry,
    MockPanRegistry,
    MockUdyamRegistry,
    Role,
    Tender,
    TenderRequiredDocument,
    TenderStatus,
    User,
)
from ..security import hash_password
from ..services import storage
from ..verification import extraction
from ..verification.validators import gstin_check_char

SPECIMEN = settings.SPECIMEN_DIR
TENDER_NUMBER = "GEM/2026/B/4471902"
TENDER_TITLE = "CPCL Industrial Equipment Procurement - 2026"
DEPARTMENT = "Chennai Petroleum Corporation Limited"

DEMO_PASSWORD = "Password123!"
ADMIN_PASSWORD = "Admin123!"


def _slug_email(company: str) -> str:
    stem = "".join(ch for ch in company.lower() if ch.isalnum() or ch == " ")
    stem = stem.replace("private limited", "").strip().replace(" ", "")
    return f"contact@{stem or 'bidder'}.example"


def _specimen_pdf(dataset: str, doc_type: DocumentType) -> Path:
    return SPECIMEN / "pdfs" / f"{dataset}-{doc_type.slug}.pdf"


def _extract(dataset: str, doc_type: DocumentType) -> dict:
    path = _specimen_pdf(dataset, doc_type)
    if not path.exists():
        return {}
    try:
        return extraction.extract(path, doc_type)
    except Exception:  # noqa: BLE001 - seeding must not die on one bad file
        return {}


# --------------------------------------------------------------------------
# registries
# --------------------------------------------------------------------------


def seed_registries(db: Session, manifest: list[dict]) -> None:
    for row in manifest:
        ds = row["dataset"]
        defect = row.get("defect", "none")

        gst = _extract(ds, DocumentType.GST_CERTIFICATE)
        inc = _extract(ds, DocumentType.INCORPORATION)
        udy = _extract(ds, DocumentType.UDYAM)
        epf = _extract(ds, DocumentType.EPFO_ESIC)
        oem = _extract(ds, DocumentType.OEM_AUTHORISATION)
        tov = _extract(ds, DocumentType.TURNOVER)

        legal_name = row["company"]
        pan = row["pan"]
        address = gst.get("address") or inc.get("address") or ""

        # --- PAN -------------------------------------------------------
        # The registry always holds the company's current legal name. For d5
        # the PAN *card* shows a stale name; the mismatch is the finding.
        db.merge(
            MockPanRegistry(
                pan=pan, name=legal_name, holder_type=pan[3] if len(pan) > 3 else "C", status="ACTIVE"
            )
        )

        # --- GST -------------------------------------------------------
        gstin = row["gstin"]
        if defect == "gstin_checksum":
            # Store the GSTIN as it *should* be, so the corrupted one on the
            # certificate is absent from the registry as well as failing its
            # own checksum.
            gstin = gstin[:14] + gstin_check_char(gstin[:14])
        db.merge(
            MockGstRegistry(
                gstin=gstin,
                legal_name=legal_name,
                trade_name=gst.get("trade_name"),
                pan=pan,
                address=address,
                state_code=gstin[:2],
                status="ACTIVE",
                registration_date=_parse_date(gst.get("registration_date")),
            )
        )

        # --- Udyam -----------------------------------------------------
        db.merge(
            MockUdyamRegistry(
                udyam_number=row["udyam"],
                business_name=legal_name,
                pan=pan,
                gstin=gstin,
                address=udy.get("address") or address,
                enterprise_type=udy.get("enterprise_type") or "Small",
                status="ACTIVE",
            )
        )

        # --- MCA -------------------------------------------------------
        db.merge(
            MockCompanyRegistry(
                cin=row["cin"],
                company_name=legal_name,
                pan=pan,
                registered_address=inc.get("address") or address,
                incorporation_date=_parse_date(inc.get("date_of_incorporation")),
                directors=inc.get("directors") or row["signatory"],
                status="ACTIVE",
            )
        )

        # --- OEM -------------------------------------------------------
        db.merge(
            MockOemRegistry(
                authorization_id=f"OEM-{ds.upper()}-{TENDER_NUMBER.split('/')[-1]}",
                oem_name=oem.get("oem_name") or "Unknown OEM",
                dealer_name=legal_name,
                dealer_pan=pan,
                tender_number=TENDER_NUMBER,
                product=oem.get("tender_title") or TENDER_TITLE,
                valid_until=datetime(2027, 3, 31, tzinfo=timezone.utc).replace(tzinfo=None),
                status="ACTIVE",
            )
        )

        # --- EPFO ------------------------------------------------------
        db.merge(
            MockEpfoRegistry(
                establishment_code=row["epfo_code"],
                establishment_name=legal_name,
                pan=pan,
                esic_code=row["esic_code"],
                subscribers=0,
                status="ACTIVE",
            )
        )

        # --- financials ------------------------------------------------
        existing = (
            db.query(MockFinancialRegistry)
            .filter_by(pan=pan, financial_year="2024-25")
            .first()
        )
        turnover = float(tov.get("turnover_cr") or row["turnover_fy2024_25_cr"])
        if existing:
            existing.turnover_cr = turnover
        else:
            db.add(
                MockFinancialRegistry(
                    pan=pan, financial_year="2024-25", turnover_cr=turnover
                )
            )
    db.flush()


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# users, tender
# --------------------------------------------------------------------------


def seed_users(db: Session, manifest: list[dict]) -> dict[str, User]:
    admin = db.query(User).filter_by(email="admin@gemverify.local").first()
    if not admin:
        admin = User(
            name="Procurement Administrator",
            email="admin@gemverify.local",
            password_hash=hash_password(ADMIN_PASSWORD),
            role=Role.ADMIN.value,
            company_name=DEPARTMENT,
        )
        db.add(admin)

    bidders: dict[str, User] = {}
    for row in manifest:
        email = _slug_email(row["company"])
        user = db.query(User).filter_by(email=email).first()
        if not user:
            user = User(
                name=row["signatory"],
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                role=Role.BIDDER.value,
                company_name=row["company"],
            )
            db.add(user)
        bidders[row["dataset"]] = user
    db.flush()
    return bidders


def seed_tender(db: Session) -> Tender:
    tender = db.query(Tender).filter_by(tender_number=TENDER_NUMBER).first()
    if tender:
        return tender
    tender = Tender(
        tender_number=TENDER_NUMBER,
        title=TENDER_TITLE,
        department=DEPARTMENT,
        description=(
            "Supply of centrifugal process pumps (API 610 OH2), LT motor control "
            "centres, shell & tube heat exchangers, variable frequency drive panels "
            "and HART pressure transmitters, including installation supervision, "
            "commissioning and two years' warranty support."
        ),
        estimated_value=48_00_000 * 10,
        closing_date=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=13),
        status=TenderStatus.OPEN.value,
    )
    db.add(tender)
    db.flush()
    for order, doc_type in enumerate(DocumentType):
        db.add(
            TenderRequiredDocument(
                tender_id=tender.id,
                document_type=doc_type.value,
                label=DOCUMENT_LABELS[doc_type],
                mandatory=doc_type is not DocumentType.BANK_MANDATE,
                sort_order=order,
            )
        )
    db.flush()
    return tender


# --------------------------------------------------------------------------
# demo bids
# --------------------------------------------------------------------------


def seed_bids(db: Session, manifest: list[dict], bidders: dict[str, User], tender: Tender) -> list[int]:
    """Create one bid per specimen bidder with all twelve documents attached.

    Bids are left in DRAFT so that submitting them is a real action someone can
    take — the smoke test does, and so does the demo if you want to show the
    pipeline running live. Pass --verify to have the seed submit and verify them
    for you, which is what you want before a presentation.

    They are deliberately *not* left in SUBMITTED: nothing advances a bid out of
    that state except the submit endpoint, which refuses a bid already in it, so
    a SUBMITTED seed is a dead end.
    """
    created: list[int] = []
    for row in manifest:
        ds = row["dataset"]
        bidder = bidders[ds]
        existing = db.query(Bid).filter_by(bidder_id=bidder.id, tender_id=tender.id).first()
        if existing:
            continue

        bid = Bid(
            bidder_id=bidder.id,
            tender_id=tender.id,
            status=BidStatus.DRAFT.value,
        )
        db.add(bid)
        db.flush()
        created.append(bid.id)

        directory = storage.bid_directory(bidder.id, bid.id)
        for doc_type in DocumentType:
            source = _specimen_pdf(ds, doc_type)
            if not source.exists():
                continue
            content = source.read_bytes()
            stored = storage.save(content, bidder_id=bidder.id, bid_id=bid.id)
            db.add(
                Document(
                    bid_id=bid.id,
                    document_type=doc_type.value,
                    original_filename=source.name,
                    stored_filename=stored.stored_filename,
                    file_path=stored.file_path,
                    size_bytes=stored.size_bytes,
                    sha256=stored.sha256,
                    status=DocumentStatus.PENDING.value,
                )
            )
        _ = directory
    db.flush()
    return created


def verify_bids(db: Session, bid_ids: list[int]) -> None:
    """Submit and verify seeded bids, leaving them in their final state.

    Runs the pipeline inline rather than as a background task, so the command
    does not return until every bid is actually verified.
    """
    from ..services import audit
    from ..verification import orchestrator

    for bid_id in bid_ids:
        bid = db.get(Bid, bid_id)
        if bid is None:
            continue
        bid.status = BidStatus.PROCESSING.value
        bid.submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        # A seeded submission is still a submission. Writing the audit entry
        # here keeps the claim "every action is recorded" literally true — a
        # bid must never appear in the system already verified with no record
        # of anyone having submitted it.
        audit.record(
            db,
            user_id=bid.bidder_id,
            action=AuditAction.BID_SUBMITTED,
            bid_id=bid.id,
            details=f"Bid submitted with {len(bid.active_documents)} documents (seeded)",
        )
    db.commit()

    for bid_id in bid_ids:
        orchestrator.run_for_bid(bid_id)


# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the GeMVerify database")
    parser.add_argument(
        "--with-bids",
        action="store_true",
        help="also file one submitted bid per specimen bidder",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="also submit and verify the seeded bids (implies --with-bids)",
    )
    parser.add_argument(
        "--reset", action="store_true", help="delete the database and uploads first"
    )
    args = parser.parse_args()

    if args.reset:
        from ..config import DB_PATH

        for path in (DB_PATH, Path(str(DB_PATH) + "-wal"), Path(str(DB_PATH) + "-shm")):
            path.unlink(missing_ok=True)
        if settings.UPLOAD_DIR.exists():
            shutil.rmtree(settings.UPLOAD_DIR)
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        print("reset: database and uploads removed")

    init_db()
    manifest = json.loads((SPECIMEN / "manifest.json").read_text())

    bid_ids: list[int] = []
    db = SessionLocal()
    try:
        seed_registries(db, manifest)
        bidders = seed_users(db, manifest)
        tender = seed_tender(db)
        if args.with_bids or args.verify:
            bid_ids = seed_bids(db, manifest, bidders, tender)
        db.commit()
    finally:
        db.close()

    if args.verify and bid_ids:
        print(f"verifying {len(bid_ids)} bids (this runs the full pipeline)...")
        db = SessionLocal()
        try:
            verify_bids(db, bid_ids)
        finally:
            db.close()

    print(f"seeded {len(manifest)} bidders against {TENDER_NUMBER}")
    print(f"  admin  : admin@gemverify.local / {ADMIN_PASSWORD}")
    for row in manifest:
        print(f"  bidder : {_slug_email(row['company'])} / {DEMO_PASSWORD}  ({row['defect']})")
    if args.verify:
        print(f"filed and verified {len(bid_ids)} bids; they are ready to review")
    elif args.with_bids:
        print(
            f"filed {len(bid_ids)} draft bids with documents attached; "
            "submit them from the API, or re-run with --verify"
        )


if __name__ == "__main__":
    main()
