"""Progress analytics with interpretation, HSC Readiness, historical coverage and the
end-of-day / weekly / monthly reviews. Interpretations are rule-based and only made when
there is enough data."""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Attempt,
    DailySession,
    ErrorJournal,
    LearningPlanItem,
    Mastery,
    Question,
    QuestionExposure,
    RevisionQueue,
    Subject,
    SyllabusTopic,
)
from app.models.common import ORIGIN_HISTORICAL, ORIGIN_SAMPLE
from app.services import clock
from app.services import settings as st

SUBJECT_NAMES = {"MATHS": "Mathematics Advanced", "ENGLISH": "English Advanced", "LEGAL": "Legal Studies"}
WINDOWS = {"7": 7, "30": 30, "60": 60, "90": 90, "all": None}


@dataclass
class Row:
    attempt: Attempt
    question: Question
    subject: str
    item: LearningPlanItem | None
    day: date


def rows(db: Session, since: date | None = None, first_only: bool = True) -> list[Row]:
    subjects = {s.id: s.code for s in db.execute(select(Subject)).scalars()}
    items = {i.id: i for i in db.execute(select(LearningPlanItem)).scalars()}
    q = select(Attempt, Question).join(Question, Attempt.question_id == Question.id)
    if first_only:
        q = q.where(Attempt.attempt_number == 1)
    if since:
        q = q.where(Attempt.submitted_at >= datetime.combine(since, datetime.min.time()))
    return [Row(a, qq, subjects[qq.subject_id], items.get(qq.plan_item_id), a.submitted_at.date()) for a, qq in db.execute(q).all()]


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def _pct(x):
    return None if x is None else round(100 * x)


def _frac(r: Row) -> float:
    return 0.0 if r.attempt.skipped else r.attempt.fraction


def window_since(db: Session, window: str) -> date | None:
    days = WINDOWS.get(window)
    return None if days is None else clock.today(st.get(db, "timezone")) - timedelta(days=days)


def progress_report(db: Session, window: str = "30") -> dict:
    since = window_since(db, window)
    rs = rows(db, since)
    by_subject: dict[str, list[Row]] = defaultdict(list)
    for r in rs:
        by_subject[r.subject].append(r)
    subjects = {}
    for code, name in SUBJECT_NAMES.items():
        lst = by_subject.get(code, [])
        topics: dict[str, list[float]] = defaultdict(list)
        outcomes: dict[str, list[float]] = defaultdict(list)
        diffs: dict[int, list[float]] = defaultdict(list)
        times = []
        for r in lst:
            key = f"{r.item.code} {r.item.title}" if r.item and r.item.chapter else (r.item.title if r.item else "Other")
            topics[key].append(_frac(r))
            if r.item and r.item.topic:
                outcomes[r.item.topic.name].append(_frac(r))
            diffs[r.question.difficulty].append(_frac(r))
            if r.attempt.time_seconds and not r.attempt.skipped:
                times.append((r.attempt.time_seconds / 60, r.question.estimated_minutes))
        marks_awarded = sum(r.attempt.mark_awarded for r in lst)
        marks_possible = sum(r.attempt.mark_possible for r in lst)
        written = [r for r in lst if r.question.answer is None and not r.attempt.skipped]
        subjects[code] = {
            "name": name, "attempts": len(lst), "accuracy": _pct(_mean(1.0 if _frac(r) >= 0.85 else 0.0 for r in lst)),
            "average": _pct(_mean(_frac(r) for r in lst)), "marks": f"{marks_awarded:g}/{marks_possible:g}" if lst else "—",
            "topics": sorted(((k, _pct(_mean(v)), len(v)) for k, v in topics.items()), key=lambda t: (t[1] if t[1] is not None else 0)),
            "outcomes": sorted(((k, _pct(_mean(v)), len(v)) for k, v in outcomes.items()), key=lambda t: t[1] or 0),
            "difficulty": {d: (_pct(_mean(v)), len(v)) for d, v in sorted(diffs.items())},
            "time_ratio": round(_mean(a / e for a, e in times if e) or 0, 2) if times else None,
            "avg_minutes": round(_mean(a for a, _ in times), 1) if times else None,
            "avg_words": round(_mean(len(r.attempt.response_text.split()) for r in written)) if written else None,
            "skipped": sum(1 for r in lst if r.attempt.skipped),
        }
    revision = [r for r in rs if (r.attempt.question_id in _repeated_ids(db))]
    errors = Counter((e.subject_code, e.category) for e in db.execute(
        select(ErrorJournal).where(ErrorJournal.created_at >= datetime.combine(since, datetime.min.time())) if since else select(ErrorJournal)).scalars())
    return {
        "window": window, "since": since, "subjects": subjects, "total_attempts": len(rs),
        "revision_performance": _pct(_mean(_frac(r) for r in revision)), "revision_n": len(revision),
        "repeated_errors": errors.most_common(8), "coverage": syllabus_coverage(db), "not_assessed": not_yet_assessed(db),
        "interpretation": interpret(db, rs, subjects, errors),
    }


def _repeated_ids(db: Session) -> set[int]:
    return {e.question_id for e in db.execute(select(QuestionExposure).where(QuestionExposure.attempts > 1)).scalars()}


def interpret(db: Session, rs: list[Row], subjects: dict, errors: Counter) -> list[str]:
    out: list[str] = []
    if len(rs) < 5:
        return ["Not enough answers yet for reliable interpretation — complete a few sessions and check back."]
    for code, data in subjects.items():
        name = SUBJECT_NAMES[code]
        topics = [t for t in data["topics"] if t[2] >= 3]
        if len(topics) >= 2 and topics[-1][1] - topics[0][1] >= 20:
            out.append(f"{name}: you are consistently stronger on {topics[-1][0]} ({topics[-1][1]}%) than on {topics[0][0]} ({topics[0][1]}%).")
        d = data["difficulty"]
        if 1 in d and 3 in d and d[1][1] >= 3 and d[3][1] >= 3 and d[1][0] - d[3][0] >= 25:
            out.append(f"{name}: you handle foundation questions well ({d[1][0]}%) but lose marks on challenging, multi-step questions ({d[3][0]}%). Practise breaking longer problems into stages.")
        if data["time_ratio"] and data["time_ratio"] > 1.3 and data["attempts"] >= 5:
            out.append(f"{name}: you are taking about {round((data['time_ratio'] - 1) * 100)}% longer than the exam-style time estimate. Time pressure will matter more as the HSC approaches.")
    eng = [e for e in errors.items() if e[0][0] == "ENGLISH"]
    if eng:
        top = max(eng, key=lambda e: e[1])
        msg = {
            "technique identification without analysis": "your English responses identify techniques accurately, but the analysis of how they shape meaning is less developed.",
            "insufficient textual evidence": "your English responses need more precise, integrated textual evidence.",
            "descriptive response": "your English responses tend to describe the text rather than analyse how meaning is made.",
            "poor comparison": "comparative English responses need explicit, integrated comparison rather than two separate discussions.",
            "limited evaluation": "evaluation questions need a clear judgement sustained through the response.",
        }.get(top[0][1])
        if msg and top[1] >= 2:
            out.append(f"English: {msg} (flagged {top[1]} times)")
    leg = [e for e in errors.items() if e[0][0] == "LEGAL"]
    if leg:
        top = max(leg, key=lambda e: e[1])
        if top[1] >= 2:
            out.append(f"Legal Studies: the most frequent issue is '{top[0][1]}' ({top[1]} times). Build it into your next practice answers deliberately.")
    mth = [e for e in errors.items() if e[0][0] == "MATHS"]
    if mth:
        top = max(mth, key=lambda e: e[1])
        if top[1] >= 2:
            out.append(f"Mathematics: your most common error type is '{top[0][1]}' ({top[1]} times). " + (
                "These are slips, not misunderstandings — check each line as you write it." if top[0][1] in ("sign", "arithmetic", "careless error") else
                "Revisit the underlying concept rather than just redoing questions."))
    guesses = [r for r in rs if r.attempt.confidence == "guess"]
    if len(guesses) >= 4:
        right = sum(1 for r in guesses if _frac(r) >= 0.85)
        out.append(f"Confidence: {right} of {len(guesses)} answers marked 'Guess' were correct. These are scheduled for earlier revision rather than counted as mastered.")
    half = len(rs) // 2
    if half >= 5:
        a, b = _mean(_frac(r) for r in rs[:half]), _mean(_frac(r) for r in rs[half:])
        if b - a >= 0.1:
            out.append(f"Overall your results improved across this period (from {_pct(a)}% to {_pct(b)}%).")
        elif a - b >= 0.1:
            out.append(f"Your results dipped across this period (from {_pct(a)}% to {_pct(b)}%), partly because questions get harder as you progress. Check the weak areas below.")
    return out or ["Your results are steady across subjects for this period."]


def syllabus_coverage(db: Session) -> list[dict]:
    out = []
    for t in db.execute(select(SyllabusTopic).order_by(SyllabusTopic.subject_id, SyllabusTopic.position)).scalars():
        hist = db.execute(select(func.count(Question.id)).where(Question.topic_id == t.id, Question.approved.is_(True),
                                                                Question.historical_or_generated.in_([ORIGIN_HISTORICAL, ORIGIN_SAMPLE]))).scalar_one()
        gen = db.execute(select(func.count(Question.id)).where(Question.topic_id == t.id, Question.approved.is_(True),
                                                               Question.historical_or_generated.not_in([ORIGIN_HISTORICAL, ORIGIN_SAMPLE]))).scalar_one()
        level = "GOOD" if hist >= 15 else "MODERATE" if hist >= 5 else "LIMITED" if hist >= 1 else "NONE"
        out.append({"subject": t.subject.code, "topic": t.name, "kind": t.kind, "historical": hist, "generated": gen, "level": level})
    return out


def not_yet_assessed(db: Session) -> list[str]:
    attempted = {r.question.plan_item_id for r in rows(db)}
    return [f"{i.code} {i.title}" if i.chapter else i.title for i in db.execute(
        select(LearningPlanItem).where(LearningPlanItem.status != "LOCKED", LearningPlanItem.active.is_(True)).order_by(LearningPlanItem.subject_id, LearningPlanItem.position)
    ).scalars() if i.id not in attempted]


# ------------------------------------------------------------------- readiness ---
READINESS_WEIGHTS = {"coverage": 0.25, "recent": 0.20, "unseen": 0.10, "hsc_difficulty": 0.15, "retention": 0.10, "timed": 0.10, "consistency": 0.10}


def readiness(db: Session) -> dict:
    today = clock.today(st.get(db, "timezone"))
    rs = rows(db)
    recent = [r for r in rs if r.day >= today - timedelta(days=30)]
    plan = [i for i in db.execute(select(LearningPlanItem).where(LearningPlanItem.active.is_(True), LearningPlanItem.enrichment.is_(False),
                                                                    LearningPlanItem.is_assumed_knowledge.is_(False))).scalars()]
    assessed = {r.question.plan_item_id for r in rs}
    mastery = {m.plan_item_id: m.mastery for m in db.execute(select(Mastery)).scalars()}
    cov = _mean((1.0 if i.id in assessed else 0.0) * (0.5 + 0.5 * mastery.get(i.id, 0.5)) for i in plan) or 0.0
    comps = {
        "coverage": cov,
        "recent": _mean(_frac(r) for r in recent),
        "unseen": _mean(_frac(r) for r in recent if r.question.category == "unseen"),
        "hsc_difficulty": _mean(_frac(r) for r in recent if r.question.difficulty >= 2),
        "retention": _mean(_frac(r) for r in rs if r.question.id in _repeated_ids(db)),
        "timed": _mean(1.0 if r.attempt.time_seconds / 60 <= 1.25 * r.question.estimated_minutes else 0.0 for r in recent if r.attempt.time_seconds),
        "consistency": None,
    }
    daily = defaultdict(list)
    for r in recent:
        daily[r.day].append(_frac(r))
    if len(daily) >= 3:
        means = [sum(v) / len(v) for v in daily.values()]
        comps["consistency"] = max(0.0, 1.0 - 2 * statistics.pstdev(means))
    used = {k: v for k, v in comps.items() if v is not None}
    wsum = sum(READINESS_WEIGHTS[k] for k in used) or 1
    score = round(100 * sum(READINESS_WEIGHTS[k] * v for k, v in used.items()) / wsum) if used else 0
    # coverage always counts in full: readiness cannot be high before the course is covered
    if "coverage" in used and wsum < 1:
        score = round(score * (0.5 + 0.5 * cov))
    labels = {"coverage": "Syllabus coverage (topics assessed, weighted by mastery)", "recent": "Recent performance (30 days)",
              "unseen": "Unseen-text performance", "hsc_difficulty": "Performance at HSC difficulty", "retention": "Revision retention (repeat questions)",
              "timed": "Completing questions within exam-style time", "consistency": "Day-to-day consistency"}
    return {
        "score": score, "components": [{"key": k, "label": labels[k], "value": _pct(v), "weight": round(100 * READINESS_WEIGHTS[k])} for k, v in comps.items()],
        "data_points": len(rs),
        "explanation": "HSC READINESS combines the factors below, weighted as shown. Missing factors (not enough data yet) are left out and the "
                       "score is scaled by coverage, so it stays low until the course has been covered. It is a study indicator, not a predicted HSC mark.",
    }


# ------------------------------------------------------------------ summaries ---
def session_summary(db: Session, sess: DailySession) -> dict:
    from app.services.sessions import elapsed, first_attempts

    firsts = first_attempts(db, sess)
    marks: dict[str, list[float]] = {"MATHS": [0, 0], "ENGLISH": [0, 0], "LEGAL": [0, 0]}
    per_item: dict[str, list[float]] = defaultdict(list)
    cats = Counter()
    for sq in sess.questions:
        a = firsts.get(sq.id)
        if not a:
            continue
        marks[sq.subject_code][0] += a.mark_awarded
        marks[sq.subject_code][1] += a.mark_possible
        item = sq.question.plan_item_id and db.get(LearningPlanItem, sq.question.plan_item_id)
        if item:
            per_item[f"{item.code} {item.title}" if item.chapter else item.title].append(a.fraction if not a.skipped else 0)
        for c in (a.feedback.error_categories or []) if a.feedback else []:
            cats[c] += 1
    ranked = sorted(((k, sum(v) / len(v)) for k, v in per_item.items()), key=lambda t: t[1])
    today = sess.session_date
    due = db.execute(select(RevisionQueue).where(RevisionQueue.status == "open", RevisionQueue.due_date <= today + timedelta(days=7))
                     .order_by(RevisionQueue.due_date)).scalars().all()
    rev = []
    for r in due[:5]:
        item = db.get(LearningPlanItem, r.plan_item_id) if r.plan_item_id else None
        rev.append(f"{r.due_date:%a %d %b}: {item.code + ' ' + item.title if item and item.chapter else (item.title if item else 'question revision')}")
    return {
        "minutes": round(elapsed(sess) / 60),
        "marks": {k: f"{v[0]:g}/{v[1]:g}" for k, v in marks.items() if v[1]},
        "strength": f"{ranked[-1][0]} ({round(100 * ranked[-1][1])}%)" if ranked and ranked[-1][1] >= 0.6 else "Keep going — no clear strength today.",
        "main_learning": (f"Most frequent issue today: {cats.most_common(1)[0][0]}." if cats else "No recurring error today."),
        "top_priority": f"{ranked[0][0]} ({round(100 * ranked[0][1])}%)" if ranked and ranked[0][1] < 0.7 else "Continue with your current topics.",
        "revision_scheduled": rev,
    }


def weekly_review(db: Session, end: date | None = None) -> dict:
    end = end or clock.today(st.get(db, "timezone"))
    start = end - timedelta(days=end.weekday())
    sessions = db.execute(select(DailySession).where(DailySession.session_date >= start, DailySession.session_date <= end)).scalars().all()
    rs = [r for r in rows(db, start) if r.day <= end]
    prev = [r for r in rows(db, start - timedelta(days=28)) if r.day < start]
    def by_item(lst):
        d = defaultdict(list)
        for r in lst:
            if r.item:
                d[r.item.id].append(_frac(r))
        return {k: sum(v) / len(v) for k, v in d.items()}
    now_i, prev_i = by_item(rs), by_item(prev)
    improvements = sorted(((now_i[k] - prev_i[k], k) for k in now_i if k in prev_i), reverse=True)
    weak = Counter(e.category for e in db.execute(select(ErrorJournal).where(ErrorJournal.created_at >= datetime.combine(start - timedelta(days=14), datetime.min.time()))).scalars())
    lowest = sorted(now_i.items(), key=lambda kv: kv[1])
    item_name = lambda iid: (lambda i: f"{i.code} {i.title}" if i.chapter else i.title)(db.get(LearningPlanItem, iid))
    due = db.execute(select(func.count(RevisionQueue.id)).where(RevisionQueue.status == "open", RevisionQueue.due_date <= end + timedelta(days=7))).scalar_one()
    return {
        "start": start, "end": end,
        "sessions_completed": sum(1 for s in sessions if s.status == "completed"), "sessions_total": sum(1 for s in sessions if s.status != "skipped"),
        "questions": len(rs), "study_minutes": round(sum(s.elapsed_seconds for s in sessions) / 60),
        "average": _pct(_mean(_frac(r) for r in rs)),
        "strongest_improvement": f"{item_name(improvements[0][1])} (+{round(100 * improvements[0][0])} points)" if improvements and improvements[0][0] > 0.05 else "Not enough comparable data yet.",
        "persistent_weakness": f"{weak.most_common(1)[0][0]} ({weak.most_common(1)[0][1]} times in the last three weeks)" if weak else "None recorded.",
        "next_priority": item_name(lowest[0][0]) if lowest and lowest[0][1] < 0.7 else "Keep building on your current topics.",
        "revision_due": due,
    }


def monthly_review(db: Session) -> dict:
    rep = progress_report(db, "30")
    m = [(db.get(LearningPlanItem, x.plan_item_id), x) for x in db.execute(select(Mastery)).scalars()]
    mastery = sorted(((f"{i.code} {i.title}" if i.chapter else i.title, round(100 * x.mastery), x.attempts) for i, x in m if i), key=lambda t: t[1])
    written = {code: rep["subjects"][code]["average"] for code in ("ENGLISH", "LEGAL")}
    priorities = [t[0] for t in mastery[:3] if t[1] < 65]
    return {
        "report": rep, "readiness": readiness(db), "mastery": mastery, "written_quality": written,
        "priorities": priorities or ["Continue the current learning sequence; no area is below 65% mastery."],
        "time_management": {c: rep["subjects"][c]["time_ratio"] for c in rep["subjects"]},
    }


def dashboard(db: Session) -> dict:
    today = clock.today(st.get(db, "timezone"))
    week_start = today - timedelta(days=today.weekday())
    from app.services.sessions import get_session, progress as sprog, weekday_streak

    sess = get_session(db, today)
    week_rows = rows(db, week_start)
    week_sessions = db.execute(select(DailySession).where(DailySession.session_date >= week_start)).scalars().all()
    plan_status = {}
    for code in SUBJECT_NAMES:
        items = db.execute(select(LearningPlanItem).join(Subject).where(Subject.code == code, LearningPlanItem.active.is_(True))
                           .order_by(LearningPlanItem.position)).scalars().all()
        learning = [i for i in items if i.status == "LEARNING"]
        nxt = next((i for i in items if i.status == "LOCKED" and not i.enrichment), None)
        mastery_vals = [m.mastery for m in db.execute(select(Mastery).where(Mastery.plan_item_id.in_([i.id for i in items]))).scalars()]
        plan_status[code] = {"learning": learning, "next": nxt, "mastery": _pct(_mean(mastery_vals))}
    due = db.execute(select(RevisionQueue).where(RevisionQueue.status == "open", RevisionQueue.due_date <= today).order_by(RevisionQueue.due_date)).scalars().all()
    masteries = sorted(((db.get(LearningPlanItem, m.plan_item_id), m) for m in db.execute(select(Mastery).where(Mastery.attempts >= 2)).scalars()), key=lambda t: t[1].mastery)
    weak = [(i, m) for i, m in masteries if m.mastery < 0.6][:5]
    rep7, rep30 = progress_report(db, "7"), progress_report(db, "30")
    improve = []
    for code in SUBJECT_NAMES:
        a, b = rep30["subjects"][code]["average"], rep7["subjects"][code]["average"]
        if a is not None and b is not None and b - a >= 5:
            improve.append(f"{SUBJECT_NAMES[code]}: {a}% → {b}% this week")
    missed = db.execute(select(DailySession).where(DailySession.status == "missed").order_by(DailySession.session_date.desc())).scalars().all()
    return {
        "today": today, "session": sess, "session_progress": sprog(sess) if sess and sess.questions else None,
        "is_study_day": today.weekday() in (st.get(db, "weekdays") or [0, 1, 2, 3, 4]),
        "streak": weekday_streak(db, today),
        "week": {"questions": len(week_rows), "minutes": round(sum(s.elapsed_seconds for s in week_sessions) / 60), "average": _pct(_mean(_frac(r) for r in week_rows))},
        "plan_status": plan_status, "revision_due": due, "weak": weak, "improvement": improve, "missed": missed,
        "readiness": readiness(db)["score"],
    }
