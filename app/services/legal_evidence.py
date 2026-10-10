"""Legal evidence bank: add items manually or from a URL (fetched, summarised by the AI
provider from the page text only), and record verification dates."""
from __future__ import annotations

import re
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIError
from app.ai.factory import get_provider
from app.models import LegalEvidence, LegalEvidenceTopic, SyllabusTopic

PRIMARY_DOMAINS = ("legislation.nsw.gov.au", "legislation.gov.au", "hcourt.gov.au", "caselaw.nsw.gov.au", "humanrights.gov.au",
                   "lawreform.justice.nsw.gov.au", "alrc.gov.au", "parliament.nsw.gov.au", "aph.gov.au", "austlii.edu.au", "un.org", "ohchr.org")


def classify_source(url: str) -> tuple[str, str]:
    host = re.sub(r"^https?://", "", url or "").split("/")[0].lower()
    if any(host.endswith(d) for d in PRIMARY_DOMAINS):
        return "primary", "high"
    if host.endswith(".gov.au") or host.endswith(".gov"):
        return "official", "high"
    if any(host.endswith(d) for d in ("abc.net.au", "smh.com.au", "theguardian.com", "sbs.com.au", "theconversation.com")):
        return "journalism", "medium"
    return "commentary", "medium"


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|nav|footer|header).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def add_from_url(db: Session, url: str, topic_ids: list[int], settings: dict) -> LegalEvidence:
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True, headers={"User-Agent": "HSC-Companion/1.0 (private study)"})
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"Could not fetch the page: {exc}") from exc
    text = html_to_text(r.text)
    provider = get_provider(settings)
    if not provider.generative:
        raise ValueError("Summarising a source needs an AI provider. Add the item manually instead (you can paste the key facts).")
    topics = [t.name for t in db.execute(select(SyllabusTopic).where(SyllabusTopic.id.in_(topic_ids))).scalars()]
    try:
        s = provider.summarise_legal_source({"url": url, "text": text, "topics": ", ".join(topics)})
    except AIError as exc:
        raise ValueError(f"The AI summary could not be validated: {exc}") from exc
    stype, rel = classify_source(url)
    ev = LegalEvidence(title=s.title, item_type=s.item_type, date=s.date, jurisdiction=s.jurisdiction or "Unknown", issue=s.issue,
                       summary=s.summary, legal_significance=s.legal_significance, syllabus_link=s.syllabus_link, source=url.split("/")[2],
                       source_url=url, source_type=stype, reliability=rel, retrieved_date=date.today(), last_verified_date=None,
                       verification_note="AI summary of the fetched page. Read the source and click 'Mark verified today' once you have checked it.")
    db.add(ev)
    db.flush()
    for tid in topic_ids:
        db.add(LegalEvidenceTopic(evidence_id=ev.id, topic_id=tid))
    db.flush()
    return ev


def _host(url: str | None) -> str | None:
    if not url or "//" not in url:
        return None
    return url.split("/")[2]


def add_manual(db: Session, data: dict, topic_ids: list[int]) -> LegalEvidence:
    stype, rel = classify_source(data.get("source_url") or "")
    ev = LegalEvidence(
        title=data["title"], item_type=data.get("item_type", "media"), date=data.get("date"), jurisdiction=data.get("jurisdiction") or "NSW",
        issue=data.get("issue"), summary=data["summary"], legal_significance=data.get("legal_significance", ""), syllabus_link=data.get("syllabus_link"),
        source=data.get("source") or _host(data.get("source_url")) or "Manual entry",
        source_url=data.get("source_url"), source_type=data.get("source_type") or stype, reliability=data.get("reliability") or rel,
        retrieved_date=date.today(), last_verified_date=date.today() if data.get("verified") else None,
    )
    db.add(ev)
    db.flush()
    for tid in topic_ids:
        db.add(LegalEvidenceTopic(evidence_id=ev.id, topic_id=tid))
    db.flush()
    return ev


def mark_verified(db: Session, ev: LegalEvidence, when: date | None = None) -> None:
    ev.last_verified_date = when or date.today()
    ev.verification_note = f"Checked against the source on {ev.last_verified_date:%d %B %Y}."
    db.flush()
