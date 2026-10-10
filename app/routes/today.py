"""Today / daily session routes (owner: selection)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attempt, DailySession, LearningPlanItem, Question, SessionQuestion
from app.routes.common import render
from app.services import analytics, assessment, clock, sessions
from app.services import settings as st

from app.routes.question_helpers import do_submit, get_sq, question_context

router = APIRouter()


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



@router.get("/session/{sid}/q/{pos}")
def question_page(sid: int, pos: int, request: Request, retry: int = 0, db: Session = Depends(get_db)):
    sess = db.get(DailySession, sid)
    sq = get_sq(db, sid, pos)
    if sess.timer_started_at is None and sess.status != "completed":
        sessions.start_timer(db, sess)
        db.commit()
    ctx = question_context(db, sq.question, sq, bool(retry))
    return render(request, "question.html", s=sess, total=len(sess.questions), pos=pos, base=f"/session/{sid}/q/{pos}", **ctx)


@router.post("/session/{sid}/q/{pos}/draft")
def save_draft(sid: int, pos: int, text: str = Form(""), time_seconds: int = Form(0), db: Session = Depends(get_db)):
    sq = get_sq(db, sid, pos)
    sessions.save_draft(db, sq, text, time_seconds)
    db.commit()
    return JSONResponse({"ok": True})



@router.post("/session/{sid}/q/{pos}/submit")
def submit(sid: int, pos: int, answer: str = Form(""), working: str = Form(""), confidence: str = Form(""), time_seconds: int = Form(0),
           db: Session = Depends(get_db)):
    sq = get_sq(db, sid, pos)
    do_submit(db, sq.question, sq, answer, working, confidence, time_seconds, False)
    db.commit()
    return RedirectResponse(f"/session/{sid}/q/{pos}#feedback", status_code=303)


@router.post("/session/{sid}/q/{pos}/skip")
def skip(sid: int, pos: int, time_seconds: int = Form(0), db: Session = Depends(get_db)):
    sq = get_sq(db, sid, pos)
    do_submit(db, sq.question, sq, "", "", "", time_seconds, True)
    db.commit()
    return RedirectResponse(f"/session/{sid}/q/{pos}#feedback", status_code=303)



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
