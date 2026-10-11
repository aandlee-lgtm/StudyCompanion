"""Question bank health and historical question coverage (owner: analytics).

* ``bank_health`` answers "how many study days until today's questions start repeating?" per
  subject, and lists LEARNING items that have no questions at all.
* ``historical_coverage`` implements spec section 45: for every syllabus focus area, how well
  genuine NESA material covers it, counting unique source questions (parts of one question
  count once) weighted by how directly they apply to the 2027 syllabus, with generated questions
  counted separately, and the next action for areas that are LIMITED or NONE."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LearningPlanItem, Question, QuestionExposure, Source, Stimulus, SyllabusTopic
from app.models.common import (
    APPROVAL_APPROVED,
    DAILY_COUNTS,
    LOCKED,
    ORIGIN_ADAPTED,
    ORIGIN_GENERATED,
    ORIGIN_HISTORICAL,
    ORIGIN_SAMPLE,
    ORIGIN_TRIAL,
    REJECT,
)
from app.services.analytics_data import SUBJECT_NAMES

# --------------------------------------------------------------- bank health ---
GOOD_DAYS, LOW_DAYS = 20, 10


def _has_template(code: str) -> bool:
    try:
        from app.services import maths_templates
    except Exception:  # pragma: no cover - maths package missing
        return False
    fn = getattr(maths_templates, "has_template", None)
    if callable(fn):
        try:
            return bool(fn(code))
        except Exception:
            return False
    return code in (getattr(maths_templates, "TEMPLATES", None) or {})


def _servable_rows(db: Session, settings: dict) -> list:
    """Questions the selection engine may serve today (its hard rules), as light rows."""
    prefs = settings.get("source_preferences") or {}
    blocked = {o for o, k in ((ORIGIN_TRIAL, "allow_trial"), (ORIGIN_GENERATED, "allow_generated"), (ORIGIN_ADAPTED, "allow_adapted"))
               if not prefs.get(k, True)}
    stmt = (select(Question.id, Question.subject_id, Question.plan_item_id, Question.stimulus_id, Question.category, Question.question_type,
                   Question.historical_or_generated, LearningPlanItem.status, LearningPlanItem.enrichment, LearningPlanItem.code)
            .join(LearningPlanItem, Question.plan_item_id == LearningPlanItem.id)
            .where(Question.approved.is_(True), Question.approval_status == APPROVAL_APPROVED, Question.relevance_status != REJECT,
                   Question.is_extension.is_(False), LearningPlanItem.active.is_(True), LearningPlanItem.status != LOCKED))
    rows = db.execute(stmt).all()
    enrich = bool(settings.get("enrichment_enabled"))
    return [r for r in rows if (enrich or not r.enrichment) and r.historical_or_generated not in blocked]


def _days(n: int) -> str:
    return f"{n} study day{'' if n == 1 else 's'}"


def _level(days: float | None) -> str:
    if days is None:
        return "good"
    return "good" if days >= GOOD_DAYS else "warn" if days >= LOW_DAYS else "bad"


def bank_health(db: Session, settings: dict, subject_codes: dict[int, str], today: date) -> dict[str, dict]:
    rows = _servable_rows(db, settings)
    exposure = {e.question_id: e.next_revision_date for e in db.execute(select(QuestionExposure)).scalars()}
    by_subject: dict[str, list] = defaultdict(list)
    for r in rows:
        by_subject[subject_codes.get(r.subject_id, "?")].append(r)
    learning = db.execute(select(LearningPlanItem).where(LearningPlanItem.status == "LEARNING", LearningPlanItem.active.is_(True))
                          .order_by(LearningPlanItem.position)).scalars().all()
    served_items = {r.plan_item_id for r in rows}
    out: dict[str, dict] = {}
    for code in SUBJECT_NAMES:
        rs = by_subject.get(code, [])
        fresh = [r for r in rs if r.id not in exposure]
        due_again = [r for r in rs if r.id in exposure and exposure[r.id] is not None and exposure[r.id] <= today]
        per_day = DAILY_COUNTS.get(code, 3)
        empty = [i for i in learning if subject_codes.get(i.subject_id) == code and i.id not in served_items
                 and not (code == "MATHS" and _has_template(i.code))]
        d: dict = {"name": SUBJECT_NAMES[code], "servable": len(rs), "fresh": len(fresh), "due_again": len(due_again),
                   "per_day": per_day, "empty_learning": [f"{i.code} {i.title}" if i.chapter else i.title for i in empty], "lines": []}
        if code == "MATHS":
            current = [i for i in learning if subject_codes.get(i.subject_id) == code]
            templ = [i for i in current if _has_template(i.code)]
            fixed_fresh = [r for r in fresh if not _has_template(r.code)]
            d["template_items"], d["current_items"] = len(templ), len(current)
            all_templated = bool(current) and len(templ) == len(current)
            d["days"] = None if all_templated else len(fixed_fresh) // per_day
            if all_templated:
                d["headline"] = "New questions are generated for every current topic"
                which = "the current subtopic" if len(current) == 1 else f"all {len(current)} current subtopics"
                d["lines"].append(f"{len(fresh)} unseen questions in the bank; question templates create fresh ones for {which}.")
            else:
                d["headline"] = f"About {_days(d['days'])} of fresh questions"
                d["lines"].append(f"{len(fresh)} unseen questions; templates cover {len(templ)} of {len(current)} current subtopics.")
        elif code == "ENGLISH":
            stim_ids = {r.stimulus_id for r in rs if r.stimulus_id and r.category != "course"}
            seen_stims = {r.stimulus_id for r in rs if r.stimulus_id and r.id in exposure}
            pairs = _pair_map(db, stim_ids)
            sets = {pairs.get(s, s) for s in stim_ids}
            fresh_sets = {pairs.get(s, s) for s in stim_ids if s not in seen_stims and pairs.get(s, s) not in
                          {pairs.get(x, x) for x in seen_stims}}
            course_fresh = [r for r in fresh if r.category == "course"]
            share = float(settings.get("english_unseen_share") or 0.8)
            course_per_day = max(0.2, 3 * (1 - share))
            d["sets"], d["fresh_sets"], d["course_fresh"] = len(sets), len(fresh_sets), len(course_fresh)
            d["days"] = len(fresh_sets)
            d["headline"] = (f"About {_days(d['days'])} before reading sets repeat" if d["days"] else
                             "No unused reading sets left: English questions are now repeats")
            d["lines"].append(f"{len(fresh_sets)} of {len(sets)} unseen reading sets not yet used (one set per day).")
            if course_fresh:
                d["lines"].append(f"{len(course_fresh)} course-linked tasks not yet attempted (about "
                                  f"{_days(max(1, round(len(course_fresh) / course_per_day)))} at the current mix).")
            else:
                d["lines"].append("Every course-linked task has been attempted: those questions now repeat.")
        else:
            d["days"] = len(fresh) // per_day if per_day else 0
            d["headline"] = (f"About {_days(d['days'])} of fresh questions" if d["days"] else
                             "Fewer than a day of fresh questions left: Legal questions are now repeats")
            types = defaultdict(int)
            for r in fresh:
                types[r.question_type] += 1
            label = {"mcq": ("multiple-choice question", "multiple-choice questions"), "short_answer": ("short answer", "short answers"),
                     "stimulus": ("stimulus-based question", "stimulus-based questions"),
                     "extended": ("extended response", "extended responses")}
            parts = [f"{n} {label.get(t, (t, t))[0 if n == 1 else 1]}" for t, n in sorted(types.items())]
            d["lines"].append("Not yet seen: " + (", ".join(parts) or "none") + ".")
            if not types.get("extended"):
                d["lines"].append("No unseen extended responses: the weekly extended response will repeat.")
        d["level"] = _level(d["days"])
        if d["due_again"]:
            d["lines"].append(f"{len(due_again)} seen questions are due for revision again.")
        out[code] = d
    return out


def _pair_map(db: Session, stim_ids: set[int]) -> dict[int, int]:
    """Map each stimulus to one representative id for its reading set (paired texts count once)."""
    if not stim_ids:
        return {}
    out = {}
    for sid, pid in db.execute(select(Stimulus.id, Stimulus.paired_with_id).where(Stimulus.id.in_(stim_ids))).all():
        out[sid] = min(sid, pid) if pid else sid
    return out


# --------------------------------------------------------- historical coverage ---
WEIGHTS = {"sample": 1.0, "historical": 0.8, "partial": 0.4, "adapted": 0.3}
GOOD_AT, MODERATE_AT = 12.0, 4.0


def _base_number(n: str | None) -> str | None:
    if not n:
        return None
    m = re.match(r"\s*(?:Q(?:uestion)?\s*)?(\d+)", n, re.I)
    return m.group(1) if m else n.strip().lower()


def historical_coverage(db: Session, include_inactive_options: bool = False) -> list[dict]:
    """Coverage per focus area/module/topic, with per-subtopic detail and actions."""
    topics = db.execute(select(SyllabusTopic).order_by(SyllabusTopic.subject_id, SyllabusTopic.position)).scalars().all()
    items = {i.id: i for i in db.execute(select(LearningPlanItem)).scalars()}
    active_topics = {i.topic_id for i in items.values() if i.active and i.topic_id}
    rows = db.execute(select(Question.id, Question.plan_item_id, Question.topic_id, Question.historical_or_generated, Question.relevance_status,
                             Question.source_id, Question.question_number, Question.source_year, Question.approved, Question.approval_status,
                             Question.is_extension, Source.tier).join(Source, Question.source_id == Source.id, isouter=True)).all()
    score: dict[int, float] = defaultdict(float)
    unique: dict[int, set] = defaultdict(set)
    gen: dict[int, int] = defaultdict(int)
    pending: dict[int, int] = defaultdict(int)
    per_item: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    seen_keys: set = set()
    for r in rows:
        if r.relevance_status == REJECT or r.is_extension:
            continue
        item = items.get(r.plan_item_id) if r.plan_item_id else None
        area = item.topic_id if item is not None and item.topic_id else r.topic_id
        if area is None:
            continue
        origin = r.historical_or_generated
        if origin in (ORIGIN_GENERATED, ORIGIN_TRIAL):
            if r.approved:
                gen[area] += 1
            continue
        if not r.approved or r.approval_status != APPROVAL_APPROVED:
            if origin in (ORIGIN_HISTORICAL, ORIGIN_SAMPLE, ORIGIN_ADAPTED):
                pending[area] += 1
            continue
        if origin == ORIGIN_ADAPTED:
            w = WEIGHTS["adapted"]
        elif r.relevance_status != "DIRECT":
            w = WEIGHTS["partial"]
        elif origin == ORIGIN_SAMPLE or (r.tier == 1):
            w = WEIGHTS["sample"]
        else:
            w = WEIGHTS["historical"]
        key = (r.source_id, r.source_year, _base_number(r.question_number) or f"id{r.id}", area)
        if key in seen_keys:  # another part of the same source question
            continue
        seen_keys.add(key)
        score[area] += w
        unique[area].add(key)
        if item is not None:
            per_item[area][item.id] += w
    out = []
    for t in topics:
        if t.is_option and t.id not in active_topics and not include_inactive_options:
            continue
        s = round(score.get(t.id, 0.0), 1)
        level = "GOOD" if s >= GOOD_AT else "MODERATE" if s >= MODERATE_AT else "LIMITED" if s > 0 else "NONE"
        subj = t.subject.code
        sub = [{"name": f"{i.code} {i.title}" if i.chapter else i.title, "score": round(per_item[t.id].get(i.id, 0.0), 1)}
               for i in sorted((x for x in items.values() if x.topic_id == t.id and x.active), key=lambda x: x.position)]
        actions = []
        if level in ("LIMITED", "NONE"):
            # spec 45 order: official 2027 sample material, then transferable historical questions, then generated
            actions = [{"text": "Import the official NESA 2027 sample material for this area", "href": "/admin/import"}]
            if pending.get(t.id):
                actions.append({"text": f"Review the {pending[t.id]} imported historical question{'s' if pending[t.id] != 1 else ''} "
                                        "waiting for approval", "href": "/admin/review"})
            else:
                actions.append({"text": "Import past HSC papers and keep the directly transferable questions", "href": "/admin/import"})
            if gen.get(t.id):
                actions.append({"text": f"Practise the {gen[t.id]} clearly labelled generated question{'s' if gen[t.id] != 1 else ''}",
                                "href": f"/questions?subject={subj}&topic={t.id}&origin=GENERATED"})
            else:
                actions.append({"text": "No generated questions yet: an AI provider can create labelled, syllabus-aligned ones",
                                "href": "/settings"})
        out.append({"subject": subj, "topic_id": t.id, "topic": t.name, "kind": t.kind, "year11": t.kind == "year11",
                    "score": s, "questions": len(unique.get(t.id, ())), "generated": gen.get(t.id, 0), "pending": pending.get(t.id, 0),
                    "level": level, "subtopics": sub, "actions": actions})
    return out
