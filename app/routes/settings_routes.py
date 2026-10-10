from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import config
from app.db import get_db
from app.routes.common import render
from app.services import backup
from app.services import settings as st

router = APIRouter()


@router.get("/settings")
def settings_page(request: Request, saved: int = 0, restored: str = "", db: Session = Depends(get_db)):
    from app.services import plan

    from app.ai.factory import status as ai_status

    s = st.all_settings(db)
    return render(request, "settings.html", s=s, ai=ai_status(s), saved=saved, restored=restored, legal_items=plan.items(db, "LEGAL"),
                  backups=sorted(config.backups_dir.glob("*.zip"), reverse=True)[:5], data_dir=config.data_dir)


@router.post("/settings")
async def settings_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    s = st.all_settings(db)
    st.set_(db, "student_name", form.get("student_name") or s["student_name"])
    st.set_(db, "timezone", form.get("timezone") or "Australia/Sydney")
    from app.services import clock

    clock.set_timezone(st.get(db, "timezone"))
    for key in ("target_minutes", "budget_min_minutes", "budget_max_minutes", "holiday_target_minutes", "light_target_minutes"):
        if form.get(key):
            st.set_(db, key, int(form[key]))
    st.set_(db, "weekdays", sorted(int(d) for d in form.getlist("weekdays")) or [0, 1, 2, 3, 4])
    st.set_(db, "mode", form.get("mode", "auto"))
    for key in ("difficulty_behaviour", "revision_intensity", "feedback_depth"):
        st.set_(db, key, form.get(key, s[key]))
    for key in ("year12_start_date", "hsc_start_date"):
        if form.get(key):
            st.set_(db, key, form[key])
    st.set_(db, "enrichment_enabled", bool(form.get("enrichment_enabled")))
    st.set_(db, "ask_confidence", bool(form.get("ask_confidence")))
    st.set_(db, "show_why_these_questions", bool(form.get("show_why_these_questions")))
    st.set_(db, "source_preferences", {k: bool(form.get(k)) for k in ("allow_trial", "allow_generated", "allow_adapted")})
    st.set_(db, "english_unseen_share", float(form.get("english_unseen_share") or 0.8))
    weights = {k: float(form.get(f"w_{k}") or 0) for k in st.DEFAULTS["selection_weights"]}
    if sum(weights.values()) > 0:
        st.set_(db, "selection_weights", weights)
    mix = {k: float(form.get(f"mix_{k}") or 0) for k in ("learning", "recent", "older")}
    if abs(sum(mix.values()) - 1) < 0.05:
        st.set_(db, "maths_mix", mix)
    if form.get("ai_provider_override") is not None:
        st.set_(db, "ai_provider_override", form.get("ai_provider_override") or None)
        st.set_(db, "ai_model_override", form.get("ai_model_override") or None)
        if form.get("ai_effort") in ("medium", "high", "xhigh"):
            st.set_(db, "ai_effort", form.get("ai_effort"))
    raw = (form.get("holiday_ranges") or "").strip()
    ranges = []
    for line in raw.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[0] and parts[1]:
            ranges.append({"start": parts[0], "end": parts[1], "label": parts[2] if len(parts) > 2 else ""})
    st.set_(db, "holiday_ranges", ranges)
    db.commit()
    return RedirectResponse("/settings?saved=1", status_code=303)


@router.get("/backup/export")
def export_backup(db: Session = Depends(get_db)):
    path = backup.create_backup(settings=st.all_settings(db))
    return FileResponse(path, filename=path.name, media_type="application/zip")


@router.post("/backup/import")
async def import_backup(file: UploadFile = File(...)):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "restore.zip"
        p.write_bytes(await file.read())
        safety = backup.restore_backup(p)
    return RedirectResponse(f"/settings?restored={safety.name if safety else 'ok'}", status_code=303)
