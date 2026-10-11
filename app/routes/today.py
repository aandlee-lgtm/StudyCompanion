"""Today / daily session routes (owner: selection)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Attempt, DailySession
from app.routes.common import render
from app.routes.question_helpers import do_submit, get_sq, question_context
from app.services import analytics, clock, sessions
from app.services import settings as st

router = APIRouter()


def _today(db: Session):
    return clock.today(st.get(db, "timezone"))


def _session_or_404(db: Session, sid: int) -> DailySession:
    sess = db.get(DailySession, sid)
    if sess is None:
        raise ValueError("That session does not exist.")
    return sess


def _wants_json(request: Request) -> bool:
    return request.headers.get("x-requested-with") == "fetch" or "application/json" in request.headers.get("accept", "")


@router.get("/today")
def today(request: Request, db: Session = Depends(get_db)):
    t = _today(db)
    sessions.record_missed(db, t)
    if sessions.get_session(db, t) is None and sessions.study_day(db, t):
        notice = sessions.missed_notice(db, t)
        if notice:  # decide about missed days BEFORE today's set is built (selection-10)
            db.commit()
            return render(request, "selection_missed.html", notice=notice, today=t, unfinished=sessions.unfinished(db, t))
    sess = sessions.get_or_create_today(db)
    db.commit()
    if sess is None:
        return render(request, "today_none.html", today=t)
    return RedirectResponse(f"/session/{sess.id}", status_code=303)


@router.post("/today/missed")
def today_missed(action: str = Form(...), sid: int = Form(0), db: Session = Depends(get_db)):
    t = _today(db)
    if action not in ("catch_up", "resume", "skip"):
        raise ValueError("Unknown choice for the missed sessions.")
    target = sessions.resolve_missed(db, t, action, sid or None)
    if target is None:
        target = sessions.get_or_create_today(db)
    db.commit()
    return RedirectResponse(f"/session/{target.id}" if target else "/", status_code=303)


@router.post("/today/extra")
def today_extra(db: Session = Depends(get_db), mode: str = Form("normal")):
    sess = sessions.create_extra_today(db, mode)
    db.commit()
    return RedirectResponse(f"/session/{sess.id}", status_code=303)


@router.get("/sessions")
def session_history(request: Request, db: Session = Depends(get_db)):
    t = _today(db)
    return render(request, "selection_history.html", rows=sessions.history(db), today=t,
                  unfinished=sessions.unfinished(db, t), notice=sessions.missed_notice(db, t), health=_bank_health(db, t))


def _bank_health(db: Session, t) -> dict | None:
    from app.selection.health import bank_health

    try:
        return bank_health(db, t)
    except Exception:  # a health card must never break the page (e.g. before setup)
        return None


@router.get("/api/selection/bank-health")
def bank_health_api(db: Session = Depends(get_db)):
    """Question bank health per subject, by the selection engine's own rules (selection-17)."""
    health = _bank_health(db, _today(db))
    return JSONResponse(health if health is not None else {"error": "Bank health is not available yet."},
                        status_code=200 if health is not None else 503)


@router.get("/session/{sid}")
def session_view(sid: int, request: Request, swapped: int = 0, db: Session = Depends(get_db)):
    sess = _session_or_404(db, sid)
    if not sess.questions and sess.status in ("missed", "skipped"):
        return RedirectResponse("/", status_code=303)
    t = _today(db)
    if sess.timer_started_at is not None:
        if sess.session_date < t:
            sessions.pause_timer(db, sess, "day_end")
        else:
            sessions.touch(db, sess)
        db.commit()
    firsts = sessions.first_attempts(db, sess)
    answered = any(q.status in ("submitted", "skipped") for q in sess.questions)
    return render(request, "session.html", s=sess, p=sessions.progress(sess), elapsed=sessions.elapsed(sess), firsts=firsts,
                  can_rebuild=not answered and sess.status not in ("completed", "closed"), show_why=st.get(db, "show_why_these_questions"),
                  is_past=sess.session_date < t, idle_minutes=st.get(db, "timer_idle_minutes") or 10,
                  swap_controls=sessions.swap_controls(db, sess), swaps=sessions.swaps_for(db, sess),
                  swap_notice=_swap_notice(db, sess, swapped))


@router.post("/session/{sid}/timer")
def session_timer(sid: int, request: Request, action: str = Form(...), reason: str = Form(""), db: Session = Depends(get_db)):
    sess = _session_or_404(db, sid)
    if action == "start":
        sessions.start_timer(db, sess)
        sess.pause_note = None
    else:
        sessions.pause_timer(db, sess, reason or None)
    db.commit()
    if _wants_json(request):
        return JSONResponse({"elapsed": sessions.elapsed(sess), "running": sess.timer_started_at is not None, "note": sess.pause_note})
    return RedirectResponse(f"/session/{sid}", status_code=303)


@router.post("/session/{sid}/heartbeat")
def session_heartbeat(sid: int, db: Session = Depends(get_db)):
    sess = _session_or_404(db, sid)
    if sess.session_date < _today(db):
        if sess.timer_started_at is not None:
            sessions.pause_timer(db, sess, "day_end")
        db.commit()
        return JSONResponse({"elapsed": sessions.elapsed(sess), "running": False, "note": sess.pause_note})
    out = sessions.heartbeat(db, sess)
    db.commit()
    return JSONResponse(out)


@router.post("/session/{sid}/close")
def session_close(sid: int, db: Session = Depends(get_db)):
    sess = _session_or_404(db, sid)
    sessions.close_session(db, sess)
    db.commit()
    return RedirectResponse("/sessions", status_code=303)


@router.post("/session/{sid}/mode")
def session_mode(sid: int, mode: str = Form(...), db: Session = Depends(get_db)):
    sess = _session_or_404(db, sid)
    sessions.rebuild(db, sess, mode)
    db.commit()
    return RedirectResponse(f"/session/{sid}", status_code=303)


@router.get("/session/{sid}/q/{pos}")
def question_page(sid: int, pos: int, request: Request, retry: int = 0, swapped: int = 0, db: Session = Depends(get_db)):
    sess = _session_or_404(db, sid)
    sq = get_sq(db, sid, pos)
    if sess.status not in ("completed", "closed") and sess.session_date >= _today(db):
        sessions.touch(db, sess)  # starts the timer on the first question, then counts activity
    bd = sq.score_breakdown or {}
    is_retry = bd.get("kind") == "retry"
    if is_retry and not sq.draft_text and sq.status == "pending" and bd.get("retry_of_attempt"):
        prev = db.get(Attempt, bd["retry_of_attempt"])
        if prev is not None and prev.response_text:
            sq.draft_text = prev.response_text  # a rewrite task starts from the earlier answer (spec 25)
    db.commit()
    ctx = question_context(db, sq.question, sq, bool(retry))
    swap = sessions.swap_controls(db, sess).get(sq.id)  # the _swap_control.html partial (v2-swap)
    return render(request, "question.html", s=sess, total=len(sess.questions), pos=pos, base=f"/session/{sid}/q/{pos}",
                  swap=swap, swap_notice=_swap_notice(db, sess, swapped), **ctx)


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
    sessions.touch(db, sq.session)
    do_submit(db, sq.question, sq, answer, working, confidence, time_seconds, False)
    db.commit()
    return RedirectResponse(f"/session/{sid}/q/{pos}#feedback", status_code=303)


@router.post("/session/{sid}/q/{pos}/skip")
def skip(sid: int, pos: int, time_seconds: int = Form(0), db: Session = Depends(get_db)):
    sq = get_sq(db, sid, pos)
    sessions.touch(db, sq.session)
    do_submit(db, sq.question, sq, "", "", "", time_seconds, True)
    db.commit()
    return RedirectResponse(f"/session/{sid}/q/{pos}#feedback", status_code=303)


@router.get("/session/{sid}/summary")
def summary(sid: int, request: Request, db: Session = Depends(get_db)):
    sess = _session_or_404(db, sid)
    if sess.status not in ("completed", "closed"):
        sessions.maybe_complete(db, sess)
        db.commit()
    summ = sess.summary or analytics.session_summary(db, sess)
    weekdays = st.get(db, "weekdays") or [0, 1, 2, 3, 4]
    week = analytics.weekly_review(db, sess.session_date) if sess.session_date.weekday() == max(weekdays) else None
    return render(request, "summary.html", s=sess, summary=summ, week=week)


@router.post("/missed/{sid}/{action}")
def missed(sid: str, action: str, db: Session = Depends(get_db)):
    """Dashboard buttons. ``sid`` may be 'all' (one decision for every recent missed day)."""
    t = _today(db)
    if sid == "all":
        target = sessions.resolve_missed(db, t, {"revision": "catch_up"}.get(action, action), None)
        db.commit()
        return RedirectResponse(f"/session/{target.id}" if target else "/", status_code=303)
    sess = _session_or_404(db, int(sid))
    if action == "resume":
        sessions.resume_missed(db, sess)
        db.commit()
        return RedirectResponse(f"/session/{sess.id}", status_code=303)
    if action in ("revision", "catch_up"):
        sessions.move_revision_forward(db, sess)
    else:
        sessions.skip_missed(db, sess)
    db.commit()
    return RedirectResponse("/", status_code=303)


# ------------------------------------------------------------------ swap (v2-swap) ---
def _swap_notice(db: Session, sess: DailySession, swap_id: int):
    """The swap just made (shown once after the redirect of the no-JS form)."""
    if not swap_id:
        return None
    from app.models import SessionSwap

    rec = db.get(SessionSwap, swap_id)
    return rec if rec is not None and rec.session_id == sess.id else None


def _swap_payload(sess: DailySession, rec, back: str, pos: int) -> dict:
    details = rec.details or {}
    to_pos = details.get("to_positions") or []
    if back == "question" and rec.outcome == "replaced" and to_pos:
        redirect = f"/session/{sess.id}/q/{to_pos[0]}?swapped={rec.id}"
    else:
        redirect = f"/session/{sess.id}?swapped={rec.id}#swap-note"
    rows = {x.position: x for x in sess.questions}
    questions = []
    for p in to_pos:
        x = rows.get(p)
        if x is None:
            continue
        q = x.question
        questions.append({"position": p, "question_id": q.id, "subject": x.subject_code, "marks": q.marks,
                          "minutes": round(float(q.estimated_minutes or 0), 1), "reason": x.reason,
                          "href": f"/session/{sess.id}/q/{p}"})
    p = sessions.progress(sess)
    return {"ok": True, "swap_id": rec.id, "outcome": rec.outcome, "reason": rec.reason, "message": rec.message,
            "from_positions": details.get("from_positions") or [], "positions": to_pos, "questions": questions,
            "locked_plan_item_id": rec.locked_plan_item_id, "expected_minutes": sess.expected_minutes,
            "remaining_minutes": p["remaining_minutes"], "total": p["n_total"], "redirect": redirect}


@router.post("/session/{sid}/q/{pos}/swap")
def swap_question(sid: int, pos: int, request: Request, reason: str = Form(""), lock: str = Form(""), back: str = Form("session"),
                  db: Session = Depends(get_db)):
    """Swap an unanswered question ("I haven't learnt this yet" / "give me a different one").
    JSON for the page script; a redirect with the result for the plain form (no JavaScript)."""
    wants_json = _wants_json(request)
    try:
        if reason not in ("not_learnt", "different"):
            raise ValueError("Choose why you want to swap this question: not learnt yet, or a different one.")
        sess = _session_or_404(db, sid)
        sq = get_sq(db, sid, pos)
        rec = sessions.swap_question(db, sess, sq, reason, lock=lock.lower() in ("1", "on", "true", "yes"))
    except ValueError as exc:
        db.rollback()
        if wants_json:
            status = 409 if isinstance(exc, sessions.SwapRefused) else 400
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=status)
        raise
    db.commit()
    db.refresh(sess)
    payload = _swap_payload(sess, rec, back if back in ("session", "question") else "session", pos)
    if wants_json:
        return JSONResponse(payload)
    return RedirectResponse(payload["redirect"], status_code=303)
