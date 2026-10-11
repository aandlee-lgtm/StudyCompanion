"""Follow-up questions a student asks about the feedback on one attempt (v2-followup).

Each row is one turn of a short per-attempt thread: the student's question and, when an AI
provider answered it, the validated answer. Without an AI provider the question is saved for
the student's teacher instead ("Questions for my teacher" on the error journal page).
Answers explain the feedback; they never change the attempt's mark."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import utcnow
from app.models.questions import Question
from app.models.study import Attempt

# status values
ANSWERED = "answered"  # an AI answer is stored in ``answer``
OFFLINE = "offline"  # no AI provider: saved for the teacher, reference material shown instead
FAILED = "failed"  # the AI call failed or was declined; not counted as a turn, never sent as history


class FeedbackQuestion(Base):
    __tablename__ = "feedback_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    turn: Mapped[int] = mapped_column(Integer, default=1)  # 1-based position in the attempt's thread
    question_text: Mapped[str] = mapped_column(Text)
    chip: Mapped[str | None] = mapped_column(String(40), nullable=True)  # quick-question key, if a chip was used
    status: Mapped[str] = mapped_column(String(20), default=ANSWERED)
    answer: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"answer", "steps", "example", "checks"}
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    page_url: Mapped[str | None] = mapped_column(String(300), nullable=True)  # feedback page it was asked on
    for_teacher: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    teacher_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    attempt: Mapped[Attempt] = relationship()
    question: Mapped[Question] = relationship()
