"""Dashboard (owner: analytics)."""
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
