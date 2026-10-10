"""v2-adaptive tables: practice drafts, the exposure event log and revision sets."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import utcnow


class PracticeDraft(Base):
    """Autosaved draft for practice/revision mode (outside a daily session)."""

    __tablename__ = "practice_drafts"
    __table_args__ = (UniqueConstraint("student_id", "question_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    text: Mapped[str] = mapped_column(Text, default="")
    time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ExposureEvent(Base):
    """One row per attempt that touched the schedule: the evidence log behind mastery.

    Mastery can be audited (and recomputed) from these rows; ``counted`` is False for rehearsal."""

    __tablename__ = "exposure_events"
    __table_args__ = (Index("ix_exposure_events_plan_date", "plan_item_id", "study_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"))
    plan_item_id: Mapped[int | None] = mapped_column(ForeignKey("learning_plan_items.id"), nullable=True)
    study_date: Mapped[date] = mapped_column(Date)
    fraction: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[float] = mapped_column(Float, default=0.0)
    reliability: Mapped[float] = mapped_column(Float, default=1.0)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    method: Mapped[str] = mapped_column(String(30), default="deterministic")
    outcome_kind: Mapped[str] = mapped_column(String(30), default="")  # strong|unconfirmed|adequate|weak|very_weak|misconception|slip|skipped|estimated
    bucket: Mapped[str] = mapped_column(String(20), default="")
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    after_reveal: Mapped[bool] = mapped_column(Boolean, default=False)
    counted: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RevisionSet(Base):
    """A short revision mini-session started from the Revision page (3–5 due items, ~15 minutes)."""

    __tablename__ = "revision_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    created_on: Mapped[date] = mapped_column(Date)
    items: Mapped[list] = mapped_column(JSON, default=list)  # [{"question_id": .., "revision_id": .., "reason": ..}]
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|completed
    expected_minutes: Mapped[float] = mapped_column(Float, default=15)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
