"""Progress analytics, HSC readiness, the end-of-day summary, the Friday weekly review, the
monthly review and the dashboard (owner: analytics).

* Data: ``analytics_data.Dataset`` loads every counted attempt once per page (first honest
  attempts only — see that module), so each page runs a handful of queries however long the
  history is.
* Interpretation: ``analytics_insights`` (specific, evidence-based statements that are only
  made with enough data).
* Question bank health and historical coverage (spec 45): ``analytics_bank``.

Public functions keep their v1 names: ``progress_report``, ``readiness``, ``session_summary``,
``weekly_review``, ``monthly_review``, ``dashboard``, ``syllabus_coverage``,
``not_yet_assessed``."""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Attempt,
    AttemptFeedback,
    DailySession,
    ErrorJournal,
    LearningPlanItem,
    QuestionExposure,
    RevisionQueue,
    SessionQuestion,
)
from app.models.common import DAILY_COUNTS
from app.services.analytics_bank import bank_health, historical_coverage
from app.services.analytics_data import DIFFICULTY_NAMES, SUBJECT_NAMES, SUBJECT_SHORT, Dataset, Fact, mean, pct
from app.services.analytics_insights import insights, not_enough_message

WINDOWS = {"7": 7, "30": 30, "60": 60, "90": 90, "all": None}
WINDOW_LABELS = {"7": "the last 7 days", "30": "the last 30 days", "60": "the last 60 days", "90": "the last 90 days", "all": "all time"}
TYPE_LABELS = {"mcq": "Multiple choice", "short_answer": "Short answer", "stimulus": "Stimulus-based", "extended": "Extended response",
               "working": "Working", "self": "Self-marked"}


def _ds(db: Session, ds: Dataset | None = None) -> Dataset:
    return ds if ds is not None else Dataset(db)


def _avg(facts: list[Fact]) -> float | None:
    return mean(f.frac for f in facts)


def _next_study_day(d: date, weekdays: list[int]) -> date:
    for _ in range(8):
        if d.weekday() in weekdays:
            return d
        d += timedelta(days=1)
    return d


def _weekdays(ds: Dataset) -> list[int]:
    return ds.settings.get("weekdays") or [0, 1, 2, 3, 4]


def _rows(groups: dict, name, min_n: int = 1) -> list[dict]:
    out = [{"label": name(k), "pct": pct(_avg(v)), "n": len(v), "key": k} for k, v in groups.items() if len(v) >= min_n]
    return sorted(out, key=lambda r: (r["pct"] if r["pct"] is not None else 0, -r["n"]))


def _group(facts: list[Fact], key) -> dict:
    out: dict = defaultdict(list)
    for f in facts:
        k = key(f)
        if k is not None:
            out[k].append(f)
    return out


# ------------------------------------------------------------------ progress ---
def subject_metrics(ds: Dataset, facts: list[Fact], code: str) -> dict:
    lst = [f for f in facts if f.subject == code]
    auto = [f for f in lst if f.auto]
    written = [f for f in lst if not f.auto and not f.mcq and not f.skipped]
    timed = [f for f in lst if f.seconds and not f.skipped]
    ratios = sorted(f.seconds / 60 / f.est_minutes for f in timed if f.est_minutes)
    reps = [f for f in lst if f.repeat]
    first: dict[int, Fact] = {}
    for f in ds.facts:
        first.setdefault(f.question_id, f)
    first_of_reps = [first[f.question_id] for f in reps if first.get(f.question_id) is not f]
    from app.services.analytics_insights import model_words

    models = model_words(ds, {f.question_id for f in written}) if written else {}
    with_model = [f for f in written if models.get(f.question_id)]
    formats: list[dict] = []
    if code == "MATHS":
        formats.append({"title": "By marks", "rows": _rows(_group(lst, lambda f: f.marks if f.marks < 4 else 4),
                                                           lambda k: f"{k} mark{'s' if k > 1 else ''}" if k < 4 else "4+ marks")})
    elif code == "ENGLISH":
        unseen = [f for f in lst if f.category != "course"]
        formats.append({"title": "By text form (unseen)", "rows": _rows(_group(unseen, lambda f: f.form), str)})
        formats.append({"title": "By directive verb", "rows": _rows(_group(lst, lambda f: (f.verb or "").capitalize() or None), str)})
        formats.append({"title": "By marks", "rows": _rows(_group(lst, lambda f: f.marks), lambda k: f"{k} marks")})
        formats.append({"title": "Unseen and course-linked", "rows": _rows(_group(lst, lambda f: "Course-linked" if f.category == "course"
                                                                                   else "Unseen texts"), str)})
    else:
        formats.append({"title": "By question type", "rows": _rows(_group(lst, lambda f: "mcq" if f.mcq else f.qtype),
                                                                   lambda k: TYPE_LABELS.get(k, k.replace("_", " ").capitalize()))})
        formats.append({"title": "Core and options", "rows": _rows(_group(lst, lambda f: "Option topics" if f.category == "option"
                                                                           else "Core"), str)})
    errors = Counter(c for f in lst for c in f.errors)
    return {
        "name": SUBJECT_NAMES[code], "code": code, "answers": len(lst), "skipped": sum(1 for f in lst if f.skipped),
        "average": pct(_avg(lst)),
        "marks": f"{sum(f.mark for f in lst):g}/{sum(f.possible for f in lst):g}" if lst else "—",
        "accuracy": pct(mean(1.0 if f.frac >= 0.85 else 0.0 for f in auto)), "accuracy_n": len(auto),
        "estimated": sum(1 for f in lst if f.estimated),
        "topics": _rows(_group(lst, lambda f: f.plan_item_id), ds.item_name),
        "areas": _rows(_group(lst, lambda f: f.area_id), ds.area_name),
        "difficulty": sorted(_rows(_group(lst, lambda f: f.difficulty), lambda k: DIFFICULTY_NAMES.get(k, str(k))), key=lambda r: r["key"]),
        "formats": [f for f in formats if f["rows"]],
        "avg_minutes": round(mean(f.seconds / 60 for f in timed), 1) if timed else None,
        "time_ratio": round(ratios[len(ratios) // 2], 2) if ratios else None,
        "within_time": pct(mean(1.0 if f.timed_ok else 0.0 for f in timed)),
        "avg_words": round(mean(f.words for f in written)) if written else None,
        "model_words": round(mean(models[f.question_id] for f in with_model)) if with_model else None,
        "revision": pct(_avg(reps)), "revision_n": len(reps), "revision_first": pct(_avg(first_of_reps)),
        "errors": errors.most_common(5),
    }


def progress_report(db: Session, window: str = "30", ds: Dataset | None = None) -> dict:
    ds = _ds(db, ds)
    if window not in WINDOWS:
        window = "30"
    since = ds.since(WINDOWS[window])
    facts = ds.window(since)
    subjects = {code: subject_metrics(ds, facts, code) for code in SUBJECT_NAMES}
    found = insights(ds, facts)
    reps = [f for f in facts if f.repeat]
    item_groups = {k: v for k, v in _group(facts, lambda f: f.plan_item_id).items() if len(v) >= 3}
    ranked = sorted(item_groups.items(), key=lambda kv: _avg(kv[1]))
    def item_row(k, v):
        return {"name": ds.item_name(k), "subject": ds.item_subject(k), "pct": pct(_avg(v)), "n": len(v)}
    strongest = [item_row(k, v) for k, v in reversed(ranked) if _avg(v) >= 0.7][:5]
    weakest = [item_row(k, v) for k, v in ranked if _avg(v) < 0.6][:5]
    err_items: dict[tuple, Counter] = defaultdict(Counter)
    for f in facts:
        for c in f.errors:
            err_items[(f.subject, c)][f.plan_item_id] += 1
    repeated = sorted(((s, c, sum(cnt.values()), [ds.item_name(i) for i, _ in cnt.most_common(2)]) for (s, c), cnt in err_items.items()
                       if sum(cnt.values()) >= 2), key=lambda t: -t[2])[:10]
    return {
        "window": window, "window_label": WINDOW_LABELS[window], "since": since, "total_attempts": len(facts),
        "days_active": len({f.day for f in facts}), "subjects": subjects,
        "insights": [i.as_dict() for i in found], "interpretation": [i.line for i in found] or [not_enough_message(len(facts))],
        "not_enough": None if found or len(facts) >= 10 else not_enough_message(len(facts)),
        "strongest": strongest, "weakest": weakest,
        "revision_performance": pct(_avg(reps)), "revision_n": len(reps),
        "repeated_errors": repeated, "syllabus": syllabus_assessment(ds), "coverage": historical_coverage(db),
        "not_assessed": not_yet_assessed(db, ds),
        "estimated": sum(1 for f in facts if f.estimated),
    }


# ------------------------------------------------------------------ syllabus ---
def _course_items(ds: Dataset, include_locked: bool = True) -> dict[str, list[LearningPlanItem]]:
    enrich = bool(ds.settings.get("enrichment_enabled"))
    out: dict[str, list[LearningPlanItem]] = defaultdict(list)
    for i in sorted(ds.items.values(), key=lambda x: (x.subject_id, x.position)):
        if not i.active or (i.enrichment and not enrich):
            continue
        topic = ds.areas.get(i.topic_id) if i.topic_id else None
        if topic is not None and not topic.examinable:
            continue
        if not include_locked and i.status == "LOCKED":
            continue
        out[ds.subject_codes.get(i.subject_id, "?")].append(i)
    return out


def syllabus_assessment(ds: Dataset) -> dict[str, dict]:
    """Spec 21 'syllabus coverage' / 'topics not yet assessed': which plan items have counted answers."""
    assessed = Counter(f.plan_item_id for f in ds.facts if f.plan_item_id)
    out = {}
    for code, items in _course_items(ds).items():
        if code not in SUBJECT_NAMES:
            continue
        unlocked = [i for i in items if i.status != "LOCKED"]
        done = [i for i in unlocked if assessed.get(i.id)]
        out[code] = {"total": len(items), "unlocked": len(unlocked), "assessed": len(done),
                     "locked": len(items) - len(unlocked), "pct_course": pct(len(done) / len(items)) if items else None,
                     "not_assessed": [ds.item_name(i.id) for i in unlocked if not assessed.get(i.id)]}
    return out


def not_yet_assessed(db: Session, ds: Dataset | None = None) -> list[str]:
    ds = _ds(db, ds)
    return [n for s in syllabus_assessment(ds).values() for n in s["not_assessed"]]


def syllabus_coverage(db: Session) -> list[dict]:
    """Historical question coverage per syllabus area (spec 45); kept under its v1 name."""
    return historical_coverage(db)


# ------------------------------------------------------------------ readiness ---
QUALITY_WEIGHTS = {"recent": 0.25, "hsc_difficulty": 0.20, "unseen": 0.10, "retention": 0.15, "timed": 0.15, "consistency": 0.15}
MIN_ANSWERS, MIN_DAYS = 20, 3
LEGAL_OPTIONS_REQUIRED = 2
READINESS_LABELS = {
    "recent": "Recent performance (last 30 days)",
    "hsc_difficulty": "Performance on HSC-standard and challenging questions (60 days)",
    "unseen": "Unseen-text performance (English, 60 days)",
    "retention": "Revision retention (questions met again, 90 days)",
    "timed": "Timed performance (answers over 1.25× exam time count half)",
    "consistency": "Consistency (regular practice and steady results, 4 weeks)",
}
MIN_N = {"recent": 10, "hsc_difficulty": 8, "unseen": 3, "retention": 5, "timed": 10, "consistency": 5}
BANDS = ((75, "Well prepared"), (50, "Consolidating"), (25, "Developing"), (0, "Early stage"))


def course_coverage(ds: Dataset) -> dict:
    """Share of the whole 2027 course assessed, each subject weighted equally. A topic counts in
    full after three counted answers and is weighted by how well those answers went."""
    by_item = _group(ds.facts, lambda f: f.plan_item_id)
    subjects = {}
    for code in SUBJECT_NAMES:
        items = _course_items(ds).get(code, [])
        values = []
        for i in items:
            fs = by_item.get(i.id, [])
            if not fs:
                values.append(0.0)
                continue
            quality = _avg(fs[-5:]) or 0.0
            values.append(min(1.0, len(fs) / 3) * (0.5 + 0.5 * quality))
        if code == "LEGAL":
            active_opts = sum(1 for i in items if (ds.areas.get(i.topic_id).is_option if i.topic_id and ds.areas.get(i.topic_id) else False))
            values += [0.0] * max(0, LEGAL_OPTIONS_REQUIRED - active_opts)  # options not chosen yet still have to be covered
        assessed = sum(1 for i in items if by_item.get(i.id))
        subjects[code] = {"coverage": mean(values) or 0.0, "assessed": assessed, "total": len(values),
                          "locked_share": (sum(1 for i in items if i.status == "LOCKED") / len(items)) if items else 0.0}
    return {"overall": mean(s["coverage"] for s in subjects.values()) or 0.0, "subjects": subjects}


def _consistency(ds: Dataset) -> tuple[float | None, int, str]:
    end = ds.today - timedelta(days=1)
    start = max(ds.today - timedelta(days=28), ds.year_start or ds.today - timedelta(days=28))
    scheduled = ds.study_days(start, end)
    if len(scheduled) < MIN_N["consistency"]:
        return None, len(scheduled), ""
    by_day = _group([f for f in ds.facts if start <= f.day <= end], lambda f: f.day)
    attendance = sum(1 for d in scheduled if d in by_day) / len(scheduled)
    means = [_avg(v) for v in by_day.values()]
    if len(means) >= 5:
        stability = max(0.0, 1.0 - 2 * statistics.pstdev(means))
        return 0.5 * attendance + 0.5 * stability, len(scheduled), (f"practised on {sum(1 for d in scheduled if d in by_day)} of "
                                                                    f"{len(scheduled)} study days; daily results steady to {pct(stability)}%")
    return attendance, len(scheduled), f"practised on {sum(1 for d in scheduled if d in by_day)} of {len(scheduled)} study days"


def readiness(db: Session, ds: Dataset | None = None) -> dict:
    ds = _ds(db, ds)
    t = ds.today
    recent = ds.window(ds.since(30))
    last60 = ds.window(ds.since(60))
    last90 = ds.window(ds.since(90))
    groups = {
        "recent": recent,
        "hsc_difficulty": [f for f in last60 if f.difficulty >= 2],
        "unseen": [f for f in last60 if f.subject == "ENGLISH" and f.category == "unseen"],
        "retention": [f for f in last90 if f.repeat],
        "timed": [f for f in recent if f.seconds and not f.skipped],
    }
    values: dict[str, float | None] = {}
    ns: dict[str, int] = {}
    for k, fs in groups.items():
        ns[k] = len(fs)
        if len(fs) < MIN_N[k]:
            values[k] = None
        elif k == "timed":
            values[k] = mean(f.frac if f.timed_ok else 0.5 * f.frac for f in fs)
        else:
            values[k] = _avg(fs)
    values["consistency"], ns["consistency"], cons_detail = _consistency(ds)
    used = {k: v for k, v in values.items() if v is not None}
    wsum = sum(QUALITY_WEIGHTS[k] for k in used)
    quality = sum(QUALITY_WEIGHTS[k] * v for k, v in used.items()) / wsum if wsum else None
    cov = course_coverage(ds)
    days = len({f.day for f in ds.facts})
    enough = len(ds.facts) >= MIN_ANSWERS and days >= MIN_DAYS and quality is not None
    raw = 100 * cov["overall"] * quality if enough else None
    score = int(5 * round(raw / 5)) if raw is not None else None
    band = next(label for lo, label in BANDS if score is None or score >= lo) if score is not None else None
    components = [{"key": k, "label": READINESS_LABELS[k], "value": pct(values[k]), "n": ns.get(k, 0), "min_n": MIN_N[k],
                   "weight": round(100 * QUALITY_WEIGHTS[k]), "detail": cons_detail if k == "consistency" else ""}
                  for k in QUALITY_WEIGHTS]
    subjects = {}
    for code in SUBJECT_NAMES:
        fs = [f for f in last60 if f.subject == code]
        c = cov["subjects"][code]
        subjects[code] = {"name": SUBJECT_NAMES[code], "coverage": pct(c["coverage"]), "assessed": c["assessed"], "total": c["total"],
                          "recent": pct(_avg(fs)) if len(fs) >= 5 else None, "n": len(fs)}
    summary = []
    if not enough:
        summary.append(f"Not enough data yet: readiness is shown after {MIN_ANSWERS} counted answers on at least {MIN_DAYS} different days "
                       f"(so far {len(ds.facts)} answers on {days} day{'s' if days != 1 else ''}).")
    else:
        summary.append(f"You have been assessed on about {pct(cov['overall'])}% of the 2027 course, and the quality of those answers is "
                       f"{pct(quality)}%, so readiness is about {score if score else 'under 5'}/100 ({band.lower()}).")
        locked = mean(s["locked_share"] for s in cov["subjects"].values()) or 0
        if cov["overall"] < 0.35:
            summary.append("It is low mainly because most of the course has not been assessed yet" +
                           (f" — about {pct(locked)}% of the learning plan is still to be taught, so this is expected." if locked >= 0.4 else
                            ": the topics you have studied need more questions answered."))
        weakest = min(used.items(), key=lambda kv: kv[1])
        strongest = max(used.items(), key=lambda kv: kv[1])
        if weakest[0] != strongest[0]:
            summary.append(f"Strongest factor: {READINESS_LABELS[strongest[0]].split(' (')[0].lower()} ({pct(strongest[1])}%). "
                           f"Weakest: {READINESS_LABELS[weakest[0]].split(' (')[0].lower()} ({pct(weakest[1])}%).")
        missing = [READINESS_LABELS[k].split(" (")[0].lower() for k, v in values.items() if v is None]
        if missing:
            summary.append("Not yet included (too few answers): " + ", ".join(missing) + ".")
    return {
        "score": score, "display": (str(score) if score else "under 5") if score is not None else None, "band": band,
        "raw": round(raw, 1) if raw is not None else None, "enough": enough,
        "coverage": pct(cov["overall"]), "quality": pct(quality), "components": components, "subjects": subjects,
        "data_points": len(ds.facts), "summary": summary,
        "explanation": "HSC READINESS = course coverage × answer quality. Coverage is the share of the whole 2027 course you have been "
                       "assessed on, each subject counting equally (a topic counts in full after three answers and is weighted by how "
                       "well they went; Legal options you have not chosen yet count as uncovered). Quality is the weighted average of the "
                       "factors below; a factor is left out until it has enough answers. Only answers that count are used: first "
                       "attempts — not retries, practice after the answer was shown, or answers still waiting for a self-mark. The "
                       "result is rounded to the nearest 5 because every input is an estimate. It stays low until the course has been "
                       "covered, and it is a study indicator, not a predicted HSC mark.",
    }


# ------------------------------------------------------------------ sessions ---
def session_minutes(db: Session, sess: DailySession, q_seconds: int | None = None) -> tuple[int, bool]:
    """Active study minutes for a session, and whether the timer value was capped. A timer
    left running while the student was away is capped at the time recorded on the questions
    plus 15 minutes."""
    try:
        from app.services.sessions import elapsed

        el = int(elapsed(sess))
    except Exception:
        el = int(sess.elapsed_seconds or 0)
    if q_seconds is None:
        q_seconds = db.execute(select(func.coalesce(func.sum(SessionQuestion.time_spent_seconds), 0))
                               .where(SessionQuestion.session_id == sess.id)).scalar_one() or 0
    if q_seconds and el > 2 * q_seconds and el > q_seconds + 30 * 60:
        return round((q_seconds + 15 * 60) / 60), True
    if not el and q_seconds:
        return round(q_seconds / 60), False
    return round(el / 60), False


def _session_attempts(db: Session, sess: DailySession) -> dict[int, Attempt]:
    ids = [q.id for q in sess.questions]
    out: dict[int, Attempt] = {}
    if ids:
        for a in db.execute(select(Attempt).where(Attempt.session_question_id.in_(ids)).order_by(Attempt.attempt_number, Attempt.id)).scalars():
            out.setdefault(a.session_question_id, a)
    return out


def _lost_lesson(db: Session, ds: Dataset, a: Attempt, item_name: str) -> str | None:
    """A one-sentence learning from an answer that lost marks, from its feedback."""
    p = (a.feedback.payload if a.feedback else None) or {}
    journal = db.execute(select(ErrorJournal.category, ErrorJournal.description).where(ErrorJournal.attempt_id == a.id)).first()
    text = None
    if p.get("kind") == "maths":
        # the key idea is the transferable learning; the divergence note is used when there is none
        text = f"Key idea: {p['concept']}" if p.get("concept") else p.get("divergence")
    elif p.get("kind") == "mcq":
        text = p.get("explanation") or p.get("concept")
    else:
        r = p.get("result") or {}
        candidates = [*(r.get("missing_elements") or [])[:1], *(r.get("improvements") or [])[:1], r.get("next_level")]
        # skip pointers to other parts of the feedback screen ("listed under …"): they mean nothing here
        text = next((c for c in candidates if isinstance(c, str) and c.strip() and "listed under" not in c), None)
    if not text and journal:
        text = journal.description
    if not text:
        return None
    cat = f" ({journal.category})" if journal and journal.category else ""
    text = " ".join(str(text).split())
    if len(text) > 260:
        text = text[:257].rsplit(" ", 1)[0] + "…"
    return f"{item_name}{cat}: {text}"


def session_summary(db: Session, sess: DailySession, ds: Dataset | None = None) -> dict:
    """End-of-day summary (spec 47): time, marks per subject, then strength, main learning, top
    priority and the revision scheduled from today's answers."""
    ds = _ds(db, ds)
    weekdays = _weekdays(ds)
    firsts = _session_attempts(db, sess)
    marks = {c: [0.0, 0.0, 0, 0] for c in SUBJECT_NAMES}  # awarded, possible, answered, total
    per_item: dict[int, list[Attempt]] = defaultdict(list)
    q_seconds = 0
    skipped = 0
    for sq in sess.questions:
        m = marks.setdefault(sq.subject_code, [0.0, 0.0, 0, 0])
        m[3] += 1
        a = firsts.get(sq.id)
        q_seconds += max(sq.time_spent_seconds or 0, a.time_seconds if a else 0)
        if not a:
            continue
        m[0] += a.mark_awarded
        m[1] += a.mark_possible
        m[2] += 1
        skipped += 1 if a.skipped else 0
        if sq.question.plan_item_id:
            per_item[sq.question.plan_item_id].append(a)
    minutes, capped = session_minutes(db, sess, q_seconds)

    def frac(lst):
        return sum(0 if x.skipped else x.mark_awarded for x in lst) / max(1e-9, sum(x.mark_possible for x in lst))
    ranked = sorted(per_item.items(), key=lambda kv: (frac(kv[1]), sum(x.mark_possible for x in kv[1])))
    before = _group([f for f in ds.facts if f.day < sess.session_date], lambda f: f.plan_item_id)
    # strength
    strength = "No clear strength today — every topic lost marks somewhere. That is useful information, not a verdict."
    if ranked:
        k, lst = max(ranked, key=lambda kv: (frac(kv[1]), sum(x.mark_possible for x in kv[1])))
        if frac(lst) >= 0.75:
            got, of = sum(x.mark_awarded for x in lst), sum(x.mark_possible for x in lst)
            prev = before.get(k, [])
            trend = ""
            if len(prev) >= 2 and frac(lst) - (_avg(prev) or 0) >= 0.15:
                trend = f", up from {pct(_avg(prev))}% before today"
            strength = f"{ds.item_name(k)}: {got:g}/{of:g} marks across {len(lst)} question{'s' if len(lst) != 1 else ''}{trend}."
    # main learning: the answer that lost the most marks, explained by its own feedback
    lost = sorted((a for a in firsts.values() if not a.skipped and a.mark_possible - a.mark_awarded > 0),
                  key=lambda a: -(a.mark_possible - a.mark_awarded))
    main = None
    cats = Counter(c for a in firsts.values() if a.feedback for c in (a.feedback.error_categories or []))
    for a in lost[:3]:
        main = _lost_lesson(db, ds, a, ds.item_name(a.question.plan_item_id))
        if main:
            break
    if main and cats and cats.most_common(1)[0][1] >= 2:
        c, n = cats.most_common(1)[0]
        main += f" The same issue — {c} — came up {n} times today."
    if not main:
        main = ("Everything you answered was right today." if firsts and not lost and not skipped else
                "No marks were lost on answered questions." if firsts else "No answers yet.")
    # top priority: weakest topic today, flagged as persistent if it was weak before too
    priority = "Continue with your current topics: nothing today fell below 60%."
    if ranked and frac(ranked[0][1]) < 0.6:
        k, lst = ranked[0]
        prev = before.get(k, [])
        due = db.execute(select(func.min(RevisionQueue.due_date)).where(RevisionQueue.plan_item_id == k, RevisionQueue.status == "open",
                                                                        RevisionQueue.due_date > sess.session_date)).scalar_one()
        persistent = len(prev) >= 3 and (_avg(prev) or 0) < 0.6
        priority = (f"{ds.item_name(k)} — {pct(frac(lst))}% today" + (f" and {pct(_avg(prev))}% across {len(prev)} earlier answers: a persistent "
                                                                    "gap. Re-read the worked solutions before the next session." if persistent
                                                                    else ". Go through today's feedback on it before tomorrow."))
        if due:
            priority += f" A different question on it is scheduled for {_next_study_day(due, weekdays):%a %d %b}."
    # revision scheduled from today's answers
    rev = []
    for k, _lst in sorted(per_item.items(), key=lambda kv: frac(kv[1])):
        due = db.execute(select(RevisionQueue.due_date, RevisionQueue.reason).where(
            RevisionQueue.plan_item_id == k, RevisionQueue.status == "open", RevisionQueue.due_date > sess.session_date)
            .order_by(RevisionQueue.due_date)).first()
        if due and (due.due_date - sess.session_date).days <= 21:
            rev.append(f"{ds.item_name(k)}: practice with a different question from {_next_study_day(due.due_date, weekdays):%a %d %b}.")
    nexts = []
    for a in firsts.values():
        sched = ((a.feedback.payload if a.feedback else None) or {}).get("schedule") or {}
        if sched.get("next_revision"):
            try:
                nexts.append(date.fromisoformat(sched["next_revision"]))
            except ValueError:
                pass
    if nexts:
        rev.append(f"Today's {len(nexts)} questions return for exact revision between {min(nexts):%d %b} and {max(nexts):%d %b} "
                   "(sooner for the ones that lost marks).")
    return {
        "v": 2, "minutes": minutes, "minutes_capped": capped,
        "marks": {c: f"{m[0]:g}/{m[1]:g}" for c, m in marks.items() if m[1]},
        "subjects": {c: {"awarded": round(m[0], 1), "possible": m[1], "pct": round(100 * m[0] / m[1]) if m[1] else None,
                         "answered": m[2], "total": m[3]} for c, m in marks.items() if m[3]},
        "skipped": skipped, "answered": sum(m[2] for m in marks.values()), "total": sum(m[3] for m in marks.values()),
        "strength": strength, "main_learning": main, "top_priority": priority, "revision_scheduled": rev[:5],
    }


# ------------------------------------------------------------------ weekly ---
def _sessions_between(db: Session, start: date, end: date) -> list[DailySession]:
    return list(db.execute(select(DailySession).where(DailySession.session_date >= start, DailySession.session_date <= end)
                           .order_by(DailySession.session_date)).scalars())


def _q_seconds(db: Session, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    return {sid: int(s or 0) for sid, s in db.execute(select(SessionQuestion.session_id, func.sum(SessionQuestion.time_spent_seconds))
                                                       .where(SessionQuestion.session_id.in_(ids)).group_by(SessionQuestion.session_id)).all()}


def _answered_counts(db: Session, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    return dict(db.execute(select(SessionQuestion.session_id, func.count(SessionQuestion.id)).where(
        SessionQuestion.session_id.in_(ids), SessionQuestion.status.in_(("submitted", "skipped"))).group_by(SessionQuestion.session_id)).all())


def study_minutes(db: Session, sessions: list[DailySession]) -> int:
    qs = _q_seconds(db, [s.id for s in sessions])
    return sum(session_minutes(db, s, qs.get(s.id, 0))[0] for s in sessions)


def _revision_coming(db: Session, ds: Dataset, start: date, end: date) -> tuple[int, list[str], int]:
    weekdays = _weekdays(ds)
    rows = db.execute(select(RevisionQueue.plan_item_id, func.min(RevisionQueue.due_date)).where(
        RevisionQueue.status == "open", RevisionQueue.due_date <= end, RevisionQueue.plan_item_id.is_not(None))
        .group_by(RevisionQueue.plan_item_id).order_by(func.min(RevisionQueue.due_date))).all()
    lines = []
    for item_id, due in rows[:6]:
        when = "now (overdue)" if due < start else f"{_next_study_day(due, weekdays):%a %d %b}"
        lines.append(f"{ds.item_name(item_id)} — {when}")
    exact = db.execute(select(func.count(QuestionExposure.id)).where(QuestionExposure.next_revision_date >= start,
                                                                       QuestionExposure.next_revision_date <= end)).scalar_one()
    return len(rows), lines, exact


def weekly_review(db: Session, end: date | None = None, ds: Dataset | None = None) -> dict:
    """THIS WEEK (spec 48), shown at the end of Friday's session and on /progress/week."""
    ds = _ds(db, ds)
    end = end or ds.today
    start = end - timedelta(days=end.weekday())
    weekdays = _weekdays(ds)
    sess = _sessions_between(db, start, end)
    by_date = {s.session_date: s for s in sess}
    answered = _answered_counts(db, [s.id for s in sess])
    scheduled = [d for d in ds.study_days(start, end) if not ds.year_start or d >= ds.year_start]
    completed = [s for s in sess if s.status == "completed"]
    partial = [s for s in sess if s.status != "completed" and answered.get(s.id)]
    missed = [d for d in scheduled if d < ds.today and (d not in by_date or (by_date[d].status in ("missed", "skipped")
                                                                             and not answered.get(by_date[d].id)))]
    week = ds.window(start, end)
    prior = ds.window(start - timedelta(days=28), start - timedelta(days=1))
    now_i = _group(week, lambda f: f.plan_item_id)
    prev_i = _group(prior, lambda f: f.plan_item_id)
    gains = sorted(((_avg(v) - _avg(prev_i[k]), k) for k, v in now_i.items() if len(v) >= 2 and len(prev_i.get(k, [])) >= 2),
                   key=lambda t: -t[0])
    if gains and gains[0][0] >= 0.10:
        g, k = gains[0]
        improvement = (f"{ds.item_name(k)}: {pct(_avg(prev_i[k]))}% → {pct(_avg(now_i[k]))}% ({len(now_i[k])} question"
                       f"{'s' if len(now_i[k]) != 1 else ''} this week, {len(prev_i[k])} in the four weeks before).")
    else:
        subj_gain = []
        for code in SUBJECT_NAMES:
            a = [f for f in prior if f.subject == code]
            b = [f for f in week if f.subject == code]
            if len(a) >= 5 and len(b) >= 5 and _avg(b) - _avg(a) >= 0.08:
                subj_gain.append((_avg(b) - _avg(a), code, _avg(a), _avg(b)))
        if subj_gain:
            _, code, a, b = max(subj_gain)
            improvement = f"{SUBJECT_NAMES[code]}: {pct(a)}% over the previous four weeks → {pct(b)}% this week."
        elif not prior:
            improvement = "Your first week — improvement is measured from next week, once there is a week to compare with."
        else:
            improvement = "No clear improvement this week compared with the four weeks before — no topic rose by 10 points or more."
    # persistent weakness: an error type that recurs across weeks
    three = ds.window(start - timedelta(days=14), end)
    weeks_of: dict[tuple, set] = defaultdict(set)
    counts: Counter = Counter()
    for f in three:
        for c in f.errors:
            weeks_of[(f.subject, c)].add((f.day - (start - timedelta(days=14))).days // 7)
            counts[(f.subject, c)] += 1
    persistent = sorted((k for k in counts if len(weeks_of[k]) >= 2 and counts[k] >= 3), key=lambda k: (-len(weeks_of[k]), -counts[k]))
    if persistent:
        s, c = persistent[0]
        weak_items = Counter(f.plan_item_id for f in three if c in f.errors).most_common(1)
        weakness = (f"{SUBJECT_SHORT[s]} — {c}: {counts[(s, c)]} times in {len(weeks_of[(s, c)])} of the last 3 weeks"
                    + (f", most often in {ds.item_name(weak_items[0][0])}." if weak_items else "."))
    else:
        low = sorted(((k, v) for k, v in _group(three, lambda f: f.plan_item_id).items()
                      if len(v) >= 3 and (_avg(v) or 0) < 0.6 and len({(f.day - start).days // 7 for f in v}) >= 2), key=lambda kv: _avg(kv[1]))
        weakness = (f"{ds.item_name(low[0][0])}: {pct(_avg(low[0][1]))}% across {len(low[0][1])} answers over the last 3 weeks."
                    if low else "Nothing has persisted: no error type or topic stayed weak across more than one week.")
    # next week's priority
    weak_now = sorted(((k, v) for k, v in now_i.items() if len(v) >= 2 and (_avg(v) or 0) < 0.6), key=lambda kv: _avg(kv[1]))
    if persistent:
        s, c = persistent[0]
        priority = f"Work on '{c}' in {SUBJECT_NAMES[s]}: it has recurred across weeks."
        if weak_now:
            priority += f" Start with {ds.item_name(weak_now[0][0])} ({pct(_avg(weak_now[0][1]))}% this week)."
    elif weak_now:
        k, v = weak_now[0]
        priority = f"{ds.item_name(k)} — {pct(_avg(v))}% across {len(v)} questions this week."
    else:
        priority = "Keep building on your current topics; nothing this week fell below 60%."
    due_n, due_lines, exact = _revision_coming(db, ds, end + timedelta(days=1), end + timedelta(days=7))
    found = insights(ds, week, limit=3)
    return {
        "start": start, "end": end, "sessions_completed": len(completed), "sessions_total": len(scheduled),
        "sessions_partial": len(partial), "sessions_missed": len(missed),
        "questions": len(week), "skipped": sum(1 for f in week if f.skipped),
        "study_minutes": study_minutes(db, sess), "average": pct(_avg(week)),
        "subject_averages": {c: pct(_avg([f for f in week if f.subject == c])) for c in SUBJECT_NAMES if any(f.subject == c for f in week)},
        "strongest_improvement": improvement, "persistent_weakness": weakness, "next_priority": priority,
        "revision_due": due_n, "revision_lines": due_lines, "exact_repeats": exact,
        "insights": [i.line for i in found],
        "is_friday_review": end.weekday() == max(weekdays),
    }


# ------------------------------------------------------------------ monthly ---
def monthly_review(db: Session, ds: Dataset | None = None) -> dict:
    """Monthly review (spec 49): the last 30 days compared with the 30 before, interpreted."""
    ds = _ds(db, ds)
    rep = progress_report(db, "30", ds)
    month = ds.window(ds.since(30))
    prev = ds.window(ds.since(60), ds.since(30) - timedelta(days=1))
    # coverage this month
    first_day: dict[int, date] = {}
    for f in ds.facts:
        if f.plan_item_id:
            first_day.setdefault(f.plan_item_id, f.day)
    new_topics = [ds.item_name(k) for k, d in first_day.items() if d >= ds.since(30)]
    cov = course_coverage(ds)
    # topic mastery (recent answers per topic) with change against the previous month
    cur_i = _group(month, lambda f: f.plan_item_id)
    prev_i = _group(prev, lambda f: f.plan_item_id)
    mastery = []
    for k, v in cur_i.items():
        if len(v) < 2:
            continue
        p = prev_i.get(k, [])
        change = pct(_avg(v) - _avg(p)) if len(p) >= 2 else None
        mastery.append({"name": ds.item_name(k), "subject": ds.item_subject(k), "pct": pct(_avg(v)), "n": len(v), "change": change})
    mastery.sort(key=lambda r: r["pct"])
    # improvement per subject
    improvement = []
    for code in SUBJECT_NAMES:
        a = [f for f in prev if f.subject == code]
        b = [f for f in month if f.subject == code]
        if len(a) >= 5 and len(b) >= 5:
            d = _avg(b) - _avg(a)
            word = "up" if d >= 0.05 else "down" if d <= -0.05 else "steady"
            reasons = []
            if word == "down":
                if mean(f.difficulty for f in b) - mean(f.difficulty for f in a) >= 0.25:
                    reasons.append("the questions were harder this month")
                fresh = sum(1 for f in b if f.plan_item_id and first_day.get(f.plan_item_id, ds.today) >= ds.since(30))
                if fresh / len(b) >= 0.4:
                    reasons.append(f"{pct(fresh / len(b))}% of this month's answers were on topics started this month, so a dip is expected")
            elif word == "up" and mean(f.difficulty for f in b) - mean(f.difficulty for f in a) >= 0.25:
                reasons.append("even though the questions were harder")
            improvement.append(f"{SUBJECT_NAMES[code]}: {pct(_avg(a))}% → {pct(_avg(b))}% ({word}" + "".join(f"; {r}" for r in reasons) + ").")
    if not improvement:
        improvement.append("Improvement is measured against the previous 30 days once both months have at least five answers in a subject.")
    # weak areas with the main reason
    weak = []
    for r in mastery:
        if r["pct"] < 60 and r["n"] >= 3:
            k = next(k for k in cur_i if ds.item_name(k) == r["name"])
            top = Counter(c for f in cur_i[k] for c in f.errors).most_common(1)
            weak.append(f"{r['name']} — {r['pct']}% across {r['n']} answers" + (f"; most common issue: {top[0][0]}." if top else "."))
    # response quality (written English and Legal)
    quality = []
    for code in ("ENGLISH", "LEGAL"):
        sd = rep["subjects"][code]
        written = [f for f in month if f.subject == code and not f.auto and not f.mcq and not f.skipped]
        if len(written) < 3:
            continue
        line = f"{SUBJECT_NAMES[code]}: written answers average {pct(_avg(written))}% across {len(written)} responses"
        if sd["avg_words"]:
            line += f", {sd['avg_words']} words on average" + (f" (Band 6 models: {sd['model_words']})" if sd["model_words"] else "")
        top = Counter(c for f in written for c in f.errors).most_common(2)
        if top:
            line += "; most frequent issues: " + ", ".join(f"{c} ({n})" for c, n in top)
        est = sum(1 for f in written if f.estimated)
        if est:
            line += f". {est} of these marks are offline estimates."
        quality.append(line if line.endswith(".") else line + ".")
    # time management
    time_lines = []
    for code, sd in rep["subjects"].items():
        if sd["time_ratio"] is None or sd["answers"] < 5:
            continue
        r = sd["time_ratio"]
        verdict = ("well over exam pace" if r > 1.3 else "close to exam pace" if r >= 0.8 else "well inside exam time")
        time_lines.append(f"{SUBJECT_NAMES[code]}: a typical question takes {r}× the exam-style time ({verdict}); "
                          f"{sd['within_time']}% finished within 1.25× of it.")
    sessions = _sessions_between(db, ds.since(30), ds.today)
    done = [s for s in sessions if s.status == "completed"]
    if done:
        mins = study_minutes(db, done) / len(done)
        target = ds.settings.get("target_minutes") or 90
        time_lines.append(f"Completed sessions took {round(mins)} minutes on average (target about {target}).")
    # revision retention
    reps = [f for f in month if f.repeat]
    retention = None
    if len(reps) >= 3:
        firsts: dict[int, Fact] = {}
        for f in ds.facts:
            firsts.setdefault(f.question_id, f)
        a = _avg([firsts[f.question_id] for f in reps])
        retention = (f"On {len(reps)} questions you met again you scored {pct(_avg(reps))}%, compared with {pct(a)}% the first time — "
                     + ("revision is consolidating." if _avg(reps) - a >= 0.05 else "knowledge is fading between exposures; revise "
                        "worked solutions a few days after each session." if a - _avg(reps) >= 0.05 else "about the same."))
    # priorities
    priorities = []
    for w in rep["insights"]:
        if w["tone"] == "warn" and len(priorities) < 2:
            priorities.append(w["line"])
    for r in mastery:
        if r["pct"] < 60 and r["n"] >= 3 and len(priorities) < 4:
            priorities.append(f"Rebuild {r['name']} ({r['pct']}%): read the worked solutions, then practise two fresh questions.")
    if not priorities:
        priorities = ["Continue the current learning sequence; no topic this month is below 60%."]
    return {
        "report": rep, "readiness": readiness(db, ds), "n": len(month), "n_prev": len(prev),
        "coverage": {"overall": pct(cov["overall"]), "subjects": {c: pct(v["coverage"]) for c, v in cov["subjects"].items()},
                     "new_topics": new_topics, "not_assessed": rep["not_assessed"]},
        "mastery": mastery, "improvement": improvement, "weak": weak, "response_quality": quality, "time_management": time_lines,
        "retention": retention, "priorities": priorities,
    }


# ------------------------------------------------------------------ dashboard ---
def dashboard(db: Session) -> dict:
    """Everything on the dashboard (spec 20) from one dataset."""
    ds = Dataset(db)
    today = ds.today
    weekdays = _weekdays(ds)
    week_start = today - timedelta(days=today.weekday())
    from app.services import sessions as sessions_service

    try:
        sess = sessions_service.get_session(db, today)
    except Exception:  # the selection package owns sessions: degrade to "no session" rather than fail the dashboard
        sess = None
    sprog = None
    if sess is not None and sess.questions:
        try:
            raw = sessions_service.progress(sess) or {}
        except Exception:
            raw = {}
        n_total = int(raw.get("n_total") or len(sess.questions))
        n_done = int(raw.get("n_done") if raw.get("n_done") is not None else
                     sum(1 for q in sess.questions if q.status in ("submitted", "skipped")))
        sprog = {"n_done": n_done, "n_total": n_total, "pct": int(raw.get("pct") if raw.get("pct") is not None else
                                                                    round(100 * n_done / n_total) if n_total else 0),
                 "remaining_minutes": raw.get("remaining_minutes")}
    try:
        streak = sessions_service.weekday_streak(db, today)
    except Exception:
        streak = 0
    week = ds.window(week_start, today)
    week_sessions = _sessions_between(db, week_start, today)
    # unfinished sessions from earlier days (answers saved, questions left)
    earlier = list(db.execute(select(DailySession).where(DailySession.session_date < today, DailySession.session_date >= today - timedelta(days=14),
                                                         DailySession.status.in_(("generated", "in_progress", "missed"))).order_by(DailySession.session_date.desc())).scalars())
    answered = _answered_counts(db, [s.id for s in earlier])
    unfinished = []
    missed = []
    for s in earlier:
        n_total = len(s.questions)
        n_done = answered.get(s.id, 0)
        if n_total and 0 < n_done < n_total:
            left = [sq for sq in s.questions if sq.status not in ("submitted", "skipped")]
            unfinished.append({"session": s, "left": len(left), "minutes": round(sum(sq.question.estimated_minutes for sq in left))})
        elif s.status == "missed":
            missed.append(s)
    # subject status
    recent = ds.window(ds.since(30))
    before = ds.window(ds.since(60), ds.since(30) - timedelta(days=1))
    plan_status = {}
    for code in SUBJECT_NAMES:
        items = sorted((i for i in ds.items.values() if ds.subject_codes.get(i.subject_id) == code and i.active), key=lambda i: i.position)
        learning = [i for i in items if i.status == "LEARNING"]
        nxt = next((i for i in items if i.status == "LOCKED" and not i.enrichment), None)
        r = [f for f in recent if f.subject == code]
        b = [f for f in before if f.subject == code]
        trend = None
        if len(r) >= 5 and len(b) >= 5:
            d = _avg(r) - _avg(b)
            trend = "up" if d >= 0.05 else "down" if d <= -0.05 else "steady"
        plan_status[code] = {"learning": learning, "next": nxt, "recent": pct(_avg(r)) if len(r) >= 3 else None, "recent_n": len(r),
                             "trend": trend, "mastery": pct(mean(ds.mastery[i.id].mastery for i in items if i.id in ds.mastery))}
    # revision due
    due_rows = db.execute(select(RevisionQueue.plan_item_id, func.min(RevisionQueue.due_date)).where(
        RevisionQueue.status == "open", RevisionQueue.due_date <= today, RevisionQueue.plan_item_id.is_not(None))
        .group_by(RevisionQueue.plan_item_id).order_by(func.min(RevisionQueue.due_date))).all()
    exact_due = db.execute(select(func.count(QuestionExposure.id)).where(QuestionExposure.next_revision_date <= today)).scalar_one()
    revision = {"skills": len(due_rows), "names": [ds.item_name(k) for k, _ in due_rows[:4]], "exact": exact_due}
    # weak areas (last 60 days, at least three answers)
    last60 = ds.window(ds.since(60))
    weak = []
    for k, v in sorted(_group(last60, lambda f: f.plan_item_id).items(), key=lambda kv: _avg(kv[1])):
        if len(v) >= 3 and _avg(v) < 0.6:
            top = Counter(c for f in v for c in f.errors).most_common(1)
            weak.append({"name": ds.item_name(k), "subject": ds.item_subject(k), "pct": pct(_avg(v)), "n": len(v),
                         "issue": top[0][0] if top else None})
    # recent improvement: last 14 days against the 28 days before
    last14 = ds.window(ds.since(14))
    prior = ds.window(ds.since(42), ds.since(14) - timedelta(days=1))
    improve = []
    a_i, b_i = _group(prior, lambda f: f.plan_item_id), _group(last14, lambda f: f.plan_item_id)
    for k, v in b_i.items():
        if len(v) >= 3 and len(a_i.get(k, [])) >= 3 and _avg(v) - _avg(a_i[k]) >= 0.10:
            improve.append((_avg(v) - _avg(a_i[k]), f"{ds.item_name(k)}: {pct(_avg(a_i[k]))}% → {pct(_avg(v))}%"))
    for code in SUBJECT_NAMES:
        a = [f for f in prior if f.subject == code]
        b = [f for f in last14 if f.subject == code]
        if len(a) >= 5 and len(b) >= 5 and _avg(b) - _avg(a) >= 0.08:
            improve.append((_avg(b) - _avg(a) - 0.001, f"{SUBJECT_NAMES[code]} overall: {pct(_avg(a))}% → {pct(_avg(b))}%"))
    improve = [t for _, t in sorted(improve, key=lambda x: -x[0])[:3]]
    top_insight = insights(ds, ds.window(ds.since(30)), limit=1)
    return {
        "today": today, "session": sess, "session_progress": sprog,
        "is_study_day": today.weekday() in weekdays, "streak": streak,
        "week": {"questions": len(week), "minutes": study_minutes(db, week_sessions), "average": pct(_avg(week)),
                 "sessions": sum(1 for s in week_sessions if s.status == "completed")},
        "plan_status": plan_status, "revision": revision, "revision_due": due_rows, "weak": weak[:5], "improvement": improve,
        "missed": missed, "unfinished": unfinished, "readiness": readiness(db, ds), "bank": bank_health(db, ds.settings, ds.subject_codes, today),
        "insight": top_insight[0].line if top_insight else None, "answers_total": len(ds.facts),
        "next_study_day": _next_study_day(today + timedelta(days=1), weekdays),
        "daily_counts": dict(DAILY_COUNTS),
    }
