from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.routes.common import render
from app.services import analytics, backup

router = APIRouter()


@router.get("/progress")
def progress(request: Request, window: str = "30", db: Session = Depends(get_db)):
    if window not in analytics.WINDOWS:
        window = "30"
    return render(request, "progress.html", r=analytics.progress_report(db, window), readiness=analytics.readiness(db))


@router.get("/progress/week")
def week(request: Request, db: Session = Depends(get_db)):
    return render(request, "week.html", w=analytics.weekly_review(db))


@router.get("/progress/month")
def month(request: Request, db: Session = Depends(get_db)):
    return render(request, "month.html", m=analytics.monthly_review(db))


@router.get("/export/attempts.csv")
def export_csv(db: Session = Depends(get_db)):
    return Response(backup.attempts_csv(db), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=hsc-companion-answers.csv"})
