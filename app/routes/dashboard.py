from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LearningPlanItem, PrescribedText
from app.routes.common import render
from app.services import analytics, clock, plan
from app.services import settings as st

router = APIRouter()


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    d = analytics.dashboard(db)
    db.commit()
    return render(request, "dashboard.html", d=d, name=st.get(db, "student_name"), hour=datetime.now().hour, target=st.get(db, "target_minutes"))


@router.get("/setup")
def setup_form(request: Request, db: Session = Depends(get_db)):
    return render(request, "setup.html", s=st.all_settings(db), today=clock.today(st.get(db, "timezone")),
                  maths_items=[i for i in plan.items(db, "MATHS") if not i.is_assumed_knowledge],
                  english_items=plan.items(db, "ENGLISH"), texts=db.execute(select(PrescribedText)).scalars().all())


@router.post("/setup")
def setup_save(
    db: Session = Depends(get_db), student_name: str = Form(""), hsc_year: int = Form(2027), timezone: str = Form("Australia/Sydney"),
    target_minutes: int = Form(90), year12_start_date: str = Form(""), hsc_start_date: str = Form(""), maths_current: int = Form(0),
    english_current: int = Form(0),
):
    st.set_(db, "student_name", student_name.strip() or "Student")
    st.set_(db, "hsc_year", hsc_year)
    st.set_(db, "timezone", timezone.strip() or "Australia/Sydney")
    st.set_(db, "target_minutes", target_minutes)
    if year12_start_date:
        st.set_(db, "year12_start_date", year12_start_date)
    if hsc_start_date:
        st.set_(db, "hsc_start_date", hsc_start_date)
    if maths_current:
        plan.start_from(db, maths_current)
    if english_current:
        for it in plan.items(db, "ENGLISH"):
            if it.code in ("EN-UNSEEN", "EN-CRAFT"):
                continue
            plan.set_status(db, it.id, "LEARNING" if it.id == english_current else ("LOCKED" if it.status == "LOCKED" or it.status == "LEARNING" else it.status))
    st.set_(db, "setup_complete", True)
    db.commit()
    return RedirectResponse("/", status_code=303)
