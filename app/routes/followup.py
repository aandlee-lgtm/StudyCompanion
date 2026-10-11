"""'Ask about this feedback' and 'Questions for my teacher' (owner: followup).

JSON for the page script (requests sent with ``X-Requested-With: fetch``) and plain form posts
with a redirect for browsers without JavaScript. Cross-site posts are refused by
``app.security.LocalOnlyMiddleware`` like every other state-changing request."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session, object_session

from app.db import SessionLocal, get_db
from app.models import Attempt
from app.models.followup import FeedbackQuestion
from app.routes.common import templates
from app.services import followup as fu

router = APIRouter()


def _wants_json(request: Request) -> bool:
    return request.headers.get("x-requested-with") == "fetch" or "application/json" in request.headers.get("accept", "")


def _safe_back(back: str | None, fallback: str = "/") -> str:
    return fu._safe_page(back) or fallback


def _turn_html(db: Session, row: FeedbackQuestion) -> str:
    from app.ai.factory import get_provider
    from app.services import settings as st

    return templates.get_template("_followup_turn.html").render(r=row, fu_ai=get_provider(st.all_settings(db)).generative)


def _row_json(db: Session, row: FeedbackQuestion) -> dict:
    rows = fu.thread(db, row.attempt_id)
    limit = fu.max_turns(db)
    used = fu.turns_used(rows)
    out = {"ok": row.status != "failed", "id": row.id, "status": row.status, "question": row.question_text, "answer": row.answer,
           "error": row.error, "for_teacher": row.for_teacher, "used": used, "max": limit, "remaining": max(0, limit - used),
           "html": _turn_html(db, row)}
    if row.status == "offline":
        out["message"] = ("Free questions need Claude (set it up in Settings → AI). Your question was saved to "
                          "'Questions for my teacher' on the Error journal page so you can ask it in class.")
    return out


def _error(request: Request, exc: fu.FollowUpError, back: str):
    if _wants_json(request):
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=exc.status)
    from app.routes.common import render_error

    return render_error(request, str(exc), status_code=exc.status)


@router.get("/attempt/{aid}/followup")
def get_thread(aid: int, db: Session = Depends(get_db)):
    attempt = db.get(Attempt, aid)
    if attempt is None:
        return JSONResponse({"ok": False, "error": "Unknown attempt."}, status_code=404)
    rows = fu.thread(db, aid)
    limit = fu.max_turns(db)
    return JSONResponse({"ok": True, "max": limit, "used": fu.turns_used(rows), "turns": [
        {"id": r.id, "turn": r.turn, "question": r.question_text, "chip": r.chip, "status": r.status, "answer": r.answer,
         "error": r.error, "for_teacher": r.for_teacher, "created_at": r.created_at.isoformat()} for r in rows]})


@router.post("/attempt/{aid}/followup")
def ask(aid: int, request: Request, question: str = Form(""), chip: str = Form(""), back: str = Form(""),
        db: Session = Depends(get_db)):
    attempt = db.get(Attempt, aid)
    back = _safe_back(back, f"/questions/{attempt.question_id}" if attempt else "/")
    try:
        row = fu.ask(db, attempt, question, chip or None, page_url=back)
    except fu.FollowUpError as exc:
        db.rollback()
        return _error(request, exc, back)
    db.commit()
    if _wants_json(request):
        return JSONResponse(_row_json(db, row))
    return RedirectResponse(f"{back}#fu-{row.id}", status_code=303)


@router.post("/followup/{fid}/retry")
def retry(fid: int, request: Request, back: str = Form(""), db: Session = Depends(get_db)):
    row = db.get(FeedbackQuestion, fid)
    if row is None:
        return _error(request, fu.FollowUpError("Unknown question.", 404), "/")
    back = _safe_back(back, row.page_url or "/")
    try:
        fu.retry(db, row)
    except fu.FollowUpError as exc:
        db.rollback()
        return _error(request, exc, back)
    db.commit()
    if _wants_json(request):
        return JSONResponse(_row_json(db, row))
    return RedirectResponse(f"{back}#fu-{row.id}", status_code=303)


@router.post("/followup/{fid}/teacher")
def save_for_teacher(fid: int, request: Request, back: str = Form(""), db: Session = Depends(get_db)):
    row = db.get(FeedbackQuestion, fid)
    if row is None:
        return _error(request, fu.FollowUpError("Unknown question.", 404), "/")
    fu.save_for_teacher(db, row)
    db.commit()
    if _wants_json(request):
        return JSONResponse(_row_json(db, row))
    return RedirectResponse(f"{_safe_back(back, row.page_url or '/errors')}#fu-{row.id}", status_code=303)


@router.post("/followup/{fid}/resolve")
def resolve(fid: int, request: Request, back: str = Form("/errors"), db: Session = Depends(get_db)):
    row = db.get(FeedbackQuestion, fid)
    if row is None:
        return _error(request, fu.FollowUpError("Unknown question.", 404), "/errors")
    fu.resolve_teacher_question(db, row)
    db.commit()
    if _wants_json(request):
        return JSONResponse({"ok": True, "id": row.id})
    return RedirectResponse(_safe_back(back, "/errors") + "#teacher-questions", status_code=303)


# ---- template helpers: the partials load their own data, so no other route has to change ----
def _followup_view(attempt: Attempt) -> dict | None:
    db = object_session(attempt)
    if db is not None:
        return fu.view(db, attempt)
    db = SessionLocal()
    try:
        return fu.view(db, db.get(Attempt, attempt.id))
    finally:
        db.close()


def _teacher_questions(include_resolved: bool = False) -> list[dict]:
    db = SessionLocal()
    try:
        return fu.teacher_questions(db, include_resolved=include_resolved)
    finally:
        db.close()


templates.env.globals.update(followup_view=_followup_view, followup_teacher_questions=_teacher_questions,
                             FOLLOWUP_MAX_CHARS=fu.MAX_QUESTION_CHARS)
