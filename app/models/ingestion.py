"""v2-ingestion tables: required subtopics per question, linked stimuli, outcomes and the
review audit trail."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import utcnow


class QuestionPlanItem(Base):
    """Every learning-plan item a question needs. ``Question.plan_item_id`` is the primary item
    and is always the LATEST of these in the learning sequence, so a multi-topic question is
    released late rather than early. A question is servable only when none is LOCKED."""

    __tablename__ = "question_plan_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    plan_item_id: Mapped[int] = mapped_column(ForeignKey("learning_plan_items.id"))
    role: Mapped[str] = mapped_column(String(20), default="requires")  # primary | requires
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    plan_item = relationship("LearningPlanItem")


class QuestionStimulus(Base):
    """Texts a question refers to ("Texts 1 and 4"). ``Question.stimulus_id`` is the first."""

    __tablename__ = "question_stimuli"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    stimulus_id: Mapped[int] = mapped_column(ForeignKey("stimuli.id"))
    label: Mapped[str | None] = mapped_column(String(40), nullable=True)  # "Text 1"
    position: Mapped[int] = mapped_column(Integer, default=0)

    stimulus = relationship("Stimulus")


class QuestionOutcome(Base):
    """Syllabus outcomes a question tests (many-to-many)."""

    __tablename__ = "question_outcomes"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    outcome_id: Mapped[int] = mapped_column(ForeignKey("syllabus_outcomes.id"))

    outcome = relationship("SyllabusOutcome")


class ReviewDecision(Base):
    """One row per reviewer (or automatic) action on an imported question or source."""

    __tablename__ = "review_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"), nullable=True, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(30))  # approve|auto_approve|reject|edit|adapt|keep_parts|retire|restore|remap|reveal|delete_source
    actor: Mapped[str] = mapped_column(String(20), default="reviewer")  # reviewer | import (automatic)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
