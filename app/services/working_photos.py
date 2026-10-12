"""Photos of handwritten working: validate, normalise, store, attach to attempts, and (with an AI
provider that reads images) transcribe.

Every upload is decoded and re-encoded as a JPEG: the stored file never contains the original
bytes, location or camera metadata, and anything that is not a real image is rejected. iPhone
HEIC photos are converted with macOS's built-in ``sips`` tool when Pillow cannot read them."""
from __future__ import annotations

import hashlib
import io
import logging
import shutil
import subprocess
import sys
import tempfile
import uuid
import warnings
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import config
from app.models import Attempt, Question, WorkingPhoto

log = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_PHOTOS = 6  # pages per answer
MAX_PIXELS = 60_000_000  # larger images are refused rather than decoded (decompression bombs)
STORE_EDGE = 2000  # longest edge of the stored JPEG
SEND_EDGE = 1568  # longest edge sent to an AI model (enough for handwriting, keeps requests small)

HEIC_HELP = ("This photo is in Apple's HEIC format, which couldn't be converted here. On the iPhone choose "
             "Settings → Camera → Formats → Most Compatible, or export the photo as a JPEG, and try again.")


class PhotoError(ValueError):
    """A user-facing reason an upload was refused."""


def _is_heic(data: bytes) -> bool:
    return data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1")


def _convert_with_sips(data: bytes) -> bytes | None:
    """macOS only: convert HEIC to JPEG with the system's sips tool."""
    sips = shutil.which("sips") if sys.platform == "darwin" else None
    if not sips:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "in.heic", Path(tmp) / "out.jpg"
        src.write_bytes(data)
        try:
            subprocess.run([sips, "-s", "format", "jpeg", str(src), "--out", str(dst)], check=True,
                           capture_output=True, timeout=60)
        except (subprocess.SubprocessError, OSError) as exc:
            log.warning("sips could not convert a HEIC photo: %s", exc)
            return None
        return dst.read_bytes() if dst.exists() else None


def _open_image(data: bytes):
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            img = Image.open(io.BytesIO(data))
            if img.format not in ("JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF", "MPO"):
                raise PhotoError("Please upload a photo (JPEG, PNG, WebP or HEIC).")
            img.load()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise PhotoError("That image is too large. Use a normal phone photo or screenshot.") from exc
        except PhotoError:
            raise
        except Exception as exc:
            raise PhotoError("That file isn't a photo this app can read. Use a JPEG, PNG, WebP or HEIC photo.") from exc
    img = ImageOps.exif_transpose(img)  # phone photos are often stored sideways with a rotation tag
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _jpeg(img, edge: int, quality: int = 85) -> bytes:
    img = img.copy()
    img.thumbnail((edge, edge))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=quality, optimize=True)  # no EXIF: metadata is dropped
    return out.getvalue()


def normalise(data: bytes) -> tuple[bytes, int, int]:
    """Decode an uploaded photo and return (jpeg bytes, width, height) ready to store."""
    if not data:
        raise PhotoError("The file was empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise PhotoError(f"That file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if _is_heic(data):
        try:
            img = _open_image(data)  # works if a HEIF plugin happens to be installed
        except PhotoError:
            converted = _convert_with_sips(data)
            if converted is None:
                raise PhotoError(HEIC_HELP)
            img = _open_image(converted)
    else:
        img = _open_image(data)
    if min(img.size) < 50:
        raise PhotoError("That image is too small to show any working.")
    jpeg = _jpeg(img, STORE_EDGE)
    w, h = img.size
    scale = min(1.0, STORE_EDGE / max(w, h))
    return jpeg, round(w * scale), round(h * scale)


# ------------------------------------------------------------------ storage ---
def path_for(photo: WorkingPhoto) -> Path:
    return config.working_dir / Path(photo.filename).name


def pending(db: Session, question_id: int, sq_id: int | None) -> list[WorkingPhoto]:
    """Photos uploaded for an answer that has not been submitted yet."""
    stmt = select(WorkingPhoto).where(WorkingPhoto.question_id == question_id, WorkingPhoto.attempt_id.is_(None))
    stmt = stmt.where(WorkingPhoto.session_question_id == sq_id) if sq_id else stmt.where(WorkingPhoto.session_question_id.is_(None))
    return list(db.scalars(stmt.order_by(WorkingPhoto.page, WorkingPhoto.id)))


def pending_any(db: Session, question_id: int) -> list[WorkingPhoto]:
    """Unsubmitted photos for a question, whichever session they were added in."""
    return list(db.scalars(select(WorkingPhoto).where(WorkingPhoto.question_id == question_id, WorkingPhoto.attempt_id.is_(None))
                           .order_by(WorkingPhoto.page, WorkingPhoto.id)))


def for_attempt(db: Session, attempt_id: int) -> list[WorkingPhoto]:
    return list(db.scalars(select(WorkingPhoto).where(WorkingPhoto.attempt_id == attempt_id).order_by(WorkingPhoto.page, WorkingPhoto.id)))


def add(db: Session, question_id: int, sq_id: int | None, data: bytes) -> WorkingPhoto:
    if db.get(Question, question_id) is None:
        raise PhotoError("Unknown question.")
    existing = pending(db, question_id, sq_id)
    digest = hashlib.sha256(data).hexdigest()
    for p in existing:
        if p.source_sha256 == digest:
            return p  # the same photo added twice
    if len(existing) >= MAX_PHOTOS:
        raise PhotoError(f"You can add up to {MAX_PHOTOS} photos to one answer. Remove one first.")
    jpeg, w, h = normalise(data)
    config.working_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    (config.working_dir / name).write_bytes(jpeg)
    photo = WorkingPhoto(question_id=question_id, session_question_id=sq_id or None, filename=name,
                         page=(max((p.page for p in existing), default=0) + 1), width=w, height=h,
                         size_bytes=len(jpeg), source_sha256=digest)
    db.add(photo)
    db.flush()
    return photo


def remove(db: Session, photo: WorkingPhoto) -> None:
    if photo.attempt_id is not None:
        raise PhotoError("This photo belongs to a submitted answer and is kept with it.")
    try:
        path_for(photo).unlink(missing_ok=True)
    except OSError as exc:  # pragma: no cover - file system edge case
        log.warning("Could not delete %s: %s", photo.filename, exc)
    db.delete(photo)
    db.flush()


def attach_pending(db: Session, attempt: Attempt) -> list[WorkingPhoto]:
    """Called when an answer is submitted: its pending photos become part of the attempt."""
    photos = pending(db, attempt.question_id, attempt.session_question_id)
    for p in photos:
        p.attempt_id = attempt.id
    db.flush()
    return photos


def images(photos: list[WorkingPhoto]) -> list[tuple[str, bytes]]:
    """The photos as (media type, bytes) for an AI provider, downsized for the request."""
    from PIL import Image

    out = []
    for p in photos:
        path = path_for(p)
        if not path.exists():
            continue
        with Image.open(path) as img:
            out.append(("image/jpeg", _jpeg(img.convert("RGB"), SEND_EDGE, quality=88)))
    return out


def public(photo: WorkingPhoto) -> dict:
    return {"id": photo.id, "page": photo.page, "url": f"/working-photos/{photo.id}", "width": photo.width,
            "height": photo.height, "attached": photo.attempt_id is not None}


# ------------------------------------------------------------------ reading ---
def reading_context(q: Question) -> dict:
    sol = q.solution or {}
    spec = sol.get("answer") if isinstance(sol.get("answer"), dict) else None
    fmt = None
    if spec:
        fmt = {"num": "a number", "expr": "an algebraic expression", "set": "a set of values", "interval": "an interval or inequality",
               "antiderivative": "an expression (include + C)", "mcq": "a letter A-D"}.get(spec.get("type"), spec.get("type"))
    parts = [{"label": p.label, "text": p.text} for p in (q.parts or [])] if getattr(q, "parts", None) else []
    return {"question": q.question_text, "marks": q.marks, "answer_format": fmt, "parts": parts}


def read(db: Session, provider, q: Question, photos: list[WorkingPhoto]) -> dict:
    """Ask a vision-capable provider to transcribe the photos. Raises AIError/AIUnavailable."""
    imgs = images(photos)
    if not imgs:
        raise PhotoError("Add a photo of your working first.")
    result = provider.read_working(reading_context(q), imgs)
    data = result.model_dump()
    for p in photos:
        p.reading = data
    db.flush()
    return data
