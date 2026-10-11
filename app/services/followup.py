"""'Ask about this feedback' (v2-followup).

A student can ask follow-up questions about the feedback on one attempt. Each question is a turn
in a short stored thread (shown again when the feedback page is reopened; at most
``followup_max_turns`` turns per attempt). With an AI provider the answer is generated from a
grounding context — the question, any stimulus, the student's response, the marking result and
feedback, the worked solution / model answer and the criteria — plus the earlier turns. Without
one, the question is saved to "Questions for my teacher" and the full reference material is shown.

This module never writes to ``Attempt`` or ``AttemptFeedback``: a follow-up answer cannot re-mark
an attempt or change its mark."""
from __future__ import annotations

import logging
import re
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import prompts_followup
from app.ai.base import AIError, AIUnavailable
from app.ai.factory import get_provider
from app.ai.schemas import FollowUpAnswer
from app.models import Attempt, Question, Stimulus, Subject
from app.models.common import ORIGIN_LABELS, utcnow
from app.models.followup import ANSWERED, FAILED, OFFLINE, FeedbackQuestion
from app.services import settings as st
from app.services.assessment.common import plan_and_outcome, subject_code

log = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 1000
MAX_ROWS_PER_ATTEMPT = 60  # answered + offline + failed (failed rows do not count as turns)
CHIPS = prompts_followup.CHIPS
CHIP_LABELS = prompts_followup.CHIP_LABELS

METHOD_LABELS = {
    "deterministic": "marked automatically",
    "ai": "AI-estimated mark (not an official NESA mark)",
    "offline_estimate": "offline estimate (no AI provider; not a marking judgement)",
    "self": "self-marked by the student against the marking guideline",
    "skipped": "skipped, recorded as 0",
}

# Feedback payload keys the grounding context handles explicitly. Anything else a package adds to
# the payload is passed through as "other feedback shown to the student".
_HANDLED = {
    "kind", "subject", "method", "label", "note", "mark", "max", "result", "model_answer", "model_answer_source", "comparison",
    "improved_answer", "guidance", "criteria_text", "criteria_official", "facts_checked", "unverified_references", "evidence",
    "disclaimer", "schedule", "previous", "working", "student_answer", "student_parsed", "correct_answer", "worked_solution",
    "divergence", "divergence_step", "concept", "quicker", "technique", "outcome", "revision", "error_category", "notes",
    "correct", "explanation", "guideline", "guideline_official", "self_marked",
    "evidence_role", "solution_shown", "model_viewed",  # v2-adaptive bookkeeping, not feedback
}
_RESULT_KEYS = ("performance_level", "marking_rationale", "next_level", "improvement_task", "improved_argument", "strengths",
                "weaknesses", "missing_elements", "corrections", "evidence_suggestions", "improvements", "revision_recommendation",
                "errors", "criteria", "dimensions")
_DIRECT_KEYS = ("note", "correct", "student_answer", "student_parsed", "correct_answer", "divergence", "divergence_step",
                "error_category", "explanation", "concept", "quicker", "technique", "revision", "notes", "comparison", "improved_answer")


class FollowUpError(ValueError):
    """A request the service refuses (empty question, turn limit, unknown attempt). ``status``
    is the HTTP status the route should use."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# ------------------------------------------------------------------ grounding ---
def _stimulus(db: Session, q: Question) -> tuple[str | None, str | None]:
    stim = q.stimulus
    if stim is None:
        return None, None
    texts = stim.reading_set() if hasattr(stim, "reading_set") else [stim]
    if len(texts) == 1 and stim.paired_with_id is None:
        partner = db.execute(select(Stimulus).where(Stimulus.paired_with_id == stim.id)).scalars().first()
        if partner is not None:
            texts = [stim, partner]
    body = "\n\n".join(f"{t.title}\n{t.body or ''}".strip() for t in texts if (t.body or t.title))
    attribution = "; ".join(t.attribution for t in texts if t.attribution)
    return body or None, attribution or None


def _photo_working(db: Session, attempt: Attempt) -> str | None:
    try:
        from app.services import working_photos as wp

        photos = wp.for_attempt(db, attempt.id)
    except Exception:  # the photo feature is optional for this module
        return None
    reading = next((p.reading for p in photos if p.reading), None)
    if not reading:
        return f"({len(photos)} photo(s) of handwritten working attached; not transcribed.)" if photos else None
    text = (reading.get("working_text") or "").strip()
    final = (reading.get("final_answer") or "").strip()
    out = "Transcribed from photos of handwritten working:\n" + text if text else ""
    if final:
        out += f"\nFinal answer as written: {final}"
    return out.strip() or None


def grounding(db: Session, attempt: Attempt) -> dict:
    """Everything the follow-up answer must be grounded in, for any kind of feedback (maths,
    MCQ, English, Legal, self-marked and skipped)."""
    q = attempt.question
    fbrow = attempt.feedback
    p = dict(fbrow.payload) if fbrow and fbrow.payload else {}
    code = subject_code(db, q)
    subj = db.get(Subject, q.subject_id)
    item, outcome = plan_and_outcome(db, q)
    sol = q.solution or {}
    stim_text, attribution = _stimulus(db, q)
    r = p.get("result") or {}

    feedback: dict = {k: p[k] for k in _DIRECT_KEYS if p.get(k) not in (None, "", [], {})}
    for k in _RESULT_KEYS:
        if r.get(k) not in (None, "", [], {}):
            feedback.setdefault(k, r[k])
    extra = {k: v for k, v in p.items() if k not in _HANDLED and v not in (None, "", [], {})}
    if extra:
        feedback["extra"] = extra

    worked = p.get("worked_solution") or sol.get("steps") or []
    correct = p.get("correct_answer")
    if correct is None and q.answer:
        from app.services.assessment import answer_display

        correct = answer_display(q)
    criteria = p.get("criteria_text") or p.get("guideline") or q.marking_guideline
    official = bool(p.get("criteria_official") if "criteria_official" in p else (p.get("guideline_official") or q.guideline_official))
    working = p.get("working")
    photo_working = _photo_working(db, attempt)
    if photo_working:
        working = f"{working}\n\n{photo_working}" if working else photo_working
    previous = None
    if attempt.attempt_number > 1:
        prev = db.scalars(select(Attempt).where(Attempt.question_id == q.id, _same_context(attempt),
                                                Attempt.attempt_number == attempt.attempt_number - 1)).first()
        previous = prev.response_text if prev else None
    method = attempt.marking_method or p.get("method") or ""
    # Maths hint-first (adaptive-15): until the student chooses "Show full solution" (or retries),
    # the correct answer and the worked solution stay hidden on the page, and here too.
    solution_hidden = (p.get("kind") == "maths" and not p.get("correct") and p.get("solution_shown") is False
                       and attempt.model_viewed_at is None)
    return {
        "subject": code, "subject_name": subj.name if subj else code, "topic": item.title if item else "", "outcome": outcome,
        "question": q.question_text, "marks": q.marks, "directive_verb": q.directive_verb,
        "origin": ORIGIN_LABELS.get(q.historical_or_generated, q.historical_or_generated),
        "options": q.options if q.question_type == "mcq" or (q.answer or {}).get("type") == "mcq" else None,
        "stimulus": stim_text, "stimulus_attribution": attribution,
        "kind": p.get("kind"), "skipped": bool(attempt.skipped), "attempt_number": attempt.attempt_number,
        "response": attempt.response_text, "working": working, "previous_attempt": previous,
        "mark": float(attempt.mark_awarded), "max": float(attempt.mark_possible), "method": method,
        "method_label": METHOD_LABELS.get(method, method) + (f". {p['label']}" if p.get("label") else ""),
        "feedback": feedback, "why_lost": fbrow.why_lost if fbrow else None,
        "correct_answer": correct, "worked_solution": [str(s) for s in worked],
        "model_answer": p.get("model_answer") or q.model_answer, "model_answer_source": p.get("model_answer_source")
        or ("Written for this question by HSC Companion" if q.model_answer else None),
        "criteria": criteria, "criteria_official": official,
        "guidance": p.get("guidance") or sol.get("guidance") or [],
        "evidence": _legal_evidence(db, q, p) if code == "LEGAL" else [],
        "solution_hidden": solution_hidden,
    }


def _same_context(attempt: Attempt):
    """Attempts at the same question in the same place (the same session slot, or practice)."""
    if attempt.session_question_id:
        return Attempt.session_question_id == attempt.session_question_id
    return Attempt.session_question_id.is_(None)


def _legal_evidence(db: Session, q: Question, payload: dict) -> list[dict]:
    """The verified evidence-bank items the feedback was grounded in (current bank if absent)."""
    if payload.get("evidence") is not None:
        return list(payload["evidence"])
    from app.services.assessment.legal import evidence_for

    return evidence_for(db, q)


def reference(db: Session, attempt: Attempt, ctx: dict | None = None) -> dict:
    """The material shown fully expanded when no AI provider can answer: worked solution or
    model answer, criteria and the feedback's key explanations."""
    ctx = ctx or grounding(db, attempt)
    fb = ctx["feedback"]
    is_mcq = ctx["options"] is not None
    hidden = bool(ctx.get("solution_hidden"))
    return {
        "subject": ctx["subject"], "kind": ctx["kind"], "options": ctx["options"], "solution_hidden": hidden,
        "correct_answer": ctx["correct_answer"] if ctx["subject"] == "MATHS" and not is_mcq and not hidden else None,  # LaTeX
        "mcq_answer": (fb.get("correct_answer") or ctx["correct_answer"]) if is_mcq else None,  # option text
        "worked_solution": [] if hidden else ctx["worked_solution"], "explanation": fb.get("explanation"), "concept": fb.get("concept"),
        "divergence": fb.get("divergence"), "model_answer": ctx["model_answer"], "model_answer_source": ctx["model_answer_source"],
        "criteria": ctx["criteria"], "criteria_official": ctx["criteria_official"], "criteria_judgements": fb.get("criteria") or [],
        "guidance": ctx["guidance"], "next_level": fb.get("next_level"), "improvements": fb.get("improvements") or [],
        "why_lost": ctx["why_lost"],
    }


# ------------------------------------------------------------------- thread ---
def thread(db: Session, attempt_id: int) -> list[FeedbackQuestion]:
    return list(db.scalars(select(FeedbackQuestion).where(FeedbackQuestion.attempt_id == attempt_id).order_by(FeedbackQuestion.id)))


def turns_used(rows: list[FeedbackQuestion]) -> int:
    return sum(1 for r in rows if r.status != FAILED)


def max_turns(db: Session) -> int:
    try:
        return max(1, int(st.get(db, "followup_max_turns") or 20))
    except (TypeError, ValueError):
        return 20


def history(rows: list[FeedbackQuestion], before: FeedbackQuestion | None = None) -> list[dict]:
    """Earlier answered turns, oldest first, as sent to the model."""
    out = []
    for r in rows:
        if before is not None and r.id >= before.id:
            break
        if r.status == ANSWERED and r.answer:
            out.append({"question": r.question_text, "answer": r.answer.get("answer", ""), "steps": r.answer.get("steps") or [],
                        "example": r.answer.get("example") or ""})
    return out


def _clean_question(text: str | None, chip: str | None) -> tuple[str, str | None]:
    chip = (chip or "").strip() or None
    if chip is not None and chip not in CHIP_LABELS:
        raise FollowUpError("Unknown quick question.")
    text = re.sub(r"[ \t]+", " ", (text or "").replace("\r\n", "\n")).strip()
    if chip:
        text = CHIP_LABELS[chip]  # a chip asks exactly its own question
    if not text:
        raise FollowUpError("Type your question about the feedback first.")
    if len(text) > MAX_QUESTION_CHARS:
        raise FollowUpError(f"Please keep your question under {MAX_QUESTION_CHARS} characters.")
    return text, chip


def safe_page(page_url: str | None) -> str | None:
    if page_url and page_url.startswith("/") and not page_url.startswith("//") and "\\" not in page_url and len(page_url) <= 300:
        return page_url
    return None


def ask(db: Session, attempt: Attempt | None, text: str | None, chip: str | None = None, page_url: str | None = None) -> FeedbackQuestion:
    """Store a new question in the attempt's thread and answer it (or save it for the teacher
    when no AI provider is configured)."""
    if attempt is None or attempt.feedback is None:
        raise FollowUpError("There is no feedback to ask about yet.", 404)
    text, chip = _clean_question(text, chip)
    rows = thread(db, attempt.id)
    limit = max_turns(db)
    if turns_used(rows) >= limit:
        raise FollowUpError(f"You have asked {limit} questions about this feedback, which is the limit for one attempt. "
                            "Save anything still unclear for your teacher, or try the question again.", 409)
    if len(rows) >= MAX_ROWS_PER_ATTEMPT:
        raise FollowUpError("This thread is full. Save anything still unclear for your teacher.", 409)
    row = FeedbackQuestion(attempt_id=attempt.id, question_id=attempt.question_id, turn=len(rows) + 1, question_text=text, chip=chip,
                           status=ANSWERED, page_url=safe_page(page_url))
    db.add(row)
    db.flush()
    _answer(db, attempt, row, rows)
    return row


def retry(db: Session, row: FeedbackQuestion) -> FeedbackQuestion:
    """Ask again a question that failed, or that was saved while offline (now that an AI
    provider is available)."""
    if row.status == ANSWERED:
        return row
    rows = thread(db, row.attempt_id)
    if row.status == FAILED and turns_used(rows) >= max_turns(db):
        raise FollowUpError("This thread has reached its question limit. Save the question for your teacher instead.", 409)
    _answer(db, row.attempt, row, [r for r in rows if r.id < row.id], retrying=True)
    return row


def _answer(db: Session, attempt: Attempt, row: FeedbackQuestion, earlier: list[FeedbackQuestion], retrying: bool = False) -> None:
    provider = get_provider(st.all_settings(db))
    row.provider = provider.name
    row.model = getattr(provider, "model", None)
    if not provider.generative:
        if retrying and row.status == OFFLINE:
            return  # still offline: nothing changes
        row.status, row.answer, row.error = OFFLINE, None, None
        row.for_teacher = True
        db.flush()
        return
    ctx = grounding(db, attempt)
    user = prompts_followup.followup(ctx, history(earlier), row.question_text, row.chip)
    images = _images_for(db, attempt, provider, ctx)
    try:
        result = provider.complete_json(prompts_followup.SYSTEM, user, FollowUpAnswer, images=images or None)
    except (AIError, AIUnavailable) as exc:
        log.warning("Follow-up answer failed: %s", exc)
        if row.status != OFFLINE:  # a question saved offline stays saved; only a new one becomes "failed"
            row.status = FAILED
        row.error = _friendly_error(exc)
        db.flush()
        return
    answer = result.model_dump()
    answer["checks"] = honesty_checks(ctx, answer, row.question_text, history(earlier))
    row.status, row.answer, row.error = ANSWERED, answer, None
    row.answered_at = utcnow()
    db.flush()


def _images_for(db: Session, attempt: Attempt, provider, ctx: dict) -> list:
    """Photos of handwritten working go with the question to providers that read images."""
    if ctx["subject"] != "MATHS" or not getattr(provider, "vision", False):
        return []
    try:
        from app.services import working_photos as wp

        return wp.images(wp.for_attempt(db, attempt.id))
    except Exception as exc:  # a missing file must not stop the explanation
        log.warning("Could not attach working photos to a follow-up question: %s", exc)
        return []


def _friendly_error(exc: Exception) -> str:
    msg = str(exc)
    if "declined" in msg.lower():
        return "The AI declined to answer this question. Try rewording it, or save it for your teacher."
    if "validation" in msg.lower():
        return "The AI's reply could not be used (it was not in the expected format). Ask again, or save it for your teacher."
    return f"The AI could not answer just now ({msg}). Ask again, or save it for your teacher."


# ----------------------------------------------------------- honesty checks ---
_QUOTE = re.compile(r"[\"“”]([^\"“”]{3,400})[\"“”]")


def _norm(text: str) -> str:
    text = (text or "").lower().replace("’", "'").replace("‘", "'").replace("—", "-").replace("–", "-")
    return re.sub(r"[^a-z0-9']+", " ", text).strip()


def unverified_quotes(text: str, sources: list[str]) -> list[str]:
    """Quotations (4+ words in double quotation marks) that do not appear in any grounding source."""
    haystack = " " + " ".join(_norm(s) for s in sources if s) + " "
    out = []
    for m in _QUOTE.finditer(text or ""):
        quote = m.group(1).strip()
        n = _norm(quote)
        if len(n.split()) < 4:
            continue
        if f" {n} " not in haystack and quote not in out:
            out.append(quote)
    return out


def honesty_checks(ctx: dict, answer: dict, question: str, hist: list[dict]) -> dict:
    """Flag quotations and legal authorities in the answer that are not in the grounding
    material (shown as cautions under the answer)."""
    body = "\n".join([answer.get("answer", ""), *answer.get("steps", [])])
    fb = ctx.get("feedback") or {}
    sources = [ctx.get("question"), ctx.get("stimulus"), ctx.get("response"), ctx.get("working"), ctx.get("model_answer"),
               ctx.get("criteria"), ctx.get("why_lost"), ctx.get("previous_attempt"), question,
               " ".join(ctx.get("worked_solution") or []), " ".join(ctx.get("guidance") or []), _flatten(fb),
               " ".join(h["question"] + " " + h["answer"] for h in hist)]
    checks: dict = {}
    if ctx.get("subject") in ("ENGLISH", "LEGAL"):
        quotes = unverified_quotes(body, [s for s in sources if s])
        if quotes:
            checks["unverified_quotes"] = quotes
    if ctx.get("subject") == "LEGAL":
        from app.services.assessment.legal import unverified_citations

        grounded = " ".join(s for s in sources if s).lower()
        cited = unverified_citations(body + "\n" + answer.get("example", ""), ctx.get("evidence") or [])
        refs = [c for c in cited if re.sub(r"\s*\(.*?\)\s*$", "", c).lower() not in grounded]
        if refs:
            checks["unverified_references"] = refs
    return checks


def _flatten(value) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(v) for v in value)
    return str(value) if value is not None else ""


# ------------------------------------------------------- teacher questions ---
def save_for_teacher(db: Session, row: FeedbackQuestion) -> FeedbackQuestion:
    row.for_teacher = True
    row.teacher_resolved = False
    row.resolved_at = None
    db.flush()
    return row


def resolve_teacher_question(db: Session, row: FeedbackQuestion) -> FeedbackQuestion:
    row.teacher_resolved = True
    row.resolved_at = utcnow()
    db.flush()
    return row


def teacher_questions(db: Session, include_resolved: bool = False, limit: int = 200) -> list[dict]:
    stmt = select(FeedbackQuestion).where(FeedbackQuestion.for_teacher.is_(True))
    if not include_resolved:
        stmt = stmt.where(FeedbackQuestion.teacher_resolved.is_(False))
    rows = db.scalars(stmt.order_by(FeedbackQuestion.created_at.desc(), FeedbackQuestion.id.desc()).limit(limit)).all()
    codes = {s.id: s.code for s in db.scalars(select(Subject))}
    out = []
    for r in rows:
        q = r.question
        out.append({"id": r.id, "text": r.question_text, "created_at": r.created_at, "subject": codes.get(q.subject_id, ""),
                    "question_id": r.question_id, "question_excerpt": _excerpt(q.question_text), "marks": q.marks,
                    "mark": r.attempt.mark_awarded, "max": r.attempt.mark_possible, "page_url": r.page_url or f"/questions/{r.question_id}",
                    "answered_by_ai": r.status == ANSWERED, "resolved": r.teacher_resolved})
    return out


def teacher_question_count(db: Session) -> int:
    return db.scalar(select(func.count(FeedbackQuestion.id)).where(FeedbackQuestion.for_teacher.is_(True),
                                                                    FeedbackQuestion.teacher_resolved.is_(False))) or 0


def _excerpt(text: str, n: int = 110) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


# --------------------------------------------------------------- page view ---
def view(db: Session, attempt: Attempt) -> dict:
    """Everything ``_feedback_followup.html`` needs for one attempt."""
    rows = thread(db, attempt.id)
    used = turns_used(rows)
    limit = max_turns(db)
    provider = get_provider(st.all_settings(db))
    full_marks = attempt.mark_awarded >= attempt.mark_possible and not attempt.skipped
    chips = [(k, label) for k, label in CHIPS if not (full_marks and k == "first_wrong")]
    earlier = []
    if attempt.attempt_number > 1:
        prev_ids = list(db.scalars(select(Attempt.id).where(Attempt.question_id == attempt.question_id, _same_context(attempt),
                                                             Attempt.attempt_number < attempt.attempt_number)))
        if prev_ids:
            prev_rows = db.scalars(select(FeedbackQuestion).where(FeedbackQuestion.attempt_id.in_(prev_ids))
                                   .order_by(FeedbackQuestion.id)).all()
            earlier = [r for r in prev_rows if r.status != FAILED]
    return {
        "attempt": attempt, "subject": subject_code(db, attempt.question), "rows": rows, "used": used, "max": limit, "remaining": max(0, limit - used), "ai": provider.generative,
        "provider_name": provider.name, "chips": chips, "reference": None if provider.generative else reference(db, attempt),
        "earlier": earlier, "teacher_count": sum(1 for r in rows if r.for_teacher and not r.teacher_resolved),
    }
