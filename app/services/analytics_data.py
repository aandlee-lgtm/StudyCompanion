"""Read-only loading of everything the analytics screens need (owner: analytics).

One query loads every attempt with the question columns analytics uses (no ORM objects, so
3,000+ attempts load in a few tens of milliseconds); the rest of the analytics code works on
the resulting ``Fact`` list in memory.

COUNTED ATTEMPTS. Only attempts that count as evidence are analysed: the first honest attempt
at a question in a session, or the first-ever attempt at it in practice. Retries, practice of
a question whose answer was already seen (after a skip or earlier the same day) and
self-marked answers that have not been marked yet are left out. When the attempt table has a
``counts_for_mastery`` column (v2 adaptive package) that flag is used instead of the
fallback rules."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Attempt,
    AttemptFeedback,
    ErrorJournal,
    LearningPlanItem,
    Mastery,
    Question,
    Stimulus,
    Subject,
    SyllabusTopic,
)
from app.services import clock
from app.services import settings as st

SUBJECT_NAMES = {"MATHS": "Mathematics Advanced", "ENGLISH": "English Advanced", "LEGAL": "Legal Studies"}
SUBJECT_SHORT = {"MATHS": "Maths", "ENGLISH": "English", "LEGAL": "Legal"}
DIFFICULTY_NAMES = {1: "Foundation", 2: "HSC-standard", 3: "Challenging"}


@dataclass(slots=True)
class Fact:
    """One counted attempt with the question data analytics needs."""

    attempt_id: int
    question_id: int
    sq_id: int | None
    subject: str
    day: date
    mark: float
    possible: float
    skipped: bool
    confidence: str | None
    seconds: int
    method: str
    plan_item_id: int | None
    area_id: int | None  # syllabus focus area / module / core topic
    difficulty: int
    est_minutes: float
    marks: int
    qtype: str
    verb: str | None
    category: str | None  # English unseen|course ; Legal core|option
    auto: bool  # machine-checkable answer (Maths answer, MCQ)
    mcq: bool
    form: str | None  # English stimulus form
    words: int
    repeat: bool  # this exact question was answered on an earlier day
    errors: list[str] = field(default_factory=list)
    error_tags: list[str] = field(default_factory=list)

    @property
    def frac(self) -> float:
        return 0.0 if self.skipped or not self.possible else max(0.0, min(1.0, self.mark / self.possible))

    @property
    def estimated(self) -> bool:
        """Marked by the offline estimate (no AI provider): a guide, not a reliable mark."""
        return self.method == "offline_estimate"

    @property
    def timed_ok(self) -> bool:
        return bool(self.seconds) and self.seconds / 60 <= 1.25 * max(0.5, self.est_minutes)


class Dataset:
    """Everything loaded once per page."""

    def __init__(self, db: Session, today: date | None = None):
        self.db = db
        self.settings = st.all_settings(db)
        self.today = today or clock.today(self.settings.get("timezone") or "Australia/Sydney")
        self.subject_codes = {s.id: s.code for s in db.execute(select(Subject)).scalars()}
        self.items: dict[int, LearningPlanItem] = {i.id: i for i in db.execute(select(LearningPlanItem)).scalars()}
        self.areas: dict[int, SyllabusTopic] = {t.id: t for t in db.execute(select(SyllabusTopic)).scalars()}
        self.mastery: dict[int, Mastery] = {m.plan_item_id: m for m in db.execute(select(Mastery)).scalars()}
        self.attempts_total = 0
        self.facts: list[Fact] = []
        self._load()

    # ------------------------------------------------------------------ loading ---
    def _load(self) -> None:
        db = self.db
        counts_col = getattr(Attempt, "counts_for_mastery", None)
        cols = [Attempt.id, Attempt.question_id, Attempt.session_question_id, Attempt.attempt_number, Attempt.skipped,
                Attempt.mark_awarded, Attempt.mark_possible, Attempt.confidence, Attempt.time_seconds, Attempt.marking_method,
                Attempt.submitted_at, Attempt.response_text, Question.subject_id, Question.plan_item_id, Question.topic_id,
                Question.difficulty, Question.estimated_minutes, Question.marks, Question.question_type, Question.directive_verb,
                Question.category, Question.answer, Stimulus.form]
        if counts_col is not None:
            cols.append(counts_col)
        stmt = (select(*cols).join(Question, Attempt.question_id == Question.id)
                .outerjoin(Stimulus, Question.stimulus_id == Stimulus.id)
                .where(Attempt.student_id == 1).order_by(Attempt.submitted_at, Attempt.id))
        rows = db.execute(stmt).all()
        self.attempts_total = len(rows)
        pending_self = self._pending_self_marks()
        errors, tags = self._errors()
        first_day: dict[int, date] = {}
        days_seen: dict[int, set[date]] = {}
        for r in rows:
            day = r.submitted_at.date()
            qid = r.question_id
            seen_before = qid in first_day
            same_day_before = day in days_seen.get(qid, ())
            repeat = seen_before and first_day[qid] < day
            first_day.setdefault(qid, day)
            days_seen.setdefault(qid, set()).add(day)
            flag = r[-1] if counts_col is not None else None
            if flag is not None:
                counted = bool(flag)
            else:
                counted = r.attempt_number == 1 and not same_day_before and (r.session_question_id is not None or not seen_before)
            if not counted or r.id in pending_self:
                continue
            item = self.items.get(r.plan_item_id) if r.plan_item_id else None
            area_id = item.topic_id if item is not None and item.topic_id else r.topic_id
            answer = r.answer if isinstance(r.answer, dict) else None
            auto = answer is not None
            mcq = r.question_type == "mcq" or (answer or {}).get("type") == "mcq"
            words = 0 if auto or r.skipped else len((r.response_text or "").split())
            self.facts.append(Fact(
                attempt_id=r.id, question_id=qid, sq_id=r.session_question_id, subject=self.subject_codes.get(r.subject_id, "?"),
                day=day, mark=r.mark_awarded or 0.0, possible=r.mark_possible or 0.0, skipped=bool(r.skipped), confidence=r.confidence,
                seconds=r.time_seconds or 0, method=r.marking_method or "", plan_item_id=r.plan_item_id, area_id=area_id,
                difficulty=r.difficulty or 2, est_minutes=r.estimated_minutes or 2.0, marks=r.marks or 1, qtype=r.question_type or "",
                verb=r.directive_verb, category=r.category, auto=auto, mcq=mcq, form=r.form, words=words, repeat=repeat,
                errors=errors.get(r.id, []), error_tags=tags.get(r.id, []),
            ))

    def _pending_self_marks(self) -> set[int]:
        out = set()
        for aid, payload in self.db.execute(select(AttemptFeedback.attempt_id, AttemptFeedback.payload).join(
                Attempt, AttemptFeedback.attempt_id == Attempt.id).where(Attempt.marking_method == "self")).all():
            if not (payload or {}).get("self_marked"):
                out.add(aid)
        return out

    def _errors(self) -> tuple[dict[int, list[str]], dict[int, list[str]]]:
        tag_col = getattr(ErrorJournal, "topic_tag", None)
        cols = [ErrorJournal.attempt_id, ErrorJournal.category] + ([tag_col] if tag_col is not None else [])
        errors: dict[int, list[str]] = {}
        tags: dict[int, list[str]] = {}
        for r in self.db.execute(select(*cols)).all():
            if r.category and r.category not in errors.setdefault(r.attempt_id, []):
                errors[r.attempt_id].append(r.category)
            if tag_col is not None and r[-1] and r[-1] not in tags.setdefault(r.attempt_id, []):
                tags[r.attempt_id].append(r[-1])
        return errors, tags

    # ------------------------------------------------------------------ helpers ---
    def since(self, days: int | None) -> date | None:
        """First day of a window of ``days`` days ending today (inclusive)."""
        return None if days is None else self.today - timedelta(days=days - 1)

    def window(self, since: date | None = None, until: date | None = None, subject: str | None = None) -> list[Fact]:
        return [f for f in self.facts if (since is None or f.day >= since) and (until is None or f.day <= until)
                and (subject is None or f.subject == subject)]

    def item_name(self, item_id: int | None) -> str:
        item = self.items.get(item_id) if item_id else None
        if item is None:
            return "Unassigned questions"
        return f"{item.code} {item.title}" if item.chapter else item.title

    def area_name(self, area_id: int | None) -> str:
        t = self.areas.get(area_id) if area_id else None
        return t.name if t else "Unmapped"

    def item_subject(self, item_id: int) -> str | None:
        item = self.items.get(item_id)
        return self.subject_codes.get(item.subject_id) if item else None

    def study_days(self, start: date, end: date) -> list[date]:
        """Scheduled study days in [start, end]."""
        weekdays = self.settings.get("weekdays") or [0, 1, 2, 3, 4]
        out, d = [], start
        while d <= end:
            if d.weekday() in weekdays:
                out.append(d)
            d += timedelta(days=1)
        return out

    @property
    def year_start(self) -> date | None:
        try:
            s = self.settings.get("year12_start_date")
            return date.fromisoformat(s) if s else None
        except ValueError:
            return None


def mean(xs) -> float | None:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def pct(x: float | None) -> int | None:
    return None if x is None else round(100 * x)
