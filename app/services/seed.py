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


def seed_english(db: Session) -> None:
    data = _load("questions_english.json")
    eng = db.execute(select(Subject).where(Subject.code == "ENGLISH")).scalar_one()
    src = qb.get_or_create_source(db, "HSC Companion — original unseen texts and practice questions (English Advanced)",
                                  organisation="HSC Companion (generated)", subject_id=eng.id, source_type="generated", tier=4,
                                  notes="Original passages written for this app. Not NESA texts. Model answers written for these questions.")
    unseen = _plan(db, "EN-UNSEEN")
    stimuli: dict[str, Stimulus] = {}
    for s in data["stimuli"]:
        st = db.execute(select(Stimulus).where(Stimulus.title == s["title"])).scalar_one_or_none()
        if st is None:
            st = Stimulus(subject_id=eng.id, title=s["title"], form=s["form"], body=s["body"], author=s["author"],
                          attribution=f"{s['author']}. Original text written for HSC Companion — not a NESA or published text.",
                          provenance="generated_original", source_id=src.id)
            db.add(st)
            db.flush()
        stimuli[s["key"]] = st
    for s in data["stimuli"]:
        if s.get("pair"):
            stimuli[s["key"]].paired_with_id = stimuli[s["pair"]].id
    for s in data["stimuli"]:
        for q in s.get("questions", []):
            st = stimuli[s["key"]]
            qb.create_question(
                db, subject_code="ENGLISH", source_id=src.id, stimulus_id=st.id, question_text=q["text"], marks=q["marks"],
                question_type="short_answer", directive_verb=q["verb"], difficulty=q["difficulty"], topic_id=unseen.topic_id,
                plan_item_id=unseen.id, category="unseen", historical_or_generated=ORIGIN_GENERATED, model_answer=q["model"],
                marking_guideline="\n".join(q["criteria"]), guideline_official=False,
                mapping_reason="Unseen-text question on an original passage; assesses reading and analysis skills examined in English Advanced.",
            )
    for q in data["course_questions"]:
        item = _plan(db, q["module"])
        qb.create_question(
            db, subject_code="ENGLISH", source_id=src.id, question_text=q["text"], marks=q["marks"], question_type="short_answer",
            directive_verb=q["verb"], difficulty=q["difficulty"], topic_id=item.topic_id, plan_item_id=item.id, category="course",
            historical_or_generated=ORIGIN_GENERATED, solution={"guidance": q["guidance"]},
            mapping_reason=f"Course-linked practice for '{item.title}' using the student's prescribed text(s).",
        )


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


def seed_templates_for_open_items(db: Session) -> int:
    created = 0
    for item in db.execute(select(LearningPlanItem).where(LearningPlanItem.status != "LOCKED")).scalars():
        if item.subject.code == "MATHS":
            created += qb.ensure_template_questions(db, item)
    return created


def seed_all(db: Session, with_templates: bool = True) -> None:
    seed_curriculum(db)
    if db.execute(select(Question.id).limit(1)).first() is None:
        seed_english(db)
        seed_legal(db)
        seed_maths_handwritten(db)
    seed_legal_evidence(db)
    if with_templates:
        seed_templates_for_open_items(db)
    db.flush()


def seed_files() -> list[Path]:
    return sorted(SEED_DIR.glob("*.json"))
