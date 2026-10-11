"""Source registry, stimuli, questions and their 2027 syllabus mappings."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import APPROVAL_PENDING, utcnow


class Source(Base):
    """Every question references a Source row rather than repeating source strings.

    tier: 1 authoritative NESA, 2 historical NESA (pre-current syllabus), 3 trial/school,
    4 generated."""

    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    organisation: Mapped[str] = mapped_column(String(200), default="NESA")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40))  # hsc_exam|sample_exam|syllabus|marking_guideline|trial|generated|legal|textbook
    tier: Mapped[int] = mapped_column(Integer, default=4)
    url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    local_file: Mapped[str | None] = mapped_column(String(800), nullable=True)
    retrieved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    official: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SourceDocument(Base):
    __tablename__ = "source_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    kind: Mapped[str] = mapped_column(String(40), default="paper")  # paper|marking_guideline|syllabus
    local_file: Mapped[str] = mapped_column(String(800))
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    extraction_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="registered")  # registered|extracted|segmented|failed
    log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    source: Mapped[Source] = relationship()


class Stimulus(Base):
    """Shared stimulus: an unseen text, a legal scenario, a graph, or a cropped PDF region."""

    __tablename__ = "stimuli"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    title: Mapped[str] = mapped_column(String(300))
    form: Mapped[str | None] = mapped_column(String(60), nullable=True)  # prose fiction, poetry, speech, ...
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(800), nullable=True)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attribution: Mapped[str] = mapped_column(Text)  # always shown with the text
    provenance: Mapped[str] = mapped_column(String(40), default="generated_original")  # generated_original|historical|public_domain|licensed
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paired_with_id: Mapped[int | None] = mapped_column(ForeignKey("stimuli.id"), nullable=True)
    # v2-english-logic: context line shown above the text, text complexity 1-3 (vocabulary, syntax,
    # ambiguity, cultural distance) and seed metadata (set key, theme tags, length in words)
    headnote: Mapped[str | None] = mapped_column(Text, nullable=True)  # v2-english-logic
    complexity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # v2-english-logic
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # v2-english-logic

    source: Mapped[Source | None] = relationship(foreign_keys=[source_id])
    paired_with: Mapped["Stimulus | None"] = relationship(remote_side="Stimulus.id", foreign_keys=[paired_with_id], back_populates="paired_by")
    paired_by: Mapped[list["Stimulus"]] = relationship(foreign_keys=[paired_with_id], back_populates="paired_with")

    def reading_set(self) -> list["Stimulus"]:
        """All texts the student must read for a question on this stimulus, in order."""
        if self.paired_with is not None:
            return [self, self.paired_with]
        if self.paired_by:
            return [*self.paired_by, self]
        return [self]


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    source_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_exam: Mapped[str | None] = mapped_column(String(200), nullable=True)
    question_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_text: Mapped[str] = mapped_column(Text)
    question_image: Mapped[str | None] = mapped_column(String(800), nullable=True)
    stimulus_id: Mapped[int | None] = mapped_column(ForeignKey("stimuli.id"), nullable=True)
    marks: Mapped[int] = mapped_column(Integer, default=1)
    question_type: Mapped[str] = mapped_column(String(40), default="short_answer")  # mcq|short_answer|extended|working
    directive_verb: Mapped[str | None] = mapped_column(String(40), nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=2)  # 1 foundation, 2 HSC-standard, 3 challenging
    estimated_minutes: Mapped[float] = mapped_column(Float, default=2.0)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("syllabus_topics.id"), nullable=True)
    plan_item_id: Mapped[int | None] = mapped_column(ForeignKey("learning_plan_items.id"), nullable=True)
    syllabus_outcome_id: Mapped[int | None] = mapped_column(ForeignKey("syllabus_outcomes.id"), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)  # English: unseen|course ; Legal: core|option
    relevance_status: Mapped[str] = mapped_column(String(12), default="DIRECT")
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
    mapping_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    historical_or_generated: Mapped[str] = mapped_column(String(20), default="GENERATED")  # see ORIGINS
    generated_from_question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    is_extension: Mapped[bool] = mapped_column(Boolean, default=False)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)  # MCQ options
    answer: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # machine-checkable answer spec
    solution: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # worked solution, concept, method, technique, common_errors
    model_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    marking_guideline: Mapped[str | None] = mapped_column(Text, nullable=True)
    guideline_official: Mapped[bool] = mapped_column(Boolean, default=False)
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(12), default=APPROVAL_PENDING)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    legal_fact_currency: Mapped[str | None] = mapped_column(String(20), nullable=True)  # current|check|outdated
    facts_checked_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    source: Mapped[Source] = relationship()
    stimulus: Mapped[Stimulus | None] = relationship()
    parts: Mapped[list["QuestionPart"]] = relationship(back_populates="question", order_by="QuestionPart.position")
    mappings: Mapped[list["QuestionMapping"]] = relationship(back_populates="question", order_by="QuestionMapping.id")


class QuestionPart(Base):
    __tablename__ = "question_parts"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    label: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    marks: Mapped[int] = mapped_column(Integer, default=1)
    answer: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped[Question] = relationship(back_populates="parts")


class QuestionMapping(Base):
    """The audit trail of how a question was judged against the 2027 syllabus."""

    __tablename__ = "question_mappings"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    original_topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mapped_topic_id: Mapped[int | None] = mapped_column(ForeignKey("syllabus_topics.id"), nullable=True)
    focus_area: Mapped[str | None] = mapped_column(String(200), nullable=True)
    outcome_id: Mapped[int | None] = mapped_column(ForeignKey("syllabus_outcomes.id"), nullable=True)
    content_descriptor: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_classification: Mapped[str] = mapped_column(String(12))
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    mapping_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    mapping_reason: Mapped[str] = mapped_column(Text, default="")
    skill_relevance: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Legal: question skill relevance
    legal_fact_currency: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Legal: fact currency
    mapped_by: Mapped[str] = mapped_column(String(20), default="seed")  # seed|ai|offline|human
    review_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|edited
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    question: Mapped[Question] = relationship(back_populates="mappings")


class MarkingGuideline(Base):
    __tablename__ = "marking_guidelines"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    official: Mapped[bool] = mapped_column(Boolean, default=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
