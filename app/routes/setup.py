"""First-run wizard (owner: platform)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PrescribedText
from app.routes.common import render
from app.services import clock, plan
from app.services import settings as st

router = APIRouter()


@router.get("/setup")
def setup_form(request: Request, db: Session = Depends(get_db)):
    return render(request, "setup.html", s=st.all_settings(db), today=clock.today(st.get(db, "timezone")),
                  maths_items=[i for i in plan.items(db, "MATHS") if not i.is_assumed_knowledge],
                  english_items=plan.items(db, "ENGLISH"), texts=db.execute(select(PrescribedText)).scalars().all())


@router.post("/setup")
async def setup_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    def num(key: str, default: int) -> int:
        try:
            return int(form.get(key) or default)
        except ValueError:
            return default

    st.set_(db, "student_name", (form.get("student_name") or "").strip() or "Student")
    st.set_(db, "hsc_year", num("hsc_year", 2027))
    st.set_(db, "timezone", (form.get("timezone") or "").strip() or "Australia/Sydney")
    clock.set_timezone(st.get(db, "timezone"))
    st.set_(db, "target_minutes", max(20, min(180, num("target_minutes", 90))))
    for key in ("year12_start_date", "hsc_start_date"):
        if form.get(key):
            st.set_(db, key, form[key])
    if form.get("maths_current"):
        plan.start_from(db, int(form["maths_current"]))
    for it in plan.items(db, "ENGLISH"):
        choice = form.get(f"english_{it.id}")
        if choice in ("LEARNED", "LEARNING", "LOCKED") and it.code != "EN-UNSEEN":
            plan.set_status(db, it.id, choice)
    if not st.get(db, "setup_completed_at"):
        st.set_(db, "setup_completed_at", clock.today().isoformat())
    st.set_(db, "setup_complete", True)
    db.commit()
    return RedirectResponse("/", status_code=303)
