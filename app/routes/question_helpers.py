"""Shared question-page helpers used by session and practice routes (owner: adaptive)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt, LearningPlanItem, PracticeDraft, Question, SessionQuestion
from app.models.common import utcnow
from app.services import assessment, clock, revision, sessions
from app.services import settings as st
from app.services.assessment import core
from app.services.assessment.written import criteria_ladder

WORKING_SEP = "\n<<WORKING>>\n"
RETRY_KINDS = ("written", "maths")


def split_draft(text: str | None) -> tuple[str, str]:
    if not text:
        return "", ""
    if WORKING_SEP in text:
        a, w = text.split(WORKING_SEP, 1)
        return a, w
    return text, ""


def get_sq(db: Session, sid: int, pos: int) -> SessionQuestion:
    sq = db.execute(select(SessionQuestion).where(SessionQuestion.session_id == sid, SessionQuestion.position == pos)).scalar_one_or_none()
    if sq is None:
        raise ValueError("That question is not part of this session.")
    return sq


def attempts_for(db: Session, q: Question, sq: SessionQuestion | None) -> list[Attempt]:
    """Attempts in this context (the session question, or today's practice sitting)."""
    today = clock.today(st.get(db, "timezone"))
    return core.classify(db, q, sq, today)["context"]


def practice_draft(db: Session, q: Question) -> PracticeDraft | None:
    return db.execute(select(PracticeDraft).where(PracticeDraft.question_id == q.id)).scalar_one_or_none()


def save_practice_draft(db: Session, q: Question, text: str, time_seconds: int | None = None) -> PracticeDraft:
    d = practice_draft(db, q)
    if d is None:
        d = PracticeDraft(question_id=q.id, text="", time_seconds=0)
        db.add(d)
    d.text = text or ""
    if time_seconds is not None:
        d.time_seconds = max(d.time_seconds or 0, int(time_seconds))
    d.updated_at = utcnow()
    db.flush()
    return d


def can_retry(a: Attempt | None) -> bool:
    """Try again is offered for written and maths answers that lost marks; never after a skip or an MCQ (answer shown)."""
    if a is None or a.skipped or a.feedback is None:
        return False
    p = a.feedback.payload or {}
    return p.get("kind") in RETRY_KINDS and a.mark_awarded < a.mark_possible and not p.get("pending_mark")


def role_label(a: Attempt) -> str:
    if a.skipped:
        return "skipped (answer shown)"
    role = a.evidence_role or ("first" if a.counts_for_mastery else "retry")
    text = {"first": "counted", "due_repeat": "counted (scheduled repeat)", "early_repeat": "counted",
            "retry": "retry", "rehearsal": "practice — not counted"}.get(role, role)
    if a.after_reveal and not a.counts_for_mastery:
        text += ", after seeing the answer"
    return text


def _photos(db: Session, a: Attempt | None) -> list[dict]:
    from app.services import working_photos

    return [working_photos.public(p) for p in working_photos.for_attempt(db, a.id)] if a is not None else []


def question_context(db: Session, q: Question, sq: SessionQuestion | None, retry: bool) -> dict:
    today = clock.today(st.get(db, "timezone"))
    cls = core.classify(db, q, sq, today)
    attempts = cls["context"]
    chain = cls["chain"]
    latest = attempts[-1] if attempts else None
    retry = bool(retry and can_retry(latest))
    item = db.get(LearningPlanItem, q.plan_item_id) if q.plan_item_id else None
    mapping = q.mappings[-1] if q.mappings else None
    draft_saved_at = None
    if sq is not None:
        answer, working = split_draft(sq.draft_text)
        draft_saved_at = sq.draft_saved_at
        spent = sq.time_spent_seconds
    else:
        d = practice_draft(db, q)
        answer, working = split_draft(d.text if d else None)
        draft_saved_at = d.updated_at if d else None
        spent = d.time_seconds if d else 0
    if retry and latest and not answer:
        answer = latest.response_text
        if latest.feedback and (latest.feedback.payload or {}).get("working") and not working:
            working = latest.feedback.payload["working"]
    code = assessment.subject_code(db, q)
    rebuild = revision.rebuild_ladder(db, q) if latest is None else None  # adaptive-19: worked example first
    kind = "mcq" if q.question_type == "mcq" else ("maths" if code == "MATHS" else "written")
    return {"q": q, "sq": sq, "attempts": attempts, "chain": chain, "latest": latest, "item": item, "mapping": mapping, "code": code,
            "kind": kind, "show_form": latest is None or retry, "retry": retry, "can_retry": can_retry(latest),
            "draft_answer": answer, "draft_working": working, "draft_saved_at": draft_saved_at, "spent_seconds": spent or 0,
            "next_evidence": cls, "role_label": role_label, "ladder": criteria_ladder(q),
            "reading": q.stimulus.reading_set() if q.stimulus else [], "ask_confidence": st.get(db, "ask_confidence"),
            "rebuild": rebuild,
            "submitted_photos": _photos(db, latest),
            "image": ("/media/" + q.question_image.split("/")[-1]) if q.question_image else None}


def do_submit(db: Session, q: Question, sq: SessionQuestion | None, answer: str, working: str, confidence: str, time_seconds: int, skipped: bool):
    if not skipped and not (answer or "").strip():
        raise ValueError("Write an answer first, or choose 'Show answer / skip'.")
    attempt = assessment.submit(db, q, answer, sq=sq, working=working or None, confidence=confidence or None, time_seconds=time_seconds,
                                skipped=skipped)
    from app.services import working_photos

    for photo in working_photos.pending_any(db, q.id):  # photos of working stay with this answer
        photo.attempt_id = attempt.id
    db.flush()
    if sq is not None:
        sq.draft_text = None
        sessions.maybe_complete(db, sq.session)
    else:
        d = practice_draft(db, q)
        if d is not None:
            db.delete(d)
            db.flush()
    return attempt
