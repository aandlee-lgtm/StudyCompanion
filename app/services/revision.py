"""Revision page data, 'Practise now' picking and 15-minute revision sets (owner: adaptive; adaptive-18, adaptive-12).

The revision page groups open revision items by urgency, shows the evidence behind each one (last
result, mastery estimate next to real accuracy, open error tags, a short trend) and lists what
revision already achieved. 'Practise now' asks the selection engine's own rules for a question:
servable (never LOCKED, rejected, extension or a disabled source), fresh or due, a DIFFERENT
question from the one that queued a revisit, and the best-scoring one for today."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Attempt,
    ErrorJournal,
    ExposureEvent,
    LearningPlanItem,
    Mastery,
    Question,
    QuestionExposure,
    RevisionQueue,
    RevisionSet,
)
from app.models.common import LEARNING
from app.services import mastery as ms

URGENT_KINDS = ("misconception", "rebuild")
SET_MIN, SET_MAX, SET_MINUTES = 3, 5, 15


# ------------------------------------------------------------------- picking ---
def question_tags(q: Question) -> set[str]:
    """Error tags a question is known to exercise (maths common errors carry ``topic_tag``/``category``)."""
    tags: set[str] = set()
    sol = q.solution if isinstance(q.solution, dict) else {}
    for ce in sol.get("common_errors") or []:
        if isinstance(ce, dict):
            for k in ("topic_tag", "category", "tag"):
                if ce.get(k):
                    tags.add(str(ce[k]).lower())
    for t in sol.get("error_tags") or []:
        tags.add(str(t).lower())
    return tags


def _context(db: Session, today: date):
    from app.selection.context import build_context

    return build_context(db, today)


def freshness_level(ctx, q: Question, alternatives: int) -> int:
    """0 = fresh or due (the selection engine's FRESH tier); 1 = a fallback repeat the engine allows
    (LADDER: not seen for two weeks); 2 = never offered (seen recently, excluded, or only a flagged
    repeat). Uses the selection engine's eligibility tiers so the exact-repeat rule stays hard."""
    from app.selection.scoring import FRESH, LADDER, eligibility

    tier, _kind = eligibility(ctx, q, alternatives)
    return 0 if tier == FRESH else (1 if tier == LADDER else 2)


def pick_question(db: Session, plan_item_id: int | None, today: date, *, tag: str | None = None, exclude: set[int] | None = None,
                  ctx=None) -> Question | None:
    """Best servable question on a skill for revision now: fresh or due first, a question carrying the
    error tag preferred, then the selection engine's score. Exact repeats follow the selection engine's
    eligibility tiers (never before the revision date except its two-week fallback); ``exclude`` removes specific questions (e.g. the one that queued a revisit)."""
    if not plan_item_id:
        return None
    from app.selection.scoring import is_servable, score

    ctx = ctx or _context(db, today)
    item = ctx.plan.get(plan_item_id) or db.get(LearningPlanItem, plan_item_id)
    if item is None:
        return None
    code = item.subject.code
    exclude = exclude or set()
    servable = [q for q in db.execute(select(Question).where(Question.plan_item_id == plan_item_id)).scalars()
                if is_servable(ctx, q)]
    best, best_key = None, None
    for q in servable:
        if q.id in exclude:
            continue
        level = freshness_level(ctx, q, len(servable) - 1)
        if level >= 2:
            continue
        tagged = 1 if tag and tag.lower() in question_tags(q) else 0
        try:
            s = score(ctx, q, code).score
        except Exception:  # scoring is owned by selection; never let it block revision
            s = 0.0
        key = (level, -tagged, -s, q.id)
        if best_key is None or key < best_key:
            best, best_key = q, key
    return best


def source_question_ids(db: Session, r: RevisionQueue) -> set[int]:
    """A revisit asks for a different question: exclude the question whose attempt queued it."""
    if r.source_attempt_id and r.kind != "recycle":
        a = db.get(Attempt, r.source_attempt_id)
        if a is not None:
            return {a.question_id}
    return set()


def pick_for_item(db: Session, r: RevisionQueue, today: date, *, exclude: set[int] | None = None, ctx=None) -> Question | None:
    if r.plan_item_id:
        return pick_question(db, r.plan_item_id, today, tag=r.tag, exclude=(exclude or set()) | source_question_ids(db, r), ctx=ctx)
    q = db.get(Question, r.question_id) if r.question_id else None
    return q if q is not None and q.approved and (not exclude or q.id not in exclude) else None


# --------------------------------------------------------------- page data ---
def _skill_name(item: LearningPlanItem | None) -> str:
    if item is None:
        return "Question revision"
    return f"{item.code} {item.title}" if item.chapter else item.title


def skill_evidence(db: Session, plan_item_id: int | None) -> dict:
    """Last result, trend, mastery estimate, real accuracy and open error tags for one skill."""
    if not plan_item_id:
        return {}
    events = db.execute(select(ExposureEvent).where(ExposureEvent.plan_item_id == plan_item_id, ExposureEvent.counted.is_(True))
                        .order_by(ExposureEvent.id.desc()).limit(8)).scalars().all()
    m = db.execute(select(Mastery).where(Mastery.plan_item_id == plan_item_id)).scalar_one_or_none()
    right, n = ms.recent_accuracy(db, plan_item_id)
    tags = Counter((e.topic_tag or e.category) for e in db.execute(
        select(ErrorJournal).where(ErrorJournal.plan_item_id == plan_item_id, ErrorJournal.resolved.is_(False))).scalars())
    last = events[0] if events else None
    return {
        "last": {"pct": round(100 * last.fraction), "date": last.study_date, "estimate": last.method == "offline_estimate",
                 "skipped": last.outcome_kind == "skipped"} if last else None,
        "trend": [round(e.fraction, 2) for e in reversed(events)],
        "mastery": round(100 * m.mastery) if m and m.attempts else None,
        "rebuild": bool(m and m.state == "rebuild"),
        "accuracy": f"{right} of your last {n} counted answers correct" if n else None,
        "tags": [t for t, _ in tags.most_common(3)],
    }


def _row(db: Session, r: RevisionQueue, today: date) -> dict:
    item = db.get(LearningPlanItem, r.plan_item_id) if r.plan_item_id else None
    days = (r.due_date - today).days
    when = "due today" if days == 0 else (f"overdue by {-days} day{'s' if days != -1 else ''}" if days < 0 else f"due {ms.nice_date(r.due_date)}")
    return {"r": r, "item": item, "skill": _skill_name(item), "kind_label": ms.KIND_LABELS.get(r.kind, "Revision"), "when": when,
            "evidence": skill_evidence(db, r.plan_item_id), "learning": bool(item and item.status == LEARNING)}


def review_page(db: Session, today: date) -> dict:
    sections: dict[str, list[dict]] = {"urgent": [], "due": [], "week": [], "later": [], "recycle": [], "learning": []}
    for r in db.execute(select(RevisionQueue).where(RevisionQueue.status == "open")
                        .order_by(RevisionQueue.due_date, RevisionQueue.priority.desc(), RevisionQueue.id)).scalars():
        row = _row(db, r, today)
        if r.kind == "recycle":
            sections["recycle"].append(row)
        elif row["learning"] and not r.tag and r.kind not in URGENT_KINDS:
            sections["learning"].append(row)  # the current topic is already in every daily session
        elif r.kind in URGENT_KINDS:
            sections["urgent"].append(row)
        elif r.due_date <= today:
            sections["due"].append(row)
        elif r.due_date <= today + timedelta(days=7):
            sections["week"].append(row)
        else:
            sections["later"].append(row)
    repeats_due, repeats_later = [], []
    rows = db.execute(select(QuestionExposure, Question).join(Question, QuestionExposure.question_id == Question.id)
                      .where(QuestionExposure.next_revision_date.is_not(None), Question.approved.is_(True))
                      .order_by(QuestionExposure.next_revision_date).limit(60)).all()
    for e, q in rows:
        (repeats_due if e.next_revision_date <= today else repeats_later).append((e, q))
    completed = []
    for r in db.execute(select(RevisionQueue).where(RevisionQueue.status == "done", RevisionQueue.completed_at.is_not(None))
                        .order_by(RevisionQueue.completed_at.desc(), RevisionQueue.id.desc()).limit(20)).scalars():
        item = db.get(LearningPlanItem, r.plan_item_id) if r.plan_item_id else None
        served = db.get(Attempt, r.served_by_attempt_id) if r.served_by_attempt_id else None
        completed.append({"r": r, "skill": _skill_name(item), "kind_label": ms.KIND_LABELS.get(r.kind, "Revision"),
                          "pct": round(100 * r.outcome) if r.outcome is not None else None, "question_id": served.question_id if served else None,
                          "verdict": _verdict(r.outcome)})
    open_set = db.execute(select(RevisionSet).where(RevisionSet.status == "open").order_by(RevisionSet.id.desc())).scalars().first()
    actionable = len(sections["urgent"]) + len(sections["due"])
    return {"sections": sections, "repeats_due": repeats_due[:20], "repeats_later": repeats_later[:20], "completed": completed,
            "open_set": open_set, "actionable": actionable, "today": today}


def _verdict(outcome: float | None) -> str:
    if outcome is None:
        return ""
    if outcome >= 0.85:
        return "fixed"
    if outcome >= 0.5:
        return "improving"
    return "still weak — queued again"


# ------------------------------------------------------------- revision set ---
def start_set(db: Session, today: date) -> RevisionSet | None:
    """3–5 due items (urgent first, then by priority), one distinct question each, about 15 minutes."""
    return _build_set(db, today)


def _minutes(q: Question) -> float:
    return float(q.estimated_minutes or 0) or max(1.5, 1.5 * float(q.marks or 1))


def _build_set(db: Session, today: date) -> RevisionSet | None:
    open_items = db.execute(select(RevisionQueue).where(RevisionQueue.status == "open", RevisionQueue.kind != "recycle")).scalars().all()
    due = [r for r in open_items if r.due_date <= today or r.kind in URGENT_KINDS]
    due.sort(key=lambda r: (r.kind not in URGENT_KINDS, -ms.KIND_URGENCY.get(r.kind, 0), -r.priority, r.due_date, r.id))
    if not due:
        return None
    ctx = _context(db, today)
    chosen, used, skills, minutes = [], set(), set(), 0.0
    last_attempt = db.execute(select(Attempt.id).order_by(Attempt.id.desc())).scalars().first() or 0
    for r in due:
        if len(chosen) >= SET_MAX:
            break
        key = r.plan_item_id or ("q", r.question_id)
        if key in skills:
            continue
        q = pick_for_item(db, r, today, exclude=used, ctx=ctx)
        if q is None:
            continue
        m = _minutes(q)
        if len(chosen) >= SET_MIN and minutes + m > SET_MINUTES + 3:
            break
        chosen.append({"question_id": q.id, "revision_id": r.id, "reason": r.reason, "kind": r.kind,
                       "skill": _skill_name(db.get(LearningPlanItem, r.plan_item_id) if r.plan_item_id else None),
                       "baseline_attempt_id": last_attempt, "minutes": round(m, 1)})
        used.add(q.id)
        skills.add(key)
        minutes += m
    if not chosen:
        return None
    s = RevisionSet(created_on=today, items=chosen, expected_minutes=round(minutes, 1))
    db.add(s)
    db.flush()
    return s


def set_progress(db: Session, s: RevisionSet) -> list[dict]:
    """Each item with its question and the attempt made after the set started (if any)."""
    out = []
    for it in s.items or []:
        q = db.get(Question, it["question_id"])
        a = db.execute(select(Attempt).where(Attempt.question_id == it["question_id"], Attempt.id > it.get("baseline_attempt_id", 0))
                       .order_by(Attempt.id)).scalars().first()
        out.append({**it, "question": q, "attempt": a})
    return out


def refresh_set_status(db: Session, s: RevisionSet) -> list[dict]:
    from app.models.common import utcnow

    rows = set_progress(db, s)
    if s.status == "open" and rows and all(r["attempt"] is not None for r in rows):
        s.status, s.completed_at = "completed", utcnow()
        db.flush()
    return rows


# ------------------------------------------------------------ rebuild ladder ---
# General study scaffolds by directive-verb tier (no subject facts are asserted here).
VERB_TIERS = {
    "identify": 1, "outline": 1, "define": 1, "describe": 1, "recall": 1, "state": 1,
    "explain": 2, "discuss": 2, "compare": 2, "distinguish": 2, "account": 2, "examine": 2,
    "analyse": 3, "assess": 3, "evaluate": 3, "justify": 3, "critically": 3, "to what extent": 3,
}
TIER_LADDER = {
    1: ["Name the feature, term or point the question asks for.", "Add one precise detail or example that shows it."],
    2: ["Name the point.", "Explain how or why it works — the cause and effect.", "Support it with evidence (a quotation, a case, a law or a figure)."],
    3: ["Name the point.", "Explain how it works, with evidence.", "Weigh it: how well, how far, compared with what — and give your judgement."],
}
STARTERS = {
    "ENGLISH": ["The composer uses … to …", "This is evident in “…”, where …", "As a result, the reader/audience …",
                "This shapes the text's meaning by …"],
    "LEGAL": ["The legal term … means …", "This applies here because …", "For example, … (case, legislation or report from your evidence bank)",
              "This is effective/ineffective in achieving justice because …", "On balance, …"],
}


def _tier(verb: str | None) -> int:
    v = (verb or "").lower()
    return next((t for k, t in VERB_TIERS.items() if k in v), 2)


def rebuild_ladder(db: Session, q: Question) -> dict | None:
    """Step-by-step practice for a skill in the rebuild state (adaptive-19): a worked example, a faded
    example to complete, then the question itself. Examples come only from questions on this skill that
    the student has already answered (their solutions were shown in feedback), so nothing fresh is spoiled."""
    if not q.plan_item_id:
        return None
    m = db.execute(select(Mastery).where(Mastery.plan_item_id == q.plan_item_id)).scalar_one_or_none()
    if m is None or m.state != "rebuild":
        return None
    item = db.get(LearningPlanItem, q.plan_item_id)
    code = item.subject.code if item else ""
    answered = db.execute(select(Question).join(Attempt, Attempt.question_id == Question.id)
                          .where(Question.plan_item_id == q.plan_item_id, Question.id != q.id, Question.approved.is_(True))
                          .order_by(Question.difficulty, Question.marks, Question.id).distinct()).scalars().all()
    out: dict = {"skill": _skill_name(item), "correct": m.rebuild_correct or 0, "needed": ms.REBUILD_EXIT_CORRECT, "since": m.state_since,
                 "code": code, "worked": None, "faded": None, "scaffold": None}
    if code == "MATHS":
        examples = [x for x in answered if isinstance(x.solution, dict) and len(x.solution.get("steps") or []) >= 2]
        if examples:
            w = examples[0]
            out["worked"] = {"question": w, "steps": w.solution["steps"], "concept": w.solution.get("concept"),
                             "technique": w.solution.get("technique")}
        if len(examples) > 1:
            f = examples[1]
            steps = f.solution["steps"]
            k = 1 if len(steps) <= 3 else 2
            out["faded"] = {"question": f, "shown": steps[:-k], "hidden": steps[-k:]}
    else:
        model = next((x for x in answered if x.model_answer), None)
        if model is not None:
            out["worked"] = {"question": model, "model": model.model_answer}
        tier = _tier(q.directive_verb)
        out["scaffold"] = {"verb": q.directive_verb or "respond", "tier": tier, "steps": TIER_LADDER[tier],
                           "paragraphs": max(1, min(4, round((q.marks or 2) / 2))) if (q.marks or 0) >= 3 else 1,
                           "starters": STARTERS.get(code, [])}
    return out
