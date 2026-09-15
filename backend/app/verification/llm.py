"""The narration layer.

Ollama runs *after* the verdict is final and reads the finished decision record.
It cannot change a verdict, a score or a status — it turns them into the prose a
human needs. That separation is deliberate and is the answer to "how do you know
the AI didn't just make this up": the AI did not decide anything.

Four generation tasks:

  ADMIN_SUMMARY        what was checked, what passed, what needs attention
  FLAG_EXPLANATION     what a specific finding means and what would resolve it
  CLARIFICATION_DRAFT  a plain, non-accusatory message to the bidder
  DECISION_REASONING   the detailed "why" behind the bid's current status

Every one has a templated fallback. If Ollama is not installed, has no model
pulled, or is slow, the fallback text is used, ``is_fallback`` is set, and
verification is entirely unaffected. The demo cannot break here.

Only the decision record is sent — structured fields already extracted, never
document text or a PDF. That satisfies the "do not send sensitive documents to
the model" rule by construction rather than by discipline.
"""

from __future__ import annotations

import json
import logging

import httpx

from ..config import settings
from ..models import ConsistencyVerdict, DocumentStatus, DocumentType, ExplanationKind

log = logging.getLogger("gemverify.llm")

_SYSTEM = (
    "You are a procurement verification assistant for an Indian government "
    "e-marketplace. You are given the FINAL results of a completed, deterministic "
    "verification run. Your only job is to explain those results in clear, neutral "
    "English for the reader described in the prompt.\n\n"
    "Rules you must follow:\n"
    "- Never contradict, re-decide or re-score anything. The verdicts are final.\n"
    "- Never accuse anyone of fraud. A mismatch may be clerical. Say what differs "
    "and what would resolve it.\n"
    "- Never invent a check, a value or a document that is not in the data.\n"
    "- Use plain professional English. No bullet lists, no markdown, no headings.\n"
    "- Be concise: at most the number of sentences requested."
)


# --------------------------------------------------------------------------
# the payload sent to the model
# --------------------------------------------------------------------------


def build_context(bid, report, documents) -> dict:
    """The minimum the model needs. Structured fields only — never document text."""
    flagged_checks = []
    for document in documents:
        for result in document.results:
            if result.result in ("FAIL", "REVIEW"):
                flagged_checks.append(
                    {
                        "document": DocumentType(document.document_type).pretty,
                        "check": result.check_type,
                        "result": result.result,
                        "submitted": result.submitted_value,
                        "on_record": result.registry_value,
                        "reason": result.reason,
                    }
                )

    return {
        "tender": bid.tender.tender_number,
        "bidder": bid.bidder.company_name,
        "status": bid.status,
        "scores": {
            "overall": bid.verification_score,
            "document_checks": bid.document_score,
            "cross_document_consistency": bid.consistency_score,
        },
        "documents": {
            "total": len(documents),
            "passed": sum(1 for d in documents if d.status == DocumentStatus.VERIFIED.value),
            "flagged": sum(
                1
                for d in documents
                if d.status in (DocumentStatus.FAILED.value, DocumentStatus.REVIEW.value)
            ),
        },
        "failed_or_review_checks": flagged_checks,
        "cross_document_findings": [
            {
                "dimension": flag["dimension"] if isinstance(flag, dict) else flag.dimension,
                "verdict": flag["verdict"] if isinstance(flag, dict) else flag.verdict,
                "finding": flag["title"] if isinstance(flag, dict) else flag.title,
                "values": flag["values"] if isinstance(flag, dict) else flag.values,
            }
            for flag in (report.flags if report else [])
        ],
    }


_PROMPTS = {
    ExplanationKind.ADMIN_SUMMARY: (
        "Reader: a procurement officer deciding whether to approve this bid.\n"
        "Write 3 to 5 sentences summarising what was verified, what passed, and "
        "what specifically needs their attention and why it matters. If nothing "
        "was flagged, say so plainly and do not manufacture concerns.\n\n"
        "Verification results:\n{context}"
    ),
    ExplanationKind.FLAG_EXPLANATION: (
        "Reader: a procurement officer looking at one specific finding.\n"
        "For each finding listed, write 2 sentences: what the difference actually "
        "is, and what benign explanation would account for it versus what would be "
        "concerning. Separate findings with a blank line.\n\n"
        "Verification results:\n{context}"
    ),
    ExplanationKind.CLARIFICATION_DRAFT: (
        "Reader: the bidder, a company representative who may have made an "
        "innocent clerical error.\n"
        "Write 2 to 4 sentences addressed to them, naming the document concerned "
        "and what they need to check or provide. Be courteous and specific. Do not "
        "imply wrongdoing and do not mention internal scores.\n\n"
        "Verification results:\n{context}"
    ),
    ExplanationKind.DECISION_REASONING: (
        "Reader: the bidder, who wants to understand their bid's current status.\n"
        "Write 3 to 5 sentences explaining why the bid is in this status, which "
        "specific checks produced that outcome, and what happens next. If the "
        "status is MANUAL_REVIEW, make clear this means a human is reviewing it, "
        "not that the bid has been rejected.\n\n"
        "Verification results:\n{context}"
    ),
}


# --------------------------------------------------------------------------
# ollama
# --------------------------------------------------------------------------


def available() -> tuple[bool, str]:
    """Is Ollama reachable, and does it have the configured model pulled?"""
    if not settings.OLLAMA_ENABLED:
        return False, "Ollama is disabled by configuration"
    try:
        response = httpx.get(f"{settings.OLLAMA_URL}/api/tags", timeout=3.0)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return False, f"Ollama is not reachable at {settings.OLLAMA_URL} ({exc.__class__.__name__})"

    models = [m.get("name", "") for m in response.json().get("models", [])]
    if not models:
        return False, "Ollama is running but no model has been pulled"
    wanted = settings.OLLAMA_MODEL
    if wanted not in models and not any(m.split(":")[0] == wanted.split(":")[0] for m in models):
        return False, f"model '{wanted}' is not pulled (available: {', '.join(models)})"
    return True, "ready"


def _generate(prompt: str) -> str | None:
    try:
        response = httpx.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "system": _SYSTEM,
                "prompt": prompt,
                "stream": False,
                # Zero temperature: the same bid must produce the same words in
                # front of judges twice running.
                "options": {"temperature": 0, "top_p": 1, "seed": 42, "num_predict": 400},
            },
            timeout=settings.OLLAMA_TIMEOUT_S,
        )
        response.raise_for_status()
        text = (response.json().get("response") or "").strip()
        return text or None
    except Exception as exc:  # noqa: BLE001
        log.warning("Ollama generation failed: %s", exc)
        return None


# --------------------------------------------------------------------------
# fallbacks
# --------------------------------------------------------------------------


def _fallback(kind: ExplanationKind, context: dict) -> str:
    docs = context["documents"]
    findings = context["cross_document_findings"]
    checks = context["failed_or_review_checks"]
    company = context["bidder"] or "The bidder"

    if kind is ExplanationKind.ADMIN_SUMMARY:
        parts = [
            f"{docs['passed']} of {docs['total']} documents passed every individual check."
        ]
        if checks:
            parts.append(
                "Checks requiring attention: "
                + "; ".join(f"{c['check']} on the {c['document']} ({c['reason']})" for c in checks)
                + "."
            )
        if findings:
            parts.append(
                "Cross-document findings: "
                + "; ".join(f"{f['finding']} ({f['verdict'].replace('_', ' ').lower()})" for f in findings)
                + "."
            )
        if not checks and not findings:
            parts.append("No individual or cross-document issues were detected.")
        parts.append(f"Overall score {context['scores']['overall']}. Status: {context['status'].replace('_', ' ').title()}.")
        return " ".join(parts)

    if kind is ExplanationKind.FLAG_EXPLANATION:
        if not findings:
            return "No cross-document inconsistencies were detected for this bid."
        return "\n\n".join(
            f"{f['finding']} — {f['verdict'].replace('_', ' ').lower()}. "
            f"Values compared: "
            + "; ".join(f"{k}: {v}" for k, v in (f["values"] or {}).items())
            for f in findings
        )

    if kind is ExplanationKind.CLARIFICATION_DRAFT:
        if checks:
            first = checks[0]
            return (
                f"Your {first['document']} requires clarification. {first['reason'].capitalize()}. "
                "Please verify the document submitted and upload a corrected version, "
                "or provide an explanation for the difference."
            )
        if findings:
            first = findings[0]
            return (
                f"{first['finding']}. Please review the documents concerned and either "
                "upload a corrected version or provide an explanation for the difference."
            )
        return (
            "Please review your submitted documents and confirm that the details provided "
            "are current and consistent."
        )

    # DECISION_REASONING
    status = context["status"].replace("_", " ").title()
    parts = [f"{company}'s bid is currently in status: {status}."]
    if checks:
        parts.append(
            "This follows from: "
            + "; ".join(f"{c['reason']} (on the {c['document']})" for c in checks)
            + "."
        )
    if findings:
        parts.append(
            "In addition, the submitted documents were compared against one another and "
            + "; ".join(f["finding"].lower() for f in findings)
            + "."
        )
    if context["status"] == "MANUAL_REVIEW":
        parts.append(
            "This status means a procurement officer is reviewing the bid. It is not a rejection."
        )
    return " ".join(parts)


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def explain(kind: ExplanationKind | str, context: dict) -> tuple[str, str | None, bool]:
    """Return ``(text, model_name, is_fallback)``.

    Never raises. A failure here degrades the prose, never the verification.
    """
    kind = ExplanationKind(str(kind))
    context = _for_reader(kind, context)
    ready, reason = available()
    if not ready:
        log.info("narration falling back to templates: %s", reason)
        return _fallback(kind, context), None, True

    prompt = _PROMPTS[kind].format(context=json.dumps(context, indent=1, default=str))
    text = _generate(prompt)
    if not text:
        return _fallback(kind, context), None, True
    return text, settings.OLLAMA_MODEL, False


#: The two narrations a bidder is allowed to read. They are written from a
#: context with the scores removed, so the model cannot quote a number the API
#: itself withholds — instructing it not to would be a request, not a
#: guarantee.
_BIDDER_FACING = {ExplanationKind.CLARIFICATION_DRAFT, ExplanationKind.DECISION_REASONING}


def _for_reader(kind: ExplanationKind, context: dict) -> dict:
    if kind not in _BIDDER_FACING:
        return context
    trimmed = dict(context)
    trimmed.pop("scores", None)
    return trimmed


def verdict_is_clean(report) -> bool:
    return not report or not report.flags or all(
        f.verdict == ConsistencyVerdict.CONSISTENT.value for f in report.flags
    )
