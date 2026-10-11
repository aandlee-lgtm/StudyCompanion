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
from app.models.legal_logic import LegalEvidenceCheck
from app.services import clock

PRIMARY_DOMAINS = ("legislation.nsw.gov.au", "legislation.gov.au", "hcourt.gov.au", "caselaw.nsw.gov.au", "humanrights.gov.au",
                   "lawreform.justice.nsw.gov.au", "alrc.gov.au", "parliament.nsw.gov.au", "aph.gov.au", "austlii.edu.au", "un.org", "ohchr.org")


def _on(host: str, domain: str) -> bool:
    """Dot-boundary domain match: 'www.legislation.gov.au' is on 'legislation.gov.au', 'evillegislation.gov.au' is not."""
    return host == domain or host.endswith("." + domain)


def classify_source(url: str) -> tuple[str, str]:
    host = re.sub(r"^https?://", "", url or "").split("/")[0].split(":")[0].lower()
    if not host:
        return "commentary", "unrated"
    if any(_on(host, d) for d in PRIMARY_DOMAINS):
        return "primary", "high"
    if host.endswith(".gov.au") or host.endswith(".gov"):
        return "official", "high"
    if any(_on(host, d) for d in ("abc.net.au", "smh.com.au", "theguardian.com", "sbs.com.au", "theconversation.com")):
        return "journalism", "medium"
    return "commentary", "unrated"  # unknown sites stay unrated until the student checks them


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
                       source_url=url, source_type=stype, reliability=rel, retrieved_date=clock.today(), last_verified_date=None,
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
        retrieved_date=clock.today(), last_verified_date=None, status=data.get("status") or "unknown",
        aliases=split_list(data.get("aliases")), sub_area=data.get("sub_area") or None, version_as_at=data.get("version_as_at") or None,
    )
    db.add(ev)
    db.flush()
    for tid in topic_ids:
        db.add(LegalEvidenceTopic(evidence_id=ev.id, topic_id=tid))
    if data.get("verified"):  # "I have checked this against the source today" when adding
        record_check(db, ev, {k: True for k in CHECKLIST}, version_as_at=data.get("version_as_at"), note="Checked when the item was added.")
    db.flush()
    return ev


CHECKLIST = {
    "title_year": "The title and year (or case citation) are exactly right",
    "jurisdiction": "The jurisdiction is right",
    "summary": "The summary is accurate",
    "current": "It is still in force / has not been overturned (or its status below is right)",
}
STATUSES = ("in_force", "amended", "repealed", "superseded", "unknown")
EDITABLE = ("title", "item_type", "date", "jurisdiction", "issue", "summary", "legal_significance", "syllabus_link", "source", "source_url",
            "source_type", "reliability", "status", "superseded_by", "sub_area", "version_as_at")
# a change to any of these means the last check no longer covers the item
CHECKED_FIELDS = ("title", "date", "jurisdiction", "summary", "status", "source_url")


def split_list(v) -> list[str] | None:
    if v is None:
        return None
    items = v if isinstance(v, list) else re.split(r"[,;\n]", str(v))
    out = [x.strip() for x in items if x and x.strip()]
    return out or None


def update_item(db: Session, ev: LegalEvidence, data: dict, topic_ids: list[int] | None = None) -> bool:
    """The edit form (legal-18). Returns True when the edit invalidated the last verification."""
    changed_checked = False
    for k in EDITABLE:
        if k not in data:
            continue
        v = data[k]
        v = v.strip() if isinstance(v, str) else v
        if k in ("title", "summary", "jurisdiction", "item_type", "source") and not v:
            raise ValueError(f"The {k.replace('_', ' ')} cannot be empty.")
        if k == "status" and v not in STATUSES:
            raise ValueError(f"Unknown status '{v}'.")
        v = v if v != "" else ("" if k == "legal_significance" else None)
        if getattr(ev, k) != v:
            if k in CHECKED_FIELDS and ev.last_verified_date is not None:
                changed_checked = True
            setattr(ev, k, v)
    for k in ("aliases", "issue_tags"):
        if k in data:
            setattr(ev, k, split_list(data[k]))
    if topic_ids is not None:
        keep = list(dict.fromkeys(int(t) for t in topic_ids))
        for link in list(ev.topics):
            if link.topic_id not in keep:
                ev.topics.remove(link)
        have = {link.topic_id for link in ev.topics}
        for tid in keep:
            if tid not in have:
                ev.topics.append(LegalEvidenceTopic(topic_id=tid))
    if changed_checked:
        ev.verification_note = f"Edited on {clock.today():%d %B %Y} after its last check: verify it again."
        ev.last_verified_date = None
    db.flush()
    return changed_checked


def record_check(db: Session, ev: LegalEvidence, checklist: dict, version_as_at: str | None = None, note: str | None = None,
                 corrected_summary: str | None = None, status: str | None = None) -> LegalEvidenceCheck:
    """The verification dialog (legal-19): every checklist point must be confirmed; legislation needs
    the version ('as at' date) that was read. Records who/when/what in the history table."""
    missing = [label for k, label in CHECKLIST.items() if not checklist.get(k)]
    if missing:
        raise ValueError("Confirm every point before marking the item verified: " + "; ".join(missing) + ".")
    version_as_at = (version_as_at or "").strip() or None
    if ev.item_type == "legislation" and not version_as_at:
        raise ValueError("For legislation, enter the version you read (the 'as at' or 'current version' date on the legislation website).")
    if status:
        if status not in STATUSES:
            raise ValueError(f"Unknown status '{status}'.")
        ev.status = status
    corrected = bool(corrected_summary and corrected_summary.strip() and corrected_summary.strip() != (ev.summary or "").strip())
    if corrected:
        ev.summary = corrected_summary.strip()
    today = clock.today()
    ev.last_verified_date = today
    if version_as_at:
        ev.version_as_at = version_as_at
    ev.verification_note = (f"Checked against the source on {today:%d %B %Y}" + (f" (version as at {version_as_at})" if version_as_at else "")
                            + (", summary corrected" if corrected else "") + "." + (f" {note.strip()}" if note and note.strip() else ""))
    row = LegalEvidenceCheck(evidence_id=ev.id, checked_on=today, version_as_at=version_as_at,
                             checklist={k: bool(checklist.get(k)) for k in CHECKLIST}, note=(note or "").strip() or None,
                             summary_corrected=corrected)
    db.add(row)
    db.flush()
    return row


def mark_verified(db: Session, ev: LegalEvidence, when: date | None = None) -> None:
    """Kept for callers of the v1 one-click action (scripts, tests): records a full check."""
    ev.last_verified_date = when or clock.today()
    ev.verification_note = f"Checked against the source on {ev.last_verified_date:%d %B %Y}."
    db.add(LegalEvidenceCheck(evidence_id=ev.id, checked_on=ev.last_verified_date, version_as_at=ev.version_as_at,
                              checklist={k: True for k in CHECKLIST}, note="Marked verified."))
    db.flush()


def delete_item(db: Session, ev: LegalEvidence) -> None:
    for row in db.execute(select(LegalEvidenceCheck).where(LegalEvidenceCheck.evidence_id == ev.id)).scalars():
        db.delete(row)
    db.flush()  # the history first: there is no ORM relationship to order the deletes
    db.delete(ev)
    db.flush()


def history(db: Session, ev: LegalEvidence) -> list[LegalEvidenceCheck]:
    return list(db.execute(select(LegalEvidenceCheck).where(LegalEvidenceCheck.evidence_id == ev.id)
                           .order_by(LegalEvidenceCheck.checked_on.desc(), LegalEvidenceCheck.id.desc())).scalars())


def state_of(ev: LegalEvidence, today: date, settings: dict | None = None) -> str:
    """verified | recheck_due | unverified | outdated (same rules as citation resolution)."""
    from app.services import citations as cit

    return cit.item_status(cit.make_item(ev), today, settings)


def grouped(db: Session, items: list[LegalEvidence], today: date, settings: dict | None = None) -> list[dict]:
    """The bank page grouped by sub-area, then issue (legal-18)."""
    from app.services import legal_plan as lp

    names = {code: info["title"] for code, info in lp.SUB_AREAS.items()}
    for it in lp.legal_items(db):
        names.setdefault(it.code, it.title)
    order = {code: i for i, code in enumerate(list(lp.SUB_AREAS) + [i.code for i in lp.legal_items(db)])}
    groups: dict[str, dict] = {}
    for ev in items:
        key = ev.sub_area or ""
        g = groups.setdefault(key, {"code": key, "title": names.get(key, "Not yet placed in a sub-area"), "issues": {}})
        g["issues"].setdefault(ev.issue or "General", []).append({"ev": ev, "state": state_of(ev, today, settings)})
    out = sorted(groups.values(), key=lambda g: order.get(g["code"], 999))
    for g in out:
        g["issues"] = sorted(g["issues"].items(), key=lambda kv: (kv[0] == "General", kv[0].lower()))
    return out


def counts(items: list[LegalEvidence], today: date, settings: dict | None = None) -> dict:
    by_type: dict[str, int] = {}
    by_state: dict[str, int] = {}
    for ev in items:
        by_type[ev.item_type] = by_type.get(ev.item_type, 0) + 1
        stt = state_of(ev, today, settings)
        by_state[stt] = by_state.get(stt, 0) + 1
    return {"type": by_type, "state": by_state}
