"""Idempotent seeding of the curriculum, prescribed texts, sources, practice questions and
the (unverified) Legal evidence bank from ``data/seed/*.json``."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.models import (
    LearningPlanItem,
    LegalEvidence,
    LegalEvidenceTopic,
    PrescribedText,
    Question,
    Stimulus,
    Student,
    Subject,
    SyllabusOutcome,
    SyllabusTopic,
    SyllabusVersion,
)
from app.models.common import ORIGIN_GENERATED
from app.services import question_bank as qb

SEED_DIR = BASE_DIR / "data" / "seed"


def _load(name: str) -> dict:
    return json.loads((SEED_DIR / name).read_text(encoding="utf-8"))


def seed_curriculum(db: Session) -> None:
    data = _load("curriculum.json")
    if db.get(Student, 1) is None:
        db.add(Student(id=1, name="Student", hsc_year=2027))
    subjects = {}
    for s in data["subjects"]:
        row = db.execute(select(Subject).where(Subject.code == s["code"])).scalar_one_or_none()
        if row is None:
            row = Subject(**s)
            db.add(row)
            db.flush()
        subjects[s["code"]] = row
    versions = {}
    for v in data["syllabus_versions"]:
        sid = subjects[v["subject"]].id
        row = db.execute(select(SyllabusVersion).where(SyllabusVersion.subject_id == sid)).scalars().first()
        if row is None:
            row = SyllabusVersion(subject_id=sid, **{k: v[k] for k in v if k != "subject"})
            db.add(row)
            db.flush()
        versions[v["subject"]] = row
    topics = {}
    for t in data["topics"]:
        row = db.execute(select(SyllabusTopic).where(SyllabusTopic.code == t["code"])).scalar_one_or_none()
        if row is None:
            row = SyllabusTopic(subject_id=subjects[t["subject"]].id, syllabus_version_id=versions[t["subject"]].id,
                                **{k: v for k, v in t.items() if k != "subject"})
            db.add(row)
            db.flush()
            db.add(SyllabusOutcome(
                subject_id=row.subject_id, topic_id=row.id, code=f"{row.code} (outcome codes not yet imported)",
                description=f"Outcomes for '{row.name}'. Placeholder until the official NESA outcomes are imported.",
                official=False,
            ))
        topics[t["code"]] = row
    for p in data["plan"]:
        sid = subjects[p["subject"]].id
        exists = db.execute(select(LearningPlanItem).where(LearningPlanItem.subject_id == sid, LearningPlanItem.code == p["code"])).scalar_one_or_none()
        if exists is None:
            fields = {k: v for k, v in p.items() if k not in ("subject", "topic")}
            db.add(LearningPlanItem(subject_id=sid, topic_id=topics[p["topic"]].id if p.get("topic") else None, **fields))
    for t in data["prescribed_texts"]:
        sid = subjects[t["subject"]].id
        exists = db.execute(select(PrescribedText).where(PrescribedText.title == t["title"], PrescribedText.author == t["author"])).scalar_one_or_none()
        if exists is None:
            db.add(PrescribedText(subject_id=sid, topic_id=topics[t["topic"]].id, **{k: v for k, v in t.items() if k not in ("subject", "topic")}))
    db.flush()


def _plan(db: Session, code: str) -> LearningPlanItem:
    return db.execute(select(LearningPlanItem).where(LearningPlanItem.code == code)).scalar_one()


def _english_solution(q: dict, *, texts_scope: list[int] | None = None, complexity: int | None = None, form: str | None = None,
                      set_key: str | None = None, module: str | None = None, passages: list[str] | None = None) -> dict:
    """Authored English marking data for ``Question.solution`` (see ``english_guided.meta``)."""
    from app.marking import quotes
    from app.services import english_guided as eg

    verb = q.get("verb")
    rt = q.get("response_type") or ("comparative" if (verb or "").lower() == "compare" else "analytical")
    ladder = eg.normalise_ladder(q.get("criteria"))
    model = q.get("model")
    status = None
    if model:
        status = "vetted"
        if passages and any(not c.found for c in quotes.verify_quotes(model, passages)):
            status = "quotes_unverified"  # never shown as a vetted model until fixed
    sol = {
        "response_type": rt, "demand": q.get("demand") or eg.default_demand(verb), "skill_tags": list(q.get("skill_tags") or []),
        "criteria": ladder, "checklist": list(q.get("checklist") or q.get("guidance") or []), "next_steps": dict(q.get("next_steps") or {}),
        "plan": q.get("plan"), "suggested_words": q.get("suggested_words"), "text_complexity": complexity, "form": form,
        "set_key": set_key, "module": module, "texts": texts_scope,
        "model_source": "app_authored" if model else ("app_authored_plan" if q.get("plan") else None), "model_status": status,
    }
    if q.get("guidance"):
        sol["guidance"] = list(q["guidance"])
    return {k: v for k, v in sol.items() if v not in (None, [], {}, "")}


def seed_english(db: Session, seed_dir: Path | None = None) -> dict:
    """Load English Advanced content: v1 ``questions_english.json`` plus, when present, the v2 reading
    sets (``english_sets.json``) and course-linked / Craft tasks (``english_course.json``).

    Idempotent: stimuli are matched by title and questions by fingerprint. Questions this loader
    created earlier get their authored marking data (ladder, checklist, next steps, model) refreshed,
    so an existing database picks up corrections; questions from other sources are never touched."""
    from app.services import english_guided as eg

    base = Path(seed_dir) if seed_dir else SEED_DIR
    eng = db.execute(select(Subject).where(Subject.code == "ENGLISH")).scalar_one()
    src = qb.get_or_create_source(db, "HSC Companion — original unseen texts and practice questions (English Advanced)",
                                  organisation="HSC Companion (generated)", subject_id=eng.id, source_type="generated", tier=4,
                                  notes="Original passages written for this app. Not NESA texts. Model answers written for these questions.")
    unseen = _plan(db, "EN-UNSEEN")
    counts = {"stimuli": 0, "questions": 0, "updated": 0}

    def stimulus(title: str, form: str, body: str, author: str | None, *, headnote: str | None = None, complexity: int | None = None,
                 meta: dict | None = None) -> Stimulus:
        st = db.execute(select(Stimulus).where(Stimulus.subject_id == eng.id, Stimulus.title == title)).scalars().first()
        author = author or "Original text (HSC Companion)"
        if st is None:
            st = Stimulus(subject_id=eng.id, title=title, form=form, body=body, author=author,
                          attribution=f"{author}. Original text written for HSC Companion — not a NESA or published text.",
                          provenance="generated_original", source_id=src.id)
            db.add(st)
            counts["stimuli"] += 1
        if st.source_id == src.id:
            st.headnote = headnote or st.headnote
            st.complexity = complexity or st.complexity
            st.meta = {**(st.meta or {}), **(meta or {})} or None
        db.flush()
        return st

    def question(q: dict, *, item: LearningPlanItem, category: str, stim: Stimulus | None, sol: dict, reason: str) -> Question:
        marks = int(q["marks"])
        rt = sol.get("response_type", "analytical")
        guideline = eg.ladder_text(sol["criteria"]) if sol.get("criteria") else None
        model = q.get("model")
        existing = qb.find_duplicate(db, eng.id, q["text"])
        if existing is not None:
            if existing.source_id == src.id and (existing.solution or {}).get("model_source") in (None, "app_authored", "app_authored_plan"):
                merged = {**(existing.solution or {}), **sol}
                if merged != (existing.solution or {}) or (guideline and existing.marking_guideline != guideline) or (model and existing.model_answer != model):
                    existing.solution = merged
                    existing.marking_guideline = guideline or existing.marking_guideline
                    existing.model_answer = model or existing.model_answer
                    existing.estimated_minutes = eg.estimate_minutes(marks, rt, sol.get("suggested_words"))
                    counts["updated"] += 1
            return existing
        counts["questions"] += 1
        return qb.create_question(
            db, subject_code="ENGLISH", source_id=src.id, stimulus_id=stim.id if stim else None, question_text=q["text"], marks=marks,
            question_type="extended" if marks >= 10 else "short_answer", directive_verb=q.get("verb"),
            difficulty=int(q.get("difficulty") or (1 if marks <= 2 else (2 if marks <= 4 else 3))),
            estimated_minutes=eg.estimate_minutes(marks, rt, sol.get("suggested_words")), topic_id=item.topic_id, plan_item_id=item.id,
            category=category, historical_or_generated=ORIGIN_GENERATED, model_answer=model, solution=sol,
            marking_guideline=guideline, guideline_official=False, mapping_reason=reason,
        )

    unseen_reason = "Unseen-text question on an original passage; assesses reading and analysis skills examined in English Advanced."
    # ---- v1 stimuli and course questions
    v1 = base / "questions_english.json"
    data = json.loads(v1.read_text(encoding="utf-8")) if v1.exists() else None
    if data:
        stimuli: dict[str, Stimulus] = {}
        for s in data.get("stimuli", []):
            stimuli[s["key"]] = stimulus(s["title"], s["form"], s["body"], s.get("author"), headnote=s.get("headnote"),
                                         complexity=s.get("complexity"), meta={"key": s["key"]})
        for s in data.get("stimuli", []):
            if s.get("pair"):
                stimuli[s["key"]].paired_with_id = stimuli[s["pair"]].id
        db.flush()
        for s in data.get("stimuli", []):
            st = stimuli[s["key"]]
            reading = st.reading_set()
            for q in s.get("questions", []):
                scope = [0, 1] if q.get("paired") else eg.text_scope(q["text"], len(reading), q.get("verb"))
                sol = _english_solution(q, texts_scope=scope if len(reading) > 1 else None, complexity=s.get("complexity"), form=s["form"],
                                        set_key=s["key"], passages=[r.body or "" for r in reading])
                question(q, item=unseen, category="unseen", stim=st, sol=sol, reason=unseen_reason)
        for q in data.get("course_questions", []):
            item = _plan(db, q["module"])
            question(q, item=item, category="course", stim=None, sol=_english_solution(q, module=q["module"]),
                     reason=f"Course-linked practice for '{item.title}' using the student's prescribed text(s).")
    # ---- v2 reading sets
    path = base / "english_sets.json"
    if path.exists():
        for s in json.loads(path.read_text(encoding="utf-8")).get("sets", []):
            meta = {"key": s["key"], "theme_tags": s.get("theme_tags") or [], "length_words": s.get("length_words") or len((s["body"] or "").split())}
            main = stimulus(s["title"], s["form"], s["body"], s.get("author"), headnote=s.get("headnote"), complexity=s.get("complexity"),
                            meta={**meta, "role": "text1" if s.get("pair") else "single"})
            reading = [main]
            if s.get("pair"):
                p = s["pair"]
                partner = stimulus(p["title"], p.get("form") or s["form"], p["body"], p.get("author") or s.get("author"),
                                   headnote=p.get("headnote") or None, complexity=p.get("complexity") or s.get("complexity"),
                                   meta={"key": f"{s['key']}--text2", "set": s["key"], "role": "text2",
                                         "length_words": len((p["body"] or "").split())})
                if main.paired_with_id is None and not partner.paired_with_id:
                    main.paired_with_id = partner.id
                db.flush()
                reading = main.reading_set()
            for q in s.get("questions", []):
                scope = eg.text_scope(q["text"], len(reading), q.get("verb"))
                sol = _english_solution(q, texts_scope=scope if len(reading) > 1 else None, complexity=s.get("complexity"), form=s["form"],
                                        set_key=s["key"], passages=[r.body or "" for r in reading])
                question(q, item=unseen, category="unseen", stim=main, sol=sol, reason=unseen_reason)
    # ---- v2 course-linked and Craft tasks
    path = base / "english_course.json"
    if path.exists():
        for q in json.loads(path.read_text(encoding="utf-8")).get("questions", []):
            item = _plan(db, q["module"])
            kind = "Craft of Writing task" if q["module"] == "EN-CRAFT" else "Course-linked practice"
            question(q, item=item, category="course", stim=None, sol=_english_solution(q, module=q["module"]),
                     reason=f"{kind} for '{item.title}' (app-authored criteria and response plan; not a NESA question).")
    db.flush()
    return counts


def seed_legal(db: Session) -> None:
    """v1 and v2 Legal questions, each attached to its syllabus sub-area (see app.services.legal_content)."""
    from app.services import legal_content

    legal_content.seed_questions(db)


def seed_maths_handwritten(db: Session) -> None:
    data = _load("questions_maths.json")
    maths = db.execute(select(Subject).where(Subject.code == "MATHS")).scalar_one()
    src = qb.get_or_create_source(db, "HSC Companion — hand-written practice questions (Mathematics Advanced)",
                                  organisation="HSC Companion (generated)", subject_id=maths.id, source_type="generated", tier=4,
                                  notes="Multi-step questions written for the app. Not past HSC questions.")
    for q in data["questions"]:
        item = _plan(db, q["plan"])
        qb.create_question(
            db, subject_code="MATHS", source_id=src.id, question_text=q["text"], marks=q["marks"], difficulty=q["difficulty"],
            directive_verb=q["verb"], question_type=q.get("question_type", "working"), options=q.get("options"),
            topic_id=item.topic_id, plan_item_id=item.id, historical_or_generated=ORIGIN_GENERATED, answer=q["answer"],
            solution={"steps": q["steps"], "concept": q["concept"], "technique": q["technique"], "quicker": q.get("quicker"),
                      "common_errors": q.get("common_errors", [])},
            mapping_reason=f"Hand-written question for {item.code} ({item.topic.name if item.topic else ''}).",
        )


def seed_legal_evidence(db: Session) -> None:
    """v1 and v2 evidence items (all unverified), then the idempotent v2 Legal upgrade: sub-area plan
    items in place, questions moved off the core topic headers, new content loaded."""
    from app.services import legal_content

    legal_content.seed_evidence(db)
    legal_content.upgrade(db)


def upgrade_legal(db: Session) -> None:
    """The v2 Legal upgrade is idempotent and cheap, and runs on every start (not only when a seed
    file changed): it places sub-area plan items and moves questions imported onto a core topic header."""
    from app.services import legal_content

    legal_content.upgrade(db)


def seed_templates_for_open_items(db: Session) -> int:
    created = 0
    for item in db.execute(select(LearningPlanItem).where(LearningPlanItem.status != "LOCKED")).scalars():
        if item.subject.code == "MATHS":
            created += qb.ensure_template_questions(db, item)
    return created


def seed_signature() -> str:
    """Fingerprint of every seed file, so new content shipped with an app update is loaded into
    an existing database (loaders are idempotent: existing rows are matched, not duplicated)."""
    import hashlib

    h = hashlib.sha256()
    for f in seed_files():
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def seed_all(db: Session, with_templates: bool = True, force: bool = False) -> None:
    from app.services import settings as st

    seed_curriculum(db)
    signature = seed_signature()
    if force or st.get(db, "seed_signature") != signature:
        seed_english(db)
        seed_legal(db)
        seed_maths_handwritten(db)
        seed_legal_evidence(db)
        st.set_(db, "seed_signature", signature)
    else:
        upgrade_legal(db)
    if with_templates:
        seed_templates_for_open_items(db)
    db.flush()


def seed_files() -> list[Path]:
    return sorted(SEED_DIR.glob("*.json"))
