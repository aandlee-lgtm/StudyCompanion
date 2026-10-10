"""Learning-plan management (statuses, ordering, options, sequence import)."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LearningPlanItem, Subject, SyllabusTopic
from app.models.common import LEARNED, LEARNING, LOCKED, PLAN_STATUSES, utcnow


def subject(db: Session, code: str) -> Subject:
    return db.execute(select(Subject).where(Subject.code == code)).scalar_one()


def items(db: Session, subject_code: str) -> list[LearningPlanItem]:
    s = subject(db, subject_code)
    return list(
        db.execute(
            select(LearningPlanItem).where(LearningPlanItem.subject_id == s.id).order_by(LearningPlanItem.position, LearningPlanItem.id)
        ).scalars()
    )


def set_status(db: Session, item_id: int, status: str) -> LearningPlanItem:
    if status not in PLAN_STATUSES:
        raise ValueError(f"unknown status {status}")
    item = db.get(LearningPlanItem, item_id)
    if item.status != status:
        item.status = status
        item.status_changed_at = utcnow()
    db.flush()
    return item


def start_from(db: Session, item_id: int) -> None:
    """Make ``item`` the current LEARNING item: earlier (non-assumed) items become LEARNED,
    later ones LOCKED. Items already in REVISION keep that status."""
    item = db.get(LearningPlanItem, item_id)
    for it in items(db, item.subject.code):
        if it.is_assumed_knowledge or not it.active:
            continue
        if it.position < item.position:
            new = it.status if it.status == "REVISION" else LEARNED
        elif it.id == item.id:
            new = LEARNING
        else:
            new = LOCKED
        if it.status != new:
            it.status, it.status_changed_at = new, utcnow()
    db.flush()


def advance(db: Session, subject_code: str) -> LearningPlanItem | None:
    """Mark the current LEARNING item LEARNED and unlock the next LOCKED one."""
    seq = [i for i in items(db, subject_code) if not i.is_assumed_knowledge and i.active]
    current = [i for i in seq if i.status == LEARNING]
    if not current:
        return None
    last = current[-1]
    for i in current:
        i.status, i.status_changed_at = LEARNED, utcnow()
    nxt = next((i for i in seq if i.position > last.position and i.status == LOCKED and not i.enrichment), None)
    if nxt:
        nxt.status, nxt.status_changed_at = LEARNING, utcnow()
    db.flush()
    return nxt


def reorder(db: Session, subject_code: str, ordered_ids: list[int]) -> None:
    by_id = {i.id: i for i in items(db, subject_code)}
    for pos, iid in enumerate(ordered_ids, start=1):
        if iid in by_id:
            by_id[iid].position = pos
    db.flush()


def set_option_active(db: Session, item_id: int, active: bool) -> None:
    item = db.get(LearningPlanItem, item_id)
    item.active = active
    if active and item.status == LOCKED:
        item.status = LEARNING
    if not active:
        item.status = LOCKED
    item.status_changed_at = utcnow()
    db.flush()


LINE = re.compile(r"^\s*(?P<code>\d{1,2}[A-Z])\s+(?P<title>.+?)\s*$")
CHAPTER = re.compile(r"^\s*CHAPTER\s+(?P<num>\d+)\s*[—\-:–]\s*(?P<title>.+?)\s*$", re.I)


def parse_sequence(text: str) -> list[dict]:
    """Parse a pasted table of contents ("CHAPTER 1 — SEQUENCES" / "1A Sequences ...")."""
    out, chapter, chapter_title = [], None, None
    for raw in text.splitlines():
        m = CHAPTER.match(raw)
        if m:
            chapter, chapter_title = int(m["num"]), m["title"].strip().title()
            continue
        m = LINE.match(raw)
        if m:
            code = m["code"]
            ch = int(re.match(r"\d+", code).group())
            out.append({"code": code, "title": m["title"], "chapter": chapter or ch, "chapter_title": chapter_title})
    return out


def import_sequence(db: Session, subject_code: str, text: str, default_topic_code: str | None = None) -> int:
    """Add or update plan items from pasted text, keeping existing statuses. Returns count."""
    s = subject(db, subject_code)
    existing = {i.code: i for i in items(db, subject_code)}
    topic = None
    if default_topic_code:
        topic = db.execute(select(SyllabusTopic).where(SyllabusTopic.code == default_topic_code)).scalar_one_or_none()
    rows = parse_sequence(text)
    for pos, row in enumerate(rows, start=1):
        it = existing.get(row["code"])
        if it is None:
            it = LearningPlanItem(subject_id=s.id, code=row["code"], title=row["title"], status=LOCKED, source="custom",
                                  topic_id=topic.id if topic else None, enrichment="challenge" in row["title"].lower())
            db.add(it)
        it.title, it.chapter, it.chapter_title, it.position = row["title"], row["chapter"], row["chapter_title"], pos
    db.flush()
    return len(rows)


def eligible_statuses() -> tuple[str, ...]:
    return ("LEARNING", "LEARNED", "REVISION")
