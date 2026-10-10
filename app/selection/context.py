"""Everything the selection engine needs to know about the student on a given day."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Attempt, DailySession, LearningPlanItem, Mastery, Question, QuestionExposure, RevisionQueue, SessionQuestion
from app.services import settings as st


@dataclass
class StudentContext:
    today: date
    mode: str
    settings: dict
    plan: dict[int, LearningPlanItem]
    mastery: dict[int, Mastery]
    exposure: dict[int, QuestionExposure]
    revision_items: dict[int, float]  # plan_item_id -> priority (due today or earlier)
    revision_questions: dict[int, float]  # question_id -> priority
    recent_texts: list[str]  # questions seen in the last 7 days (for near-duplicate checks)
    recent_plan_counts: dict[int, int]  # plan item -> questions served in last 3 sessions
    item_attempts: dict[int, int]
    performance: dict[str, float | None]  # subject -> recent mean fraction
    performance_n: dict[str, int]
    progress: float  # 0 = start of Year 12, 1 = HSC
    recent_course_share: float | None  # English course-linked share over recent sessions
    sessions_since_extended: int
    weights: dict[str, float] = field(default_factory=dict)

    def target_difficulty(self, subject: str) -> float:
        """Continuous 1..3 target: rises through the year and with strong performance,
        falls when the student is struggling (but the composition keeps HSC-standard work)."""
        base = 1.6 + 0.9 * self.progress
        perf, nperf = self.performance.get(subject), self.performance_n.get(subject, 0)
        if perf is not None and nperf >= 5:
            if perf >= 0.85:
                base += 0.5 * min(1.0, nperf / 20)
            elif perf >= 0.7:
                base += 0.2
            elif perf < 0.35:
                base -= 0.7
            elif perf < 0.5:
                base -= 0.4
        behaviour = self.settings.get("difficulty_behaviour", "adaptive")
        base += {"stretch": 0.3, "consolidate": -0.3, "steady": 0.0, "adaptive": 0.0}.get(behaviour, 0.0)
        if self.mode == "exam":
            base += 0.3
        elif self.mode == "holiday":
            base -= 0.1
        return max(1.0, min(3.0, base))


def _progress(today: date, s: dict) -> float:
    try:
        start = date.fromisoformat(s.get("year12_start_date") or "2026-10-12")
        end = date.fromisoformat(s.get("hsc_start_date") or "2027-10-11")
    except ValueError:
        return 0.0
    if end <= start:
        return 0.0
    return max(0.0, min(1.0, (today - start).days / (end - start).days))


def resolve_mode(today: date, s: dict, requested: str | None = None) -> str:
    if requested and requested != "auto":
        return requested
    mode = s.get("mode", "auto")
    if mode != "auto":
        return mode
    for r in s.get("holiday_ranges") or []:
        try:
            if date.fromisoformat(r["start"]) <= today <= date.fromisoformat(r["end"]):
                return "holiday"
        except (KeyError, ValueError):
            continue
    return "normal"


def build_context(db: Session, today: date, mode: str | None = None, student_id: int = 1) -> StudentContext:
    s = st.all_settings(db)
    plan = {p.id: p for p in db.execute(select(LearningPlanItem)).scalars()}
    mastery = {m.plan_item_id: m for m in db.execute(select(Mastery).where(Mastery.student_id == student_id)).scalars()}
    exposure = {e.question_id: e for e in db.execute(select(QuestionExposure).where(QuestionExposure.student_id == student_id)).scalars()}

    rev_items: dict[int, float] = {}
    rev_qs: dict[int, float] = {}
    for r in db.execute(select(RevisionQueue).where(RevisionQueue.status == "open", RevisionQueue.due_date <= today)).scalars():
        overdue = (today - r.due_date).days
        pr = r.priority + min(0.5, overdue / 28)
        if r.plan_item_id:
            rev_items[r.plan_item_id] = max(rev_items.get(r.plan_item_id, 0), pr)
        if r.question_id:
            rev_qs[r.question_id] = max(rev_qs.get(r.question_id, 0), pr)

    week_ago = today - timedelta(days=7)
    recent_ids = [qid for qid, e in exposure.items() if e.last_seen >= week_ago]
    recent_texts = [q.question_text for q in db.execute(select(Question).where(Question.id.in_(recent_ids))).scalars()] if recent_ids else []

    last_sessions = list(db.execute(
        select(DailySession).where(DailySession.session_date < today, DailySession.status.in_(["generated", "in_progress", "completed"]))
        .order_by(DailySession.session_date.desc()).limit(10)
    ).scalars())
    recent_plan_counts: dict[int, int] = {}
    course, english_total, since_ext, found_ext = 0, 0, 0, False
    for i, sess in enumerate(last_sessions):
        for sq in sess.questions:
            q = sq.question
            if i < 3 and q.plan_item_id:
                recent_plan_counts[q.plan_item_id] = recent_plan_counts.get(q.plan_item_id, 0) + 1
            if sq.subject_code == "ENGLISH":
                english_total += 1
                course += 1 if q.category == "course" else 0
            if sq.subject_code == "LEGAL" and q.question_type == "extended":
                found_ext = True
        if not found_ext:
            since_ext += 1

    item_attempts: dict[int, int] = {}
    perf: dict[str, list[float]] = {"MATHS": [], "ENGLISH": [], "LEGAL": []}
    rows = db.execute(
        select(Attempt, Question).join(Question, Attempt.question_id == Question.id)
        .where(Attempt.student_id == student_id).order_by(Attempt.submitted_at.desc()).limit(400)
    ).all()
    for att, q in rows:
        if q.plan_item_id:
            item_attempts[q.plan_item_id] = item_attempts.get(q.plan_item_id, 0) + 1
        code = plan[q.plan_item_id].subject.code if q.plan_item_id in plan else None
        if code and len(perf[code]) < 20 and att.attempt_number == 1:
            perf[code].append(0.0 if att.skipped else att.fraction)

    weights = dict(s.get("selection_weights") or st.DEFAULTS["selection_weights"])
    resolved = resolve_mode(today, s, mode)
    if resolved == "holiday":  # less new content, more revision and weakness work
        weights["current"] *= 0.6
        weights["spaced"] *= 1.5
        weights["weakness"] *= 1.3
    total = sum(weights.values()) or 1.0
    weights = {k: v / total for k, v in weights.items()}

    return StudentContext(
        today=today, mode=resolved, settings=s, plan=plan, mastery=mastery, exposure=exposure,
        revision_items=rev_items, revision_questions=rev_qs, recent_texts=recent_texts,
        recent_plan_counts=recent_plan_counts, item_attempts=item_attempts,
        performance={k: (sum(v) / len(v) if v else None) for k, v in perf.items()},
        performance_n={k: len(v) for k, v in perf.items()},
        progress=_progress(today, s),
        recent_course_share=(course / english_total) if english_total else None,
        sessions_since_extended=since_ext if found_ext else 99,
        weights=weights,
    )
