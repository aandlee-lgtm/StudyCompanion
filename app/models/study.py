"""Daily sessions, attempts, feedback, mastery, revision and the error journal."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import utcnow
from app.models.questions import Question


class DailySession(Base):
    __tablename__ = "daily_sessions"
    __table_args__ = (UniqueConstraint("student_id", "session_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    session_date: Mapped[date] = mapped_column(Date)
    session_number: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(20), default="normal")  # normal|holiday|exam|light
    status: Mapped[str] = mapped_column(String(20), default="generated")  # generated|in_progress|completed|missed|skipped
    target_minutes: Mapped[int] = mapped_column(Integer, default=90)
    expected_minutes: Mapped[float] = mapped_column(Float, default=0)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0)
    timer_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # "Why these questions?"
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # v2-selection: last heartbeat/activity (active-time timer)
    pause_note: Mapped[str | None] = mapped_column(String(200), nullable=True)  # v2-selection: why the timer was paused automatically

    questions: Mapped[list["SessionQuestion"]] = relationship(back_populates="session", order_by="SessionQuestion.position")


class SessionQuestion(Base):
    __tablename__ = "session_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("daily_sessions.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    subject_code: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|draft|submitted|skipped
    draft_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_saved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[DailySession] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship()


class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    session_question_id: Mapped[int | None] = mapped_column(ForeignKey("session_questions.id"), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    response_text: Mapped[str] = mapped_column(Text, default="")
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    mark_awarded: Mapped[float] = mapped_column(Float, default=0)
    mark_possible: Mapped[float] = mapped_column(Float, default=1)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)  # guess|unsure|confident|very_confident
    time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    marking_method: Mapped[str] = mapped_column(String(30), default="deterministic")  # deterministic|ai|offline_estimate|skipped
    official_guideline_used: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # v2-adaptive: one attempt chain per question. Only counted attempts are evidence for mastery and
    # schedules; retries and practice of a not-yet-due or already-revealed question are rehearsal.
    counts_for_mastery: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")  # v2-adaptive
    after_reveal: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # v2-adaptive
    evidence_role: Mapped[str | None] = mapped_column(String(20), nullable=True)  # v2-adaptive: first|due_repeat|retry|rehearsal|early_repeat
    model_viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # v2-adaptive: model response / full solution opened

    question: Mapped[Question] = relationship()
    feedback: Mapped["AttemptFeedback | None"] = relationship(back_populates="attempt", uselist=False)

    @property
    def fraction(self) -> float:
        return (self.mark_awarded / self.mark_possible) if self.mark_possible else 0.0


class AttemptFeedback(Base):
    __tablename__ = "attempt_feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)  # validated structured feedback
    why_lost: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_categories: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    attempt: Mapped[Attempt] = relationship(back_populates="feedback")


class QuestionExposure(Base):
    """Complete exposure history for each question (spaced repetition of the exact question)."""

    __tablename__ = "question_exposure"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), unique=True)
    first_seen: Mapped[date] = mapped_column(Date)
    last_seen: Mapped[date] = mapped_column(Date)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    score_history: Mapped[list] = mapped_column(JSON, default=list)
    mastery: Mapped[float] = mapped_column(Float, default=0.0)
    interval_days: Mapped[int] = mapped_column(Integer, default=7)
    next_revision_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ease: Mapped[float] = mapped_column(Float, default=2.0, server_default="2.0")  # v2-adaptive
    lapses: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # v2-adaptive


class Mastery(Base):
    """Mastery per learning-plan item (skill level), updated after every attempt."""

    __tablename__ = "mastery"
    __table_args__ = (UniqueConstraint("student_id", "plan_item_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    plan_item_id: Mapped[int] = mapped_column(ForeignKey("learning_plan_items.id"))
    mastery: Mapped[float] = mapped_column(Float, default=0.5)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_revision_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # v2-adaptive: rebuild state for struggling skills, memory model (lapses/ease), last success
    state: Mapped[str] = mapped_column(String(20), default="normal", server_default="normal")  # v2-adaptive: normal|rebuild
    state_since: Mapped[date | None] = mapped_column(Date, nullable=True)  # v2-adaptive
    rebuild_correct: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # v2-adaptive
    lapses: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # v2-adaptive
    ease: Mapped[float] = mapped_column(Float, default=2.0, server_default="2.0")  # v2-adaptive
    last_success: Mapped[date | None] = mapped_column(Date, nullable=True)  # v2-adaptive


class RevisionQueue(Base):
    __tablename__ = "revision_queue"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    plan_item_id: Mapped[int | None] = mapped_column(ForeignKey("learning_plan_items.id"), nullable=True)
    due_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|done|dismissed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # v2-adaptive: lifecycle and audit of revision items
    kind: Mapped[str] = mapped_column(String(30), default="weak_revisit", server_default="weak_revisit")  # v2-adaptive
    tag: Mapped[str | None] = mapped_column(String(60), nullable=True)  # v2-adaptive: error tag for pattern items
    source_attempt_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # v2-adaptive: attempt that queued it
    completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)  # v2-adaptive
    served_by_attempt_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # v2-adaptive
    outcome: Mapped[float | None] = mapped_column(Float, nullable=True)  # v2-adaptive: fraction scored when served

    question: Mapped[Question | None] = relationship()


class ErrorJournal(Base):
    __tablename__ = "error_journal"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    subject_code: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text)
    plan_item_id: Mapped[int | None] = mapped_column(ForeignKey("learning_plan_items.id"), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # v2-adaptive: two axes (error type + topic tag), local study date, retry fixes, auto-resolution
    topic_tag: Mapped[str | None] = mapped_column(String(60), nullable=True)  # v2-adaptive
    study_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # v2-adaptive
    fixed_on_retry: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # v2-adaptive
    resolved_on: Mapped[date | None] = mapped_column(Date, nullable=True)  # v2-adaptive
    auto_resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # v2-adaptive
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # v2-adaptive: deterministic|ai|self|mcq

    question: Mapped[Question] = relationship()


class TutorComment(Base):
    """Reserved for the future Tutor Mode (not used by version 1's interface)."""

    __tablename__ = "tutor_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    author: Mapped[str] = mapped_column(String(120))
    target_type: Mapped[str] = mapped_column(String(40))  # attempt|plan_item|week
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
