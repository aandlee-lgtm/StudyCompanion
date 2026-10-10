"""Legal Studies evidence bank: verified, dated, sourced contemporary legal material."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class LegalEvidence(Base):
    __tablename__ = "legal_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(400))
    item_type: Mapped[str] = mapped_column(String(40))  # legislation|case|law_reform|report|inquiry|treaty|media|issue
    date: Mapped[str | None] = mapped_column(String(40), nullable=True)  # year or full date, as published
    jurisdiction: Mapped[str] = mapped_column(String(60))
    issue: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    legal_significance: Mapped[str] = mapped_column(Text, default="")
    syllabus_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), default="primary")  # primary|official|commentary|journalism
    reliability: Mapped[str] = mapped_column(String(20), default="high")  # high|medium|low
    retrieved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_verified_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    topics: Mapped[list["LegalEvidenceTopic"]] = relationship(back_populates="evidence", cascade="all, delete-orphan")

    @property
    def verified(self) -> bool:
        return self.last_verified_date is not None


class LegalEvidenceTopic(Base):
    __tablename__ = "legal_evidence_topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("legal_evidence.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("syllabus_topics.id"))

    evidence: Mapped[LegalEvidence] = relationship(back_populates="topics")
