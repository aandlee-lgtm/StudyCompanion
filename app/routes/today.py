from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.marking import maths as maths_marker
from app.models import Attempt, DailySession, LearningPlanItem, Question, SessionQuestion
from app.routes.common import render
from app.services import analytics, assessment, clock, sessions
from app.services import settings as st

router = APIRouter()
WORKING_SEP = "\n<<WORKING>>\n"


def _split_draft(text: str | None) -> tuple[str, str]:
    if not text:
        return "", ""
    if WORKING_SEP in text:
        a, w = text.split(WORKING_SEP, 1)
        return a, w
    return text, ""


@router.get("/today")
def today(request: Request, db: Session = Depends(get_db)):
    sess = sessions.get_or_create_today(db)
    db.commit()
    if sess is None:
        return render(request, "today_none.html", today=clock.today(st.get(db, "timezone")))
    return RedirectResponse(f"/session/{sess.id}", status_code=303)


@router.post("/today/extra")
def today_extra(db: Session = Depends(get_db), mode: str = Form("normal")):
    sess = sessions.create_extra_today(db, mode)
    db.commit()
    return RedirectResponse(f"/session/{sess.id}", status_code=303)


@router.get("/session/{sid}")
def session_view(sid: int, request: Request, db: Session = Depends(get_db)):
    sess = db.get(DailySession, sid)
    if sess is None:
        raise ValueError("That session does not exist.")
    if not sess.questions and sess.status in ("missed", "skipped"):
        return RedirectResponse("/", status_code=303)
    firsts = sessions.first_attempts(db, sess)
    answered = any(q.status in ("submitted", "skipped") for q in sess.questions)
    return render(request, "session.html", s=sess, p=sessions.progress(sess), elapsed=sessions.elapsed(sess), firsts=firsts,
                  can_rebuild=not answered, show_why=st.get(db, "show_why_these_questions"))


@router.post("/session/{sid}/timer")
def session_timer(sid: int, action: str = Form(...), db: Session = Depends(get_db)):
    sess = db.get(DailySession, sid)
    (sessions.start_timer if action == "start" else sessions.pause_timer)(db, sess)
    db.commit()
    return RedirectResponse(f"/session/{sid}", status_code=303)


@router.post("/session/{sid}/mode")
def session_mode(sid: int, mode: str = Form(...), db: Session = Depends(get_db)):
    sess = db.get(DailySession, sid)
    sessions.rebuild(db, sess, mode)
    db.commit()
    return RedirectResponse(f"/session/{sid}", status_code=303)


def _sq(db: Session, sid: int, pos: int) -> SessionQuestion:
    sq = db.execute(select(SessionQuestion).where(SessionQuestion.session_id == sid, SessionQuestion.position == pos)).scalar_one_or_none()
    if sq is None:
        raise ValueError("That question is not part of this session.")
    return sq


def _attempts(db: Session, q: Question, sq: SessionQuestion | None) -> list[Attempt]:
    stmt = select(Attempt).where(Attempt.question_id == q.id)
    stmt = stmt.where(Attempt.session_question_id == sq.id) if sq else stmt.where(Attempt.session_question_id.is_(None))
    return list(db.execute(stmt.order_by(Attempt.attempt_number)).scalars())


def question_context(db: Session, q: Question, sq: SessionQuestion | None, retry: bool) -> dict:
    attempts = _attempts(db, q, sq)
    latest = attempts[-1] if attempts else None
    item = db.get(LearningPlanItem, q.plan_item_id) if q.plan_item_id else None
    mapping = q.mappings[-1] if q.mappings else None
    answer, working = _split_draft(sq.draft_text if sq else None)
    if retry and latest and not answer:
        answer = latest.response_text
    code = assessment.subject_code(db, q)
    kind = "mcq" if q.question_type == "mcq" else ("maths" if code == "MATHS" else "written")
    return {"q": q, "sq": sq, "attempts": attempts, "latest": latest, "item": item, "mapping": mapping, "code": code, "kind": kind,
            "show_form": latest is None or retry, "draft_answer": answer, "draft_working": working,
            "reading": q.stimulus.reading_set() if q.stimulus else [], "ask_confidence": st.get(db, "ask_confidence"),
            "image": ("/media/" + q.question_image.split("/")[-1]) if q.question_image else None}


@router.get("/session/{sid}/q/{pos}")
def question_page(sid: int, pos: int, request: Request, retry: int = 0, db: Session = Depends(get_db)):
    sess = db.get(DailySession, sid)
    sq = _sq(db, sid, pos)
    if sess.timer_started_at is None and sess.status != "completed":
        sessions.start_timer(db, sess)
        db.commit()
    ctx = question_context(db, sq.question, sq, bool(retry))
    return render(request, "question.html", s=sess, total=len(sess.questions), pos=pos, base=f"/session/{sid}/q/{pos}", **ctx)


@router.post("/session/{sid}/q/{pos}/draft")
def save_draft(sid: int, pos: int, text: str = Form(""), time_seconds: int = Form(0), db: Session = Depends(get_db)):
    sq = _sq(db, sid, pos)
    sessions.save_draft(db, sq, text, time_seconds)
    db.commit()
    return JSONResponse({"ok": True})


def _do_submit(db: Session, q: Question, sq: SessionQuestion | None, answer: str, working: str, confidence: str, time_seconds: int, skipped: bool):
    if not skipped and not (answer or "").strip():
        raise ValueError("Write an answer first, or choose 'Show answer / skip'.")
    assessment.submit(db, q, answer, sq=sq, working=working or None, confidence=confidence or None, time_seconds=time_seconds, skipped=skipped)
    if sq is not None:
        sq.draft_text = None
        sessions.maybe_complete(db, sq.session)


@router.post("/session/{sid}/q/{pos}/submit")
def submit(sid: int, pos: int, answer: str = Form(""), working: str = Form(""), confidence: str = Form(""), time_seconds: int = Form(0),
           db: Session = Depends(get_db)):
    sq = _sq(db, sid, pos)
    _do_submit(db, sq.question, sq, answer, working, confidence, time_seconds, False)
    db.commit()
    return RedirectResponse(f"/session/{sid}/q/{pos}#feedback", status_code=303)


@router.post("/session/{sid}/q/{pos}/skip")
def skip(sid: int, pos: int, time_seconds: int = Form(0), db: Session = Depends(get_db)):
    sq = _sq(db, sid, pos)
    _do_submit(db, sq.question, sq, "", "", "", time_seconds, True)
    db.commit()
    return RedirectResponse(f"/session/{sid}/q/{pos}#feedback", status_code=303)


@router.post("/attempt/{aid}/why")
def why(aid: int, db: Session = Depends(get_db)):
    a = db.get(Attempt, aid)
    text = assessment.why_lost(db, a)
    db.commit()
    return JSONResponse({"explanation": text})


@router.post("/attempt/{aid}/self-mark")
def self_mark(aid: int, mark: float = Form(...), back: str = Form("/"), db: Session = Depends(get_db)):
    a = db.get(Attempt, aid)
    assessment.apply_self_mark(db, a, mark)
    db.commit()
    return RedirectResponse(back, status_code=303)


@router.get("/session/{sid}/summary")
def summary(sid: int, request: Request, db: Session = Depends(get_db)):
    sess = db.get(DailySession, sid)
    if sess.status != "completed":
        sessions.maybe_complete(db, sess)
        db.commit()
    summ = sess.summary or analytics.session_summary(db, sess)
    weekdays = st.get(db, "weekdays") or [0, 1, 2, 3, 4]
    week = analytics.weekly_review(db, sess.session_date) if sess.session_date.weekday() == max(weekdays) else None
    return render(request, "summary.html", s=sess, summary=summ, week=week)


@router.post("/missed/{sid}/{action}")
def missed(sid: int, action: str, db: Session = Depends(get_db)):
    sess = db.get(DailySession, sid)
    if action == "resume":
        sessions.resume_missed(db, sess)
        db.commit()
        return RedirectResponse(f"/session/{sid}", status_code=303)
    if action == "revision":
        sessions.move_revision_forward(db, sess)
    else:
        sessions.skip_missed(db, sess)
    db.commit()
    return RedirectResponse("/", status_code=303)


# ---------------------------------------------------------------- practice ---
@router.get("/practice/{qid}")
def practice(qid: int, request: Request, retry: int = 0, db: Session = Depends(get_db)):
    q = db.get(Question, qid)
    if q is None or not q.approved:
        raise ValueError("That question is not available for practice.")
    ctx = question_context(db, q, None, bool(retry))
    return render(request, "question.html", s=None, total=None, pos=None, base=f"/practice/{qid}", **ctx)


@router.post("/practice/{qid}/submit")
def practice_submit(qid: int, answer: str = Form(""), working: str = Form(""), confidence: str = Form(""), time_seconds: int = Form(0),
                    db: Session = Depends(get_db)):
    _do_submit(db, db.get(Question, qid), None, answer, working, confidence, time_seconds, False)
    db.commit()
    return RedirectResponse(f"/practice/{qid}#feedback", status_code=303)


@router.post("/practice/{qid}/skip")
def practice_skip(qid: int, db: Session = Depends(get_db)):
    _do_submit(db, db.get(Question, qid), None, "", "", "", 0, True)
    db.commit()
    return RedirectResponse(f"/practice/{qid}#feedback", status_code=303)


@router.post("/api/math-preview")
def math_preview(text: str = Form("")):
    import sympy as sp

    raw = text.replace("+ C", "").replace("+C", "").replace("+ c", "")
    try:
        return JSONResponse({"ok": True, "latex": sp.latex(maths_marker.parse(raw))})
    except Exception:
        return JSONResponse({"ok": False, "message": "Keep typing… (e.g. 3x^2 - 2, sqrt(2)/2, e^(2x), 2pi/3)"})
