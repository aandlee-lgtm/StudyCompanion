"""Deterministic multi-week simulation of daily sessions (selection-21).

``run_sim`` builds a fresh database, optionally adds a synthetic bank the size of the v2 content
(30 reading sets, course tasks, Legal MCQ / short answer / stimulus / extended questions, and
multi-part Maths questions), then plays a student profile day by day: open Today, answer every
question through the real marking pipeline, advance the Maths plan every few study days. Every
served question is recorded with the facts the assertions need. No randomness except a seeded
RNG for the simulated student's answers."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

WEAK_ITEMS = {"1C", "1G", "1H", "2B", "2C", "Y11-TRIG", "Y11-PROB"}

_VOCAB = (
    "harbour lantern orchard granite meridian quarry willow ember tributary saddle compass ledger thimble"
    " vessel cinder mosaic parchment tidal frost beacon hollow summit canopy furrow glacier prism quill"
    " ridge spindle thicket umber valley wharf yarrow zephyr anchor bramble cobalt dune estuary fern"
    " gable heath inlet jetty kelp loam marsh nettle ochre pebble quartz rampart sedge thistle upland"
    " verge wattle alder basalt cairn delta eddy flint gorse hamlet isle juniper knoll lichen mesa"
    " nook oxbow pylon reef shoal tor urn vale weir yew acre bluff cove dell fjord grove"
).split()


def _words(rng: random.Random, n: int) -> str:
    return " ".join(rng.choice(_VOCAB) for _ in range(n))


@dataclass
class DayRecord:
    day: date
    mode: str
    number: int
    expected: float
    window: tuple[float, float]
    items: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    band: str | None = None
    resume_overlap: int | None = None


@dataclass
class SimResult:
    records: list[DayRecord]
    plan_codes: dict[int, str]
    y11_codes: set[str]

    def study_days(self) -> list[DayRecord]:
        return [r for r in self.records if r.items]


# ------------------------------------------------------------------ synthetic bank ---
def add_v2_like_bank(db) -> None:
    """A bank shaped like the v2 content packages (formats, marks, stimuli), with unique texts."""
    from sqlalchemy import select

    from app.models import LearningPlanItem, Stimulus, Subject
    from app.models.common import ORIGIN_GENERATED
    from app.services import question_bank as qb

    rng = random.Random(2027)

    def item(code):
        return db.execute(select(LearningPlanItem).where(LearningPlanItem.code == code)).scalar_one()

    def src(code):
        subj = db.execute(select(Subject).where(Subject.code == code)).scalar_one()
        return qb.get_or_create_source(db, f"Simulation bank ({code})", organisation="test", subject_id=subj.id, source_type="generated", tier=4), subj

    # English reading sets (3 questions, distinct marks) and course tasks
    esrc, eng = src("ENGLISH")
    unseen = item("EN-UNSEEN")
    forms = ["Prose fiction", "Memoir", "Personal essay", "Feature article", "Speech", "Poetry", "Media", "Hybrid", "Drama", "Letter"]
    verbs = [("Identify", 2), ("Explain", 3), ("Analyse", 4), ("Compare", 5), ("Evaluate", 5), ("Synthesise", 6), ("Analyse", 6), ("Explain", 4)]
    for k in range(30):
        body = "\n\n".join(_words(rng, 60) for _ in range(4))
        stim = Stimulus(subject_id=eng.id, title=f"Sim passage {k + 1}", form=forms[k % len(forms)], body=body, author="Sim",
                        attribution="Synthetic text for the simulation", provenance="generated_original", source_id=esrc.id)
        db.add(stim)
        db.flush()
        if k % 5 == 4:  # a paired set
            pair = Stimulus(subject_id=eng.id, title=f"Sim passage {k + 1} (pair)", form="Poetry", body=_words(rng, 120), author="Sim",
                            attribution="Synthetic", provenance="generated_original", source_id=esrc.id)
            db.add(pair)
            db.flush()
            stim.paired_with_id = pair.id
        marks = rng.sample([2, 3, 4, 5, 6], 3)
        for m in marks:
            verb = next(v for v, mk in verbs if mk == m) if any(mk == m for _v, mk in verbs) else "Explain"
            qb.create_question(db, subject_code="ENGLISH", source_id=esrc.id, stimulus_id=stim.id,
                               question_text=f"{verb} {_words(rng, 14)}?", marks=m, question_type="short_answer", directive_verb=verb,
                               difficulty=1 + (m >= 4) + (m >= 6), topic_id=unseen.topic_id, plan_item_id=unseen.id, category="unseen",
                               historical_or_generated=ORIGIN_GENERATED, model_answer="A detailed analytical response. " + _words(rng, 60),
                               mapping_reason="simulation")
    for code in ("EN-THE", "EN-CRAFT", "EN-THE", "EN-CRAFT", "EN-THE", "EN-CRAFT", "EN-THE", "EN-CRAFT", "EN-THE", "EN-CRAFT", "EN-THE", "EN-CRAFT"):
        it = item(code)
        m = rng.choice([4, 5, 6])
        qb.create_question(db, subject_code="ENGLISH", source_id=esrc.id, question_text=f"Analyse {_words(rng, 16)}.", marks=m,
                           question_type="short_answer", directive_verb="Analyse", difficulty=2, topic_id=it.topic_id, plan_item_id=it.id,
                           category="course", historical_or_generated=ORIGIN_GENERATED, mapping_reason="simulation")

    # Legal: MCQ, short answers across verb tiers, stimulus-based, extended responses
    lsrc, legal = src("LEGAL")
    sa_verbs = [("Identify", 2), ("Outline", 3), ("Describe", 4), ("Explain", 5), ("Analyse", 6), ("Discuss", 6), ("Assess", 7), ("Evaluate", 8)]
    for code in ("LS-CRIME", "LS-HR"):
        it = item(code)
        for k in range(14):
            ans = "ABCD"[k % 4]
            qb.create_question(db, subject_code="LEGAL", source_id=lsrc.id, question_text=f"Which {_words(rng, 12)}?", marks=1,
                               question_type="mcq", difficulty=1 + k % 2, topic_id=it.topic_id, plan_item_id=it.id, category="core",
                               historical_or_generated=ORIGIN_GENERATED, options=[f"{L}. {_words(rng, 4)}" for L in "ABCD"],
                               answer={"type": "mcq", "value": ans}, solution={"explanation": "simulation"}, mapping_reason="simulation")
        for k in range(12):
            verb, m = sa_verbs[k % len(sa_verbs)]
            qb.create_question(db, subject_code="LEGAL", source_id=lsrc.id, question_text=f"{verb} {_words(rng, 14)}.", marks=m,
                               question_type="short_answer", directive_verb=verb, difficulty=2, topic_id=it.topic_id, plan_item_id=it.id,
                               category="core", historical_or_generated=ORIGIN_GENERATED,
                               model_answer="The Crimes Act 1900 (NSW) " + _words(rng, 50), mapping_reason="simulation")
        for k in range(5):
            stim = Stimulus(subject_id=legal.id, title=f"Sim scenario {code} {k}", form="hypothetical scenario", body=_words(rng, 150),
                            author="Sim", attribution="Hypothetical scenario (simulation)", provenance="generated_original", source_id=lsrc.id)
            db.add(stim)
            db.flush()
            for verb, m in (("Explain", 4), ("Assess", 6)):
                qb.create_question(db, subject_code="LEGAL", source_id=lsrc.id, stimulus_id=stim.id,
                                   question_text=f"With reference to the scenario, {verb.lower()} {_words(rng, 12)}.", marks=m,
                                   question_type="stimulus", directive_verb=verb, difficulty=2, topic_id=it.topic_id, plan_item_id=it.id,
                                   category="core", historical_or_generated=ORIGIN_GENERATED, model_answer=_words(rng, 60),
                                   mapping_reason="simulation")
        for k in range(3):
            qb.create_question(db, subject_code="LEGAL", source_id=lsrc.id, question_text=f"Evaluate {_words(rng, 18)}.", marks=15,
                               question_type="extended", directive_verb="Evaluate", difficulty=3, topic_id=it.topic_id, plan_item_id=it.id,
                               category="core", historical_or_generated=ORIGIN_GENERATED, model_answer=_words(rng, 120),
                               mapping_reason="simulation")

    # Maths: multi-part 4–6 mark questions (one per item and difficulty 2/3) for the Year 12 items and Year 11 items
    msrc, maths = src("MATHS")
    for it in db.execute(select(LearningPlanItem).where(LearningPlanItem.subject_id == maths.id)).scalars():
        if it.enrichment:
            continue
        for d, m in ((2, 4), (3, 6), (2, 5)):
            val = str(rng.randint(2, 99))
            qb.create_question(db, subject_code="MATHS", source_id=msrc.id,
                               question_text=f"(a) {_words(rng, 10)} (b) {_words(rng, 10)} (c) hence find the value.", marks=m,
                               question_type="working", directive_verb="Find", difficulty=d, topic_id=it.topic_id, plan_item_id=it.id,
                               historical_or_generated=ORIGIN_GENERATED, answer={"type": "num", "value": val, "tol": 0},
                               solution={"steps": ["simulation"], "concept": "simulation", "technique": "simulation"},
                               mapping_reason="simulation")
    db.flush()


# ---------------------------------------------------------------------- profiles ---
def p_correct(profile: str, subject: str, item_code: str, difficulty: int, study_n: int) -> float:
    if profile == "strong":
        return 1.0
    if profile == "struggling":
        return {1: 0.45, 2: 0.2, 3: 0.08}.get(difficulty, 0.2)
    if profile == "mixed":
        if subject == "ENGLISH":
            return 0.55
        if subject == "LEGAL":
            return 0.65
        base = {1: 0.9, 2: 0.72, 3: 0.5}.get(difficulty, 0.7)
        if item_code in WEAK_ITEMS:
            base -= 0.6
        return max(0.03, base)
    if profile == "improving":
        return min(0.97, 0.25 + 0.012 * study_n) if subject == "MATHS" else 0.6
    raise ValueError(profile)


def _respond(q, good: bool) -> tuple[str, str]:
    ans = q.answer or {}
    if q.question_type == "mcq" or ans.get("type") == "mcq":
        right = (ans.get("value") or "A").upper()
        return (right if good else next(L for L in "ABCD" if L != right)), ("confident" if good else "unsure")
    if ans.get("type") == "set":
        return (", ".join(ans["values"]) if good else "999"), ("confident" if good else "unsure")
    if ans.get("value") is not None:
        return (str(ans["value"]) if good else "999999"), ("confident" if good else "unsure")
    if good:
        return (q.model_answer or "A detailed response that analyses and evaluates with evidence."), "confident"
    return "I think it shows something about it.", "unsure"


# ----------------------------------------------------------------------- runner ---
def run_sim(data_dir: Path, profile: str = "mixed", weeks: int = 4, *, start: date = date(2026, 10, 12), v2_bank: bool = True,
            advance_every: int = 4, mode: str | None = None, miss: set[date] | None = None, missaction: str | None = None,
            holiday: tuple[date, date] | None = None, seed: int = 7) -> SimResult:
    from sqlalchemy import select

    import app.services.plan as plan_mod
    from app.config import config
    from app.database_setup import prepare_database
    from app.db import SessionLocal
    from app.models import LearningPlanItem
    from app.selection.context import form_key, legal_format
    from app.services import assessment, clock, plan, sessions
    from app.services import settings as st

    config.data_dir = data_dir
    sim_now = {"d": start}
    orig_utcnow = plan_mod.utcnow
    plan_mod.utcnow = lambda: datetime.combine(sim_now["d"], time(8, 0))
    clock.set_today(start)
    try:
        dbfile = data_dir / "sim.db"
        if dbfile.exists():
            dbfile.unlink()
        prepare_database(f"sqlite:///{dbfile}")
        db = SessionLocal()
        st.set_(db, "setup_complete", True)
        st.set_(db, "year12_start_date", start.isoformat())
        st.set_(db, "setup_completed_on", start.isoformat())
        if mode:
            st.set_(db, "mode", mode)
        if holiday:
            st.set_(db, "holiday_ranges", [{"start": holiday[0].isoformat(), "end": holiday[1].isoformat(), "label": "sim"}])
        if v2_bank:
            add_v2_like_bank(db)
        db.commit()
        codes = {i.id: i.code for i in db.execute(select(LearningPlanItem)).scalars()}
        y11 = {i.code for i in db.execute(select(LearningPlanItem)).scalars() if i.is_assumed_knowledge and i.subject.code == "MATHS"}
        rng = random.Random(seed)
        records: list[DayRecord] = []
        study_n = 0
        day = start
        while day < start + timedelta(weeks=weeks):
            clock.set_today(day)
            sim_now["d"] = day
            if not sessions.study_day(db, day):
                day += timedelta(days=1)
                continue
            if miss and day in miss:
                records.append(DayRecord(day, "missed", 0, 0, (0, 0)))
                day += timedelta(days=1)
                continue
            sessions.record_missed(db, day)
            overlap = None
            resumed = None
            notice = sessions.missed_notice(db, day)
            if notice and missaction:
                target = sessions.resolve_missed(db, day, missaction)
                if missaction == "resume" and target is not None:
                    sessions.record_missed(db, day)  # what /today does next: the resumed day must stay open
                    resumed = target
                    today_sess = sessions.get_or_create_today(db)
                    overlap = len({q.question_id for q in target.questions} & {q.question_id for q in today_sess.questions})
            sess = sessions.get_or_create_today(db)
            db.commit()
            expl = sess.explanation or {}
            win = tuple(expl.get("window") or (0, 0))
            rec = DayRecord(day, sess.mode, sess.session_number, sess.expected_minutes, win, notes=list(expl.get("notes") or []),
                            band=(expl.get("difficulty") or {}).get("band"), resume_overlap=overlap)
            exp_before = {}
            from app.models import QuestionExposure

            for e in db.execute(select(QuestionExposure)).scalars():
                exp_before[e.question_id] = (e.last_seen, e.next_revision_date)
            for sq in sess.questions:
                q = sq.question
                bd = sq.score_breakdown or {}
                stim = q.stimulus
                rec.items.append({
                    "qid": q.id, "subject": sq.subject_code, "item": codes.get(q.plan_item_id), "bucket": bd.get("bucket"),
                    "kind": bd.get("kind"), "tier": bd.get("tier"), "flags": bd.get("flags") or [], "marks": q.marks,
                    "minutes": q.estimated_minutes, "type": q.question_type, "format": legal_format(q) if sq.subject_code == "LEGAL" else None,
                    "category": q.category, "verb": q.directive_verb, "difficulty": q.difficulty,
                    "unit": tuple(s.id for s in stim.reading_set()) if stim else None, "form": form_key(q),
                    "prev": exp_before.get(q.id), "reason": sq.reason,
                })
            for s_ in ([resumed] if resumed is not None and resumed.id != sess.id else []) + [sess]:
                for sq in s_.questions:
                    q = sq.question
                    item = db.get(LearningPlanItem, q.plan_item_id)
                    good = rng.random() < p_correct(profile, sq.subject_code, item.code, q.difficulty or 2, study_n)
                    resp, conf = _respond(q, good)
                    assessment.submit(db, q, resp, sq=sq, confidence=conf, time_seconds=60)
                sessions.maybe_complete(db, s_)
            db.commit()
            records.append(rec)
            study_n += 1
            if advance_every and study_n % advance_every == 0:
                plan.advance(db, "MATHS")
                db.commit()
            day += timedelta(days=1)
        db.close()
        return SimResult(records, codes, y11)
    finally:
        plan_mod.utcnow = orig_utcnow
        clock.set_today(None)
