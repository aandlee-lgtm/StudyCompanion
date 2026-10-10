"""Everything the selection engine needs to know about the student on a given day.

Built with a handful of bulk queries so generation stays fast with thousands of questions. All
history comes from the database (sessions, attempts, exposure, revision queue), never from the
browser."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Attempt,
    DailySession,
    LearningPlanItem,
    Mastery,
    Question,
    QuestionExposure,
    RevisionQueue,
    SessionQuestion,
    Stimulus,
)
from app.models.common import LEARNED, LEARNING, REVISION, utcnow
from app.selection.phases import PHASES, Phase, phase_for, timed_today
from app.selection.profiles import ModeProfile, build_profile
from app.services import settings as st

HISTORY_DAYS = 140  # enough for the passage cooldown and the extended-response rotation
OPENED = ("in_progress", "completed", "closed")
ANSWERED = ("submitted", "skipped")

# ------------------------------------------------------------------ question facets ---
_MATH_SPAN = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]|\$[^$]*\$", re.S)
_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_WS = re.compile(r"\s+")

VERB_TIERS = {
    1: ("identify", "outline", "define", "recall", "name", "state", "list", "recount"),
    2: ("describe", "explain", "distinguish", "account", "clarify", "summarise", "classify"),
    3: ("analyse", "discuss", "examine", "compare", "contrast", "interpret", "investigate", "apply"),
    4: ("assess", "evaluate", "justify", "critically", "to what extent", "recommend", "propose", "synthesise"),
}

ENGLISH_DEMANDS = ("identify", "explain", "analyse", "compare", "evaluate", "synthesise")


def verb_tier_of(question_type: str | None, verb: str | None, text: str | None = "", marks: int | None = 4) -> int:
    """0 = objective (MCQ); 1 Identify/Outline; 2 Describe/Explain; 3 Analyse/Discuss; 4 Assess/Evaluate."""
    if question_type == "mcq":
        return 0
    v = (verb or "").strip().lower()
    if not v:
        head = (text or "").strip().lower()[:40]
        for tier in (4, 3, 2, 1):
            if any(head.startswith(w) for w in VERB_TIERS[tier]):
                return tier
        return 2 if (marks or 4) <= 5 else 3
    for tier in (4, 3, 2, 1):
        if any(v.startswith(w) for w in VERB_TIERS[tier]):
            return tier
    return 2


def verb_tier(q: Question) -> int:
    return verb_tier_of(q.question_type, q.directive_verb, q.question_text, q.marks)


def demand_from_verb(verb: str | None) -> str:
    v = (verb or "").lower()
    if v.startswith(("identify", "outline", "name")):
        return "identify"
    if v.startswith(("compare", "contrast")):
        return "compare"
    if v.startswith(("evaluate", "assess", "to what extent", "justify")):
        return "evaluate"
    if v.startswith(("synthesise", "discuss")):
        return "synthesise"
    if v.startswith(("analyse", "examine", "interpret")):
        return "analyse"
    return "explain"


def english_demand(q: Question) -> str:
    sol = q.solution if isinstance(q.solution, dict) else {}
    d = (sol.get("demand") or "").lower()
    return d if d in ENGLISH_DEMANDS else demand_from_verb(q.directive_verb)


def legal_format(q: Question) -> str:
    """mcq | short_answer | stimulus | extended (spec 8A formats)."""
    t = q.question_type or "short_answer"
    if t in ("mcq", "extended", "stimulus"):
        return t
    if q.stimulus_id:
        return "stimulus"
    return "short_answer"


def form_key(q: Question) -> str:
    """A structural form id: template instances with only the numbers/expressions changed share one.

    Uses an explicit family when the content provides one (``solution.template_family`` / ``form_id``);
    otherwise generated template questions are keyed by their wording with every mathematical
    expression and number masked. Other questions are their own form."""
    sol = q.solution if isinstance(q.solution, dict) else {}
    for k in ("template_family", "form_id", "form"):
        v = sol.get(k)
        if isinstance(v, (str, int)) and str(v):
            return f"F{q.plan_item_id}:{v}"
    if (q.source_exam or "").startswith("Template"):
        masked = _MATH_SPAN.sub("§", q.question_text or "")
        masked = _NUM.sub("#", masked)
        masked = _WS.sub(" ", masked).strip().lower()[:80]
        return f"T{q.plan_item_id}:{masked}"
    return f"Q{q.id}"


@dataclass
class StudentContext:
    today: date  # the real day: every 'days since' is measured from it
    mode: str
    profile: ModeProfile
    settings: dict
    plan: dict[int, LearningPlanItem]
    mastery: dict[int, Mastery]
    exposure: dict[int, QuestionExposure]
    revision_items: dict[int, float]  # plan_item_id -> priority (due today or earlier)
    revision_item_due: dict[int, date]
    revision_questions: dict[int, float]  # question_id -> priority
    served: dict[int, list[date]]  # question -> session dates it was served (opened sessions, before today)
    recent_texts: list[str]  # questions served or attempted in the last 7 days (near-duplicate checks)
    recent_plan_counts: dict[int, int]  # plan item -> questions served in the last 3 sessions
    item_attempts: dict[int, int]
    item_results: dict[int, list[float]]  # plan item -> recent counted first-attempt fractions, newest first
    item_methods: dict[int, set[str]]  # marking methods behind item_results
    item_attempt_dates: dict[int, list[tuple[date, int]]]  # plan item -> (date, question) of attempts
    item_last_practised: dict[int, date]
    performance: dict[str, float | None]
    performance_n: dict[str, int]
    progress: float  # 0 = start of Year 12, 1 = HSC
    stimulus_last_read: dict[int, date]
    stimulus_unit: dict[int, tuple[int, ...]]  # stimulus -> ids of its reading set
    recent_forms: dict[str, date]  # Maths form key -> last served date
    english_history: list[dict]  # recent English items (newest first)
    legal_history: list[dict]  # recent Legal items (newest first)
    sessions_before: int  # study sessions with questions before today
    last_session_items: set[int]
    previous_bands: list[tuple[date, str]]  # Maths difficulty band of recent sessions (newest first)
    reserved_ids: set[int] = field(default_factory=set)  # questions sitting in another open session
    exclude_ids: set[int] = field(default_factory=set)
    exclude_stimuli: set[int] = field(default_factory=set)
    catch_up: dict[int, dict] = field(default_factory=dict)  # plan item -> {"priority", "due", "reason"}
    weights: dict[str, float] = field(default_factory=dict)
    learned_on: dict[int, date] = field(default_factory=dict)
    recent_course_share: float | None = None
    session_date: date | None = None  # the day being planned (a resumed missed day keeps its own date)
    phase: Phase = PHASES["companion"]  # phase of the year (selection-22)

    # ---------------------------------------------------------------- derived ---
    @property
    def plan_date(self) -> date:
        return self.session_date or self.today

    def last_served(self, qid: int) -> date | None:
        d = self.served.get(qid)
        return d[-1] if d else None

    def days_since_seen(self, qid: int) -> int | None:
        """Days since the question was last served or attempted (None = never)."""
        cands = []
        if qid in self.served:
            cands.append(self.served[qid][-1])
        e = self.exposure.get(qid)
        if e is not None:
            cands.append(e.last_seen)
        return (self.today - max(cands)).days if cands else None

    def accuracy(self, item_id: int | None, n: int = 6) -> tuple[int, int, float] | None:
        """True recent accuracy on an item: (correct, attempted, mean fraction) over the last n
        counted first attempts. 'Correct' means at least 85% of the marks."""
        res = self.item_results.get(item_id or -1, [])[:n]
        if not res:
            return None
        return sum(1 for f in res if f >= 0.85), len(res), sum(res) / len(res)

    def target_difficulty(self, subject: str) -> float:
        """Continuous 1..3 target: rises through the year and with sustained success, falls when the
        student is struggling (the Maths composition still keeps HSC-standard work)."""
        base = 1.6 + 0.9 * self.progress
        perf, nperf = self.performance.get(subject), self.performance_n.get(subject, 0)
        if perf is not None and nperf >= 5:
            adj = max(-0.7, min(0.5, (perf - 0.65) * 1.6))
            base += adj * min(1.0, nperf / 10)
        behaviour = self.settings.get("difficulty_behaviour", "adaptive")
        base += {"stretch": 0.3, "consolidate": -0.3, "steady": 0.0, "adaptive": 0.0}.get(behaviour, 0.0)
        base += self.profile.difficulty_shift
        return max(1.0, min(3.0, base))

    def item_target_difficulty(self, subject: str, item_id: int | None) -> float:
        """Per-item target: weak topics get easier questions, strong topics keep stretching."""
        t = self.target_difficulty(subject)
        m = self.mastery.get(item_id or -1)
        if m is not None and m.attempts >= 3:
            t += max(-0.6, min(0.4, (m.mastery - 0.6) * 1.2))
        return max(float(self.profile.difficulty_floor if subject == "MATHS" else 1), min(3.0, t))


# ---------------------------------------------------------------------- builders ---
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
        except (KeyError, ValueError, TypeError):
            continue
    return "normal"


def _learned_on(plan: dict[int, LearningPlanItem], today: date) -> dict[int, date]:
    """When each LEARNED/REVISION item was finished. ``status_changed_at`` is exact for items the
    student advanced through, but a mid-year setup marks every earlier item LEARNED at once; those
    bulk changes are spread back from the bulk date by position (about a week per subtopic)."""
    out: dict[int, date] = {}
    by_subject_day: dict[tuple[int, date], list[LearningPlanItem]] = {}
    for it in plan.values():
        if it.status in (LEARNED, REVISION) and not it.is_assumed_knowledge and it.status_changed_at:
            by_subject_day.setdefault((it.subject_id, it.status_changed_at.date()), []).append(it)
    for (_sid, day), items in by_subject_day.items():
        if len(items) < 3:
            for it in items:
                out[it.id] = day
            continue
        items.sort(key=lambda i: i.position, reverse=True)  # the last one learned first
        for k, it in enumerate(items):
            out[it.id] = min(day, today) - timedelta(days=7 * k)
    return out


def build_context(db: Session, today: date, mode: str | None = None, student_id: int = 1, *,
                  session_date: date | None = None, exclude_ids: set[int] | None = None,
                  catch_up: dict[int, dict] | None = None) -> StudentContext:
    """``today`` is the real day (history is read up to it). ``session_date`` is the day being
    planned (normally today; a resumed missed day keeps its own date but today's knowledge)."""
    s = st.all_settings(db)
    session_date = session_date or today
    plan = {p.id: p for p in db.execute(select(LearningPlanItem)).scalars()}
    mastery = {m.plan_item_id: m for m in db.execute(select(Mastery).where(Mastery.student_id == student_id)).scalars()}
    exposure = {e.question_id: e for e in db.execute(select(QuestionExposure).where(QuestionExposure.student_id == student_id)).scalars()}

    rev_items: dict[int, float] = {}
    rev_item_due: dict[int, date] = {}
    rev_qs: dict[int, float] = {}
    for r in db.execute(select(RevisionQueue).where(RevisionQueue.status == "open", RevisionQueue.due_date <= today)).scalars():
        overdue = (today - r.due_date).days
        pr = r.priority + min(0.5, overdue / 28)
        if r.plan_item_id:
            rev_items[r.plan_item_id] = max(rev_items.get(r.plan_item_id, 0), pr)
            rev_item_due[r.plan_item_id] = min(rev_item_due.get(r.plan_item_id, r.due_date), r.due_date)
        if r.question_id:
            rev_qs[r.question_id] = max(rev_qs.get(r.question_id, 0), pr)

    # ---- session history -------------------------------------------------------
    since = today - timedelta(days=HISTORY_DAYS)
    rows = db.execute(
        select(DailySession.id, DailySession.session_date, DailySession.status, DailySession.explanation,
               SessionQuestion.question_id, SessionQuestion.status, SessionQuestion.subject_code,
               Question.plan_item_id, Question.stimulus_id, Question.question_type, Question.category,
               Question.directive_verb, Question.marks)
        .join(SessionQuestion, SessionQuestion.session_id == DailySession.id)
        .join(Question, Question.id == SessionQuestion.question_id)
        .where(DailySession.session_date >= since, DailySession.student_id == student_id)
        .order_by(DailySession.session_date.desc(), SessionQuestion.position)
    ).all()
    stim_pairs = {sid: pw for sid, pw in db.execute(select(Stimulus.id, Stimulus.paired_with_id)).all()}
    stimulus_unit: dict[int, tuple[int, ...]] = {}
    for sid, pw in stim_pairs.items():
        members = {sid}
        if pw:
            members.add(pw)
        members |= {o for o, opw in stim_pairs.items() if opw == sid}
        stimulus_unit[sid] = tuple(sorted(members))

    served: dict[int, list[date]] = {}
    reserved: set[int] = set()
    stimulus_last_read: dict[int, date] = {}
    recent_plan_counts: dict[int, int] = {}
    item_last_practised: dict[int, date] = {}
    english_hist: list[dict] = []
    legal_hist: list[dict] = []
    session_order: list[date] = []
    session_items: dict[date, set[int]] = {}
    bands: dict[date, str] = {}
    recent_form_qids: dict[int, date] = {}
    for (sid, sdate, sstatus, expl, qid, sqstatus, subj, item_id, stim_id, qtype, cat, verb, marks) in rows:
        if sdate == session_date:
            continue  # the session being planned (or rebuilt)
        if sdate >= today:
            reserved.add(qid)  # today's own set while a missed day is resumed, or a future-dated session
            continue
        opened = sstatus in OPENED or sqstatus in ANSWERED or sqstatus == "draft"
        if not opened:
            if sstatus in ("generated", "in_progress"):
                reserved.add(qid)  # an earlier unfinished session still holds it
            continue
        served.setdefault(qid, []).append(sdate)
        if sdate not in session_items:
            session_order.append(sdate)
            session_items[sdate] = set()
            if isinstance(expl, dict) and isinstance(expl.get("difficulty"), dict) and expl["difficulty"].get("band"):
                bands[sdate] = expl["difficulty"]["band"]
        if item_id:
            session_items[sdate].add(item_id)
            item_last_practised[item_id] = max(item_last_practised.get(item_id, sdate), sdate)
        if stim_id and (sqstatus in ANSWERED or sqstatus == "draft" or sstatus in OPENED):
            for m in stimulus_unit.get(stim_id, (stim_id,)):
                stimulus_last_read[m] = max(stimulus_last_read.get(m, sdate), sdate)
        if subj == "MATHS" and (today - sdate).days <= 7:
            recent_form_qids[qid] = max(recent_form_qids.get(qid, sdate), sdate)
        if subj == "ENGLISH":
            english_hist.append({"date": sdate, "qid": qid, "category": cat, "stimulus_id": stim_id, "verb": verb, "marks": marks})
        if subj == "LEGAL":
            legal_hist.append({"date": sdate, "qid": qid, "type": qtype, "item": item_id, "stimulus_id": stim_id, "verb": verb, "marks": marks})
    for qid in served:
        served[qid].sort()
    for d in session_order[:3]:
        for item_id in session_items[d]:
            recent_plan_counts[item_id] = recent_plan_counts.get(item_id, 0) + 1
    last_session_items = session_items[session_order[0]] if session_order else set()

    # ---- attempts ---------------------------------------------------------------
    item_attempts: dict[int, int] = {}
    item_results: dict[int, list[float]] = {}
    item_methods: dict[int, set[str]] = {}
    item_attempt_dates: dict[int, list[tuple[date, int]]] = {}
    perf_series: dict[str, list[float]] = {"MATHS": [], "ENGLISH": [], "LEGAL": []}
    att_rows = db.execute(
        select(Attempt, Question.plan_item_id).join(Question, Attempt.question_id == Question.id)
        .where(Attempt.student_id == student_id).order_by(Attempt.submitted_at.desc()).limit(1500)
    ).all()
    for att, item_id in att_rows:
        d = att.submitted_at.date() if att.submitted_at else today
        if item_id:
            item_attempts[item_id] = item_attempts.get(item_id, 0) + 1
            item_attempt_dates.setdefault(item_id, []).append((d, att.question_id))
            item_last_practised[item_id] = max(item_last_practised.get(item_id, d), d)
        counts = getattr(att, "counts_for_mastery", True) is not False and not getattr(att, "after_reveal", False)
        if att.attempt_number != 1 or not counts:
            continue
        frac = 0.0 if att.skipped else att.fraction
        if item_id:
            res = item_results.setdefault(item_id, [])
            if len(res) < 12:
                res.append(frac)
                item_methods.setdefault(item_id, set()).add(att.marking_method or "deterministic")
        code = plan[item_id].subject.code if item_id in plan else None
        if code and len(perf_series[code]) < 20:
            perf_series[code].append(frac)
    performance: dict[str, float | None] = {}
    for code, series in perf_series.items():
        if not series:
            performance[code] = None
            continue
        ew, wsum = 0.0, 0.0  # exponentially weighted (newest first) -> smooth, but responsive
        for k, f in enumerate(series):
            w = 0.88 ** k
            ew += w * f
            wsum += w
        performance[code] = ew / wsum

    # ---- texts for near-duplicate checks and forms --------------------------------
    week_ago = today - timedelta(days=7)
    recent_ids = {qid for qid, ds in served.items() if ds[-1] >= week_ago} | {qid for qid, e in exposure.items() if e.last_seen >= week_ago}
    recent_texts: list[str] = []
    recent_forms: dict[str, date] = {}
    if recent_ids:
        for q in db.execute(select(Question).where(Question.id.in_(recent_ids))).scalars():
            recent_texts.append(q.question_text)
            if q.id in recent_form_qids:
                fk = form_key(q)
                recent_forms[fk] = max(recent_forms.get(fk, recent_form_qids[q.id]), recent_form_qids[q.id])

    # English course share over the last 10 sessions
    eng_recent = [h for h in english_hist if h["date"] in set(session_order[:10])]
    course_share = (sum(1 for h in eng_recent if h["category"] != "unseen") / len(eng_recent)) if eng_recent else None

    weights = dict(s.get("selection_weights") or st.DEFAULTS["selection_weights"])
    resolved = resolve_mode(session_date, s, mode)
    if resolved == "holiday":  # less new content, more revision and weakness work
        weights["current"] = weights.get("current", 0) * 0.6
        weights["spaced"] = weights.get("spaced", 0) * 1.5
        weights["weakness"] = weights.get("weakness", 0) * 1.3
    total = sum(max(0.0, float(v)) for v in weights.values()) or 1.0
    weights = {k: max(0.0, float(v)) / total for k, v in weights.items()}

    progress = _progress(today, s)
    phase = phase_for(progress, s)
    profile = build_profile(resolved, s)
    if resolved == "normal" and timed_today(phase, session_date.weekday(), s.get("weekdays") or [0, 1, 2, 3, 4]):
        profile.timed = True  # exam conditions on the phase's timed days

    return StudentContext(
        today=today, session_date=session_date, mode=resolved, profile=profile, settings=s, plan=plan, mastery=mastery,
        exposure=exposure, revision_items=rev_items, revision_item_due=rev_item_due, revision_questions=rev_qs, served=served,
        recent_texts=recent_texts, recent_plan_counts=recent_plan_counts, item_attempts=item_attempts, item_results=item_results,
        item_methods=item_methods, item_attempt_dates=item_attempt_dates, item_last_practised=item_last_practised,
        performance=performance, performance_n={k: len(v) for k, v in perf_series.items()}, progress=progress,
        stimulus_last_read=stimulus_last_read, stimulus_unit=stimulus_unit, recent_forms=recent_forms,
        english_history=english_hist, legal_history=legal_hist, sessions_before=len(session_order),
        last_session_items=last_session_items, previous_bands=sorted(bands.items(), reverse=True),
        reserved_ids=reserved, exclude_ids=set(exclude_ids or ()), catch_up=dict(catch_up or {}), weights=weights,
        learned_on=_learned_on(plan, today), recent_course_share=course_share, phase=phase,
    )


def now_utc():
    return utcnow()
