"""Photos of handwritten working: upload, view, remove, and have the AI read them."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.ai.base import AIError, AIUnavailable
from app.ai.factory import get_provider
from app.db import get_db
from app.models import Question, WorkingPhoto
from app.services import settings as st
from app.services import working_photos as wp

router = APIRouter()


def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


def _listing(db: Session, question_id: int, sq_id: int | None) -> dict:
    return {"ok": True, "photos": [wp.public(p) for p in wp.pending(db, question_id, sq_id)], "max": wp.MAX_PHOTOS}


@router.get("/api/working-photos")
def list_pending(question_id: int, sq_id: int | None = None, db: Session = Depends(get_db)):
    return JSONResponse(_listing(db, question_id, sq_id))


@router.post("/api/working-photos")
async def upload(question_id: int = Form(...), sq_id: int | None = Form(None), files: list[UploadFile] = File(...),
                 db: Session = Depends(get_db)):
    errors = []
    for f in files[: wp.MAX_PHOTOS]:
        data = await f.read(wp.MAX_UPLOAD_BYTES + 1)
        try:
            wp.add(db, question_id, sq_id, data)
            db.commit()
        except wp.PhotoError as exc:
            db.rollback()
            errors.append(f"{f.filename or 'Photo'}: {exc}")
    out = _listing(db, question_id, sq_id)
    if errors:
        out["errors"] = errors
    return JSONResponse(out, status_code=200 if out["photos"] or not errors else 400)


@router.get("/working-photos/{photo_id}")
def view(photo_id: int, db: Session = Depends(get_db)):
    photo = db.get(WorkingPhoto, photo_id)
    path = wp.path_for(photo) if photo else None
    if path is None or not path.exists():
        return _err("Photo not found", 404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.delete("/api/working-photos/{photo_id}")
def delete(photo_id: int, db: Session = Depends(get_db)):
    photo = db.get(WorkingPhoto, photo_id)
    if photo is None:
        return _err("Photo not found", 404)
    qid, sq_id = photo.question_id, photo.session_question_id
    try:
        wp.remove(db, photo)
        db.commit()
    except wp.PhotoError as exc:
        db.rollback()
        return _err(str(exc), 409)
    return JSONResponse(_listing(db, qid, sq_id))


@router.post("/api/working-photos/read")
def read(question_id: int = Form(...), sq_id: int | None = Form(None), db: Session = Depends(get_db)):
    """Transcribe the pending photos. The student checks the result before anything is marked."""
    q = db.get(Question, question_id)
    if q is None:
        return _err("Unknown question", 404)
    photos = wp.pending(db, question_id, sq_id)
    if not photos:
        return _err("Add a photo of your working first.")
    provider = get_provider(st.all_settings(db))
    if not provider.generative or not provider.vision:
        return _err("Reading handwriting needs Claude (or another AI provider that reads images) to be set up in Settings. "
                    "You can still type your final answer — the photos are kept with it.", 409)
    try:
        reading = wp.read(db, provider, q, photos)
        db.commit()
    except wp.PhotoError as exc:
        return _err(str(exc))
    except (AIUnavailable, AIError) as exc:
        return _err(f"The photos couldn't be read: {exc}", 502)
    return JSONResponse({"ok": True, "reading": reading})
