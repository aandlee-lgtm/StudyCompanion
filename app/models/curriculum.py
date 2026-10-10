"""Subjects, syllabuses, outcomes and the student's editable learning plans."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import LOCKED, utcnow


class Student(Base):
    """Version 1 has a single student (id=1). The table exists so a future Tutor Mode can
    attach tutors/comments without a schema rewrite."""

    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Student")
    hsc_year: Mapped[int] = mapped_column(Integer, default=2027)
    role: Mapped[str] = mapped_column(String(20), default="student")  # student | tutor (future)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)  # MATHS | ENGLISH | LEGAL
    name: Mapped[str] = mapped_column(String(120))
    daily_count: Mapped[int] = mapped_column(Integer, default=3)
    position: Mapped[int] = mapped_column(Integer, default=0)


class SyllabusVersion(Base):
    __tablename__ = "syllabus_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    name: Mapped[str] = mapped_column(String(200))
    first_hsc_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current: Mapped[bool] = mapped_column(Boolean, default=True)
    official_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SyllabusTopic(Base):
    """A NESA focus area / module / core topic / option topic."""

    __tablename__ = "syllabus_topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    syllabus_version_id: Mapped[int | None] = mapped_column(ForeignKey("syllabus_versions.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), default="focus_area")  # focus_area|year11|module|unseen|core|option
    year_level: Mapped[int] = mapped_column(Integer, default=12)
    is_option: Mapped[bool] = mapped_column(Boolean, default=False)
    examinable: Mapped[bool] = mapped_column(Boolean, default=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma list used by offline mapper
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    subject: Mapped[Subject] = relationship()


class SyllabusOutcome(Base):
    __tablename__ = "syllabus_outcomes"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("syllabus_topics.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text)
    official: Mapped[bool] = mapped_column(Boolean, default=False)  # False = placeholder until imported
    content_descriptor: Mapped[str | None] = mapped_column(Text, nullable=True)


class LearningPlanItem(Base):
    """One step of the student's learning pathway (e.g. Cambridge 1A, an English module,
    a Legal core/option topic). Statuses drive what may be served."""

    __tablename__ = "learning_plan_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), default=1)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("syllabus_topics.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(30))  # e.g. "1A", "Y11-FN", "MOD-TC", "CORE-CRIME"
    title: Mapped[str] = mapped_column(String(300))
    chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(12), default=LOCKED)
    enrichment: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)  # Legal options: inactive until chosen
    is_assumed_knowledge: Mapped[bool] = mapped_column(Boolean, default=False)  # Year 11
    source: Mapped[str] = mapped_column(String(40), default="custom")  # cambridge|nesa|custom
    status_changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    subject: Mapped[Subject] = relationship()
    topic: Mapped[SyllabusTopic | None] = relationship()


class PrescribedText(Base):
    __tablename__ = "prescribed_texts"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("syllabus_topics.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    author: Mapped[str] = mapped_column(String(200))
    form: Mapped[str | None] = mapped_column(String(60), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. the prescribed poem list
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
