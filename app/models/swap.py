"""v2-swap: the record of every real-time swap in a daily session (who, when, why, from, to).

A swap replaces an unanswered question (or a whole English reading set) with another one chosen by
the selection engine, or removes it when nothing suitable exists. The swapped-out question gets no
attempt, no skip and no exposure, so this table is the only trace of it: it feeds "Why these
questions?" and stops the same question coming straight back in the same session."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import utcnow


class SessionSwap(Base):
    __tablename__ = "session_swaps"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    session_id: Mapped[int] = mapped_column(ForeignKey("daily_sessions.id"), index=True)
    actor: Mapped[str] = mapped_column(String(40), default="student")  # who asked for it
    reason: Mapped[str] = mapped_column(String(20))  # not_learnt | different
    subject_code: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)  # first position of the swapped question(s) at the time
    outcome: Mapped[str] = mapped_column(String(20))  # replaced | removed
    from_question_ids: Mapped[list] = mapped_column(JSON, default=list)
    to_question_ids: Mapped[list] = mapped_column(JSON, default=list)
    plan_item_id: Mapped[int | None] = mapped_column(ForeignKey("learning_plan_items.id"), nullable=True)
    locked_plan_item_id: Mapped[int | None] = mapped_column(ForeignKey("learning_plan_items.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")  # what the student was told
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # the engine's facts (windows, minutes, why removed)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
