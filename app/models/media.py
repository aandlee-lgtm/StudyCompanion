"""Photos of handwritten working attached to an answer."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import utcnow


class WorkingPhoto(Base):
    """One page of working. Uploaded while answering (attempt_id is empty until the answer is
    submitted), then attached to the attempt. The image file lives in ``config.working_dir``."""

    __tablename__ = "working_photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    session_question_id: Mapped[int | None] = mapped_column(ForeignKey("session_questions.id"), nullable=True)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("attempts.id"), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(80), unique=True)  # name inside config.working_dir
    page: Mapped[int] = mapped_column(Integer, default=1)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    source_sha256: Mapped[str] = mapped_column(String(64), default="")  # of the uploaded file (duplicate check)
    reading: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # what the AI read from the page, if asked
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
