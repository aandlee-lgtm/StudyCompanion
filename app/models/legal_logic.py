"""v2-legal-logic: verification history for Legal evidence items (legal-19).

Each row records one check of an evidence item against its source: when, which version of the
legislation (``version_as_at``), which checklist points were confirmed and an optional note."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import utcnow


class LegalEvidenceCheck(Base):
    __tablename__ = "legal_evidence_checks"
    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("legal_evidence.id", ondelete="CASCADE"), index=True)
    checked_on: Mapped[date] = mapped_column(Date)
    version_as_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    checklist: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"title_year": true, "jurisdiction": true, ...}
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_corrected: Mapped[bool] = mapped_column(default=False)
    checked_by: Mapped[str] = mapped_column(String(40), default="student")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
