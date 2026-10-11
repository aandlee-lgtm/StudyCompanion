"""Legal Studies evidence bank: verified, dated, sourced contemporary legal material."""
from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, Integer, String, Text
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
    # v2-legal-logic: structure for citation resolution, currency and grouping (legal-01/04/09/18)
    aliases: Mapped[list | None] = mapped_column(JSON, nullable=True)  # other names a citation may use, e.g. ["LEPRA", "Bail Act"]
    status: Mapped[str] = mapped_column(String(20), default="unknown", server_default="unknown")  # in_force|repealed|amended|superseded|unknown
    superseded_by: Mapped[str | None] = mapped_column(String(400), nullable=True)  # title of the item that replaced it
    sub_area: Mapped[str | None] = mapped_column(String(40), nullable=True)  # Legal plan item code, e.g. LS-CRIME-YOUNG
    issue_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)  # controlled vocabulary per sub-area
    version_as_at: Mapped[str | None] = mapped_column(String(40), nullable=True)  # legislation version checked ("as at" date)
    related: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{"title": "...", "relation": "interprets|amends|..."}]

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
