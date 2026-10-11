"""Loading Legal Studies content into the database and upgrading v1 databases (legal-09, v2 content).

- ``seed_questions``  creates questions from ``questions_legal.json`` (v1) and, when present,
  ``legal_v2.json`` (v2 format, see docs/V2_PLAN.md). Each question is attached to its syllabus
  SUB-AREA plan item (``LS-CRIME-YOUNG`` ...), never to the core topic header. Stimulus questions
  get a ``Stimulus`` row; option rationales, required elements, criteria and the evidence titles
  a model answer cites are kept in ``Question.solution``.
- ``seed_evidence``   loads ``legal_evidence.json`` and, when present, ``legal_evidence_v2.json``
  (with aliases, status and sub-area). Every seeded item starts UNVERIFIED.
- ``upgrade``         runs on every start (idempotent): it places sub-area plan items in order,
  sets their first statuses from the core topic's status, moves questions still attached to a
  core topic into the best sub-area, fills structure (aliases, status, sub-area) on v1 evidence
  items and refreshes the app's own v1 seeded questions (model answers without editor notes,
  required elements).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.models import (
    LearningPlanItem,
    LegalEvidence,
    LegalEvidenceTopic,
    Question,
    QuestionMapping,
    Source,
    Stimulus,
    Subject,
    SyllabusTopic,
)
from app.models.common import LEARNED, LEARNING, LOCKED, ORIGIN_GENERATED, REVISION, utcnow
from app.services import legal_plan as lp
from app.services import question_bank as qb
from app.services import settings as st

SEED_DIR = BASE_DIR / "data" / "seed"
SOURCE_TITLE = "HSC Companion — practice questions (Legal Studies)"
QUESTION_TYPES = ("mcq", "short_answer", "stimulus", "extended")

# v1 seeded questions -> sub-area (matched on a distinctive phrase of the question text)
V1_SUB_AREAS = [
    ("standard of proof required in a criminal trial", "LS-CRIME-TRIAL"),
    ("mental element of a crime", "LS-CRIME-NATURE"),
    ("strict liability offence is one where", "LS-CRIME-NATURE"),
    ("doli incapax", "LS-CRIME-YOUNG"),
    ("purpose of sentencing", "LS-CRIME-SENTENCING"),
    ("universal declaration of human rights was adopted", "LS-HR-NATURE"),
    ("human rights protection in australia", "LS-HR-ENFORCE"),
    ("self-determination", "LS-HR-NATURE"),
    ("summary and indictable", "LS-CRIME-NATURE"),
    ("bail laws", "LS-CRIME-INVESTIGATION"),
    ("diversionary programs", "LS-CRIME-YOUNG"),
    ("non-government organisations", "LS-HR-ENFORCE"),
    ("absence of a federal", "LS-HR-ENFORCE"),
    ("criminal trial process as a means of achieving justice", "LS-CRIME-TRIAL"),
    ("one contemporary human rights issue", "LS-HR-ISSUE"),
]


def _load(name: str, seed_dir: Path | None = None) -> dict | None:
    p = (seed_dir or SEED_DIR) / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _digest(data: dict | None) -> str | None:
    if data is None:
        return None
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _legal(db: Session) -> Subject:
    return db.execute(select(Subject).where(Subject.code == "LEGAL")).scalar_one()


def legal_source(db: Session) -> Source:
    return qb.get_or_create_source(db, SOURCE_TITLE, organisation="HSC Companion (generated)", subject_id=_legal(db).id,
                                   source_type="generated", tier=4,
                                   notes="App-authored questions, labelled GENERATED. Not past HSC questions. Model answers cite only "
                                         "items in your Legal evidence bank; check those items before relying on them.")


# ------------------------------------------------------------------------- criteria ---


def criteria_rows(criteria) -> list[dict]:
    """Normalise criteria to ``[{"mark": 4, "range": "4", "descriptor": "..."}]`` (v1 strings or v2 dicts)."""
    rows = []
    for c in criteria or []:
        if isinstance(c, dict):
            rows.append({"mark": c.get("mark"), "range": c.get("range") or (str(c.get("mark")) if c.get("mark") is not None else ""),
                         "descriptor": c.get("descriptor", "")})
        else:
            s = str(c)
            m = re.match(r"\s*(\d+(?:\s*[–-]\s*\d+)?)\s*marks?\s*[:\-–]\s*(.+)", s)
            if m:
                rng = m.group(1).replace(" ", "")
                top = int(re.findall(r"\d+", rng)[-1])
                rows.append({"mark": top, "range": rng, "descriptor": m.group(2).strip()})
            else:
                rows.append({"mark": None, "range": "", "descriptor": s})
    return rows


def criteria_text(criteria) -> str | None:
    lines = []
    for r in criteria_rows(criteria):
        if r["range"]:
            unit = "mark" if r["range"] == "1" else "marks"
            lines.append(f"{r['range']} {unit}: {r['descriptor']}")
        else:
            lines.append(r["descriptor"])
    return "\n".join(lines) or None


# ------------------------------------------------------------------------- questions ---


def sub_area_code(q: dict) -> str | None:
    """The sub-area a content item belongs to: explicit ``sub_area``, else the v1 table, else the
    keyword classifier (core topics only); options have no sub-areas."""
    if q.get("sub_area"):
        return q["sub_area"]
    topic = q.get("topic") or ""
    if topic not in lp.CORE_TOPICS:
        return None
    text = (q.get("text") or "").lower()
    for phrase, code in V1_SUB_AREAS:
        if phrase in text:
            return code
    return lp.classify(f"{q.get('text', '')} {q.get('model') or ''}", topic)[0]


def _plan_item(db: Session, code: str) -> LearningPlanItem | None:
    return db.execute(select(LearningPlanItem).where(LearningPlanItem.code == code)).scalar_one_or_none()


def _stimulus(db: Session, subject_id: int, src: Source, s: dict) -> Stimulus:
    row = db.execute(select(Stimulus).where(Stimulus.subject_id == subject_id, Stimulus.title == s["title"])).scalars().first()
    if row is not None:
        return row
    kind = s.get("kind") or "hypothetical scenario"
    hypothetical = "hypothetical" in kind.lower() or "hypothetical" in (s.get("title") or "").lower()
    attribution = ("Hypothetical material written for HSC Companion practice — invented people, events and figures; not real data."
                   if hypothetical else "Extract chosen for HSC Companion practice. Check it against the evidence items listed with it.")
    row = Stimulus(subject_id=subject_id, title=s["title"], form=kind, body=s.get("body") or "", author="HSC Companion",
                   attribution=attribution, provenance="generated_original", source_id=src.id)
    db.add(row)
    db.flush()
    return row


def solution_for(q: dict) -> dict:
    """Everything the marking and feedback need about a seeded Legal question."""
    sol: dict = {"model_answer_origin": "seeded"}
    for k in ("explanation", "option_rationales", "required_elements", "evidence_titles", "currency_note", "model_note", "sub_area"):
        if q.get(k):
            sol[k] = q[k]
    if q.get("criteria"):
        sol["criteria"] = criteria_rows(q["criteria"])
    if q.get("stimulus") and q["stimulus"].get("evidence_titles"):
        sol["stimulus_evidence_titles"] = list(q["stimulus"]["evidence_titles"])
    return sol


def create_question(db: Session, src: Source, q: dict) -> Question | None:
    qtype = q.get("type") or "short_answer"
    if qtype not in QUESTION_TYPES:
        raise ValueError(f"Unknown Legal question type {qtype!r} in {q.get('text', '')[:60]!r}")
    code = sub_area_code(q) or q["topic"]
    item = _plan_item(db, code) or _plan_item(db, q["topic"])
    if item is None:
        return None
    legal = _legal(db)
    stim = _stimulus(db, legal.id, src, q["stimulus"]) if q.get("stimulus") else None
    is_mcq = qtype == "mcq"
    sol = solution_for(q)
    if not is_mcq and not sol.get("explanation") and q.get("explanation"):
        sol["explanation"] = q["explanation"]
    return qb.create_question(
        db, subject_code="LEGAL", source_id=src.id, question_text=q["text"], marks=int(q["marks"]), question_type=qtype,
        directive_verb=q.get("verb"), difficulty=int(q.get("difficulty") or 2), topic_id=item.topic_id, plan_item_id=item.id,
        category="option" if q["topic"].startswith(lp.OPTION_PREFIX) else "core", historical_or_generated=ORIGIN_GENERATED,
        options=q.get("options") if is_mcq else None, answer={"type": "mcq", "value": q["answer"]} if is_mcq else None,
        solution=sol, model_answer=q.get("model"), marking_guideline=criteria_text(q.get("criteria")),
        legal_fact_currency=q.get("legal_fact_currency") or "check", stimulus_id=stim.id if stim else None,
        mapping_reason=(f"Practice question for '{item.title}' (GENERATED by HSC Companion, not a past HSC question). "
                        "Legal facts must be checked against the evidence bank."),
    )


def seed_questions(db: Session, seed_dir: Path | None = None) -> int:
    """Create the v1 and v2 Legal questions (idempotent: existing questions are matched by text)."""
    src = legal_source(db)
    n = 0
    for name in ("questions_legal.json", "legal_v2.json"):
        data = _load(name, seed_dir)
        if data is None:
            continue
        for q in data.get("questions", []):
            if create_question(db, src, q) is not None:
                n += 1
        st.set_(db, f"legal_seeded:{name}", _digest(data))
    db.flush()
    return n


# ------------------------------------------------------------------------- evidence ---

EVIDENCE_FIELDS = ("title", "item_type", "date", "jurisdiction", "issue", "summary", "legal_significance", "syllabus_link", "source",
                   "source_url", "source_type", "aliases", "status", "superseded_by", "sub_area", "issue_tags", "version_as_at", "related")


def _evidence_row(it: dict, note: str) -> LegalEvidence:
    data = {k: it[k] for k in EVIDENCE_FIELDS if k in it and it[k] is not None}
    data.setdefault("jurisdiction", "Unknown")
    data.setdefault("source", "Seeded from general knowledge")
    data.setdefault("legal_significance", "")
    data.setdefault("status", "unknown")
    return LegalEvidence(**data, reliability="unrated", verification_note=note, last_verified_date=None)


def seed_evidence(db: Session, seed_dir: Path | None = None) -> int:
    """Add seeded evidence items that are not in the bank yet (matched by exact title)."""
    n = 0
    topics = {t.code: t for t in db.execute(select(SyllabusTopic)).scalars()}
    existing = {e.title: e for e in db.execute(select(LegalEvidence)).scalars()}
    for name in ("legal_evidence.json", "legal_evidence_v2.json"):
        data = _load(name, seed_dir)
        if data is None:
            continue
        note = data.get("_note") or "Seeded from general knowledge. Not yet verified: check the source before relying on it."
        for it in data.get("items", []):
            row = existing.get(it["title"])
            if row is None:
                row = _evidence_row(it, note)
                db.add(row)
                db.flush()
                existing[row.title] = row
                for code in it.get("topics", []):
                    if code in topics:
                        db.add(LegalEvidenceTopic(evidence_id=row.id, topic_id=topics[code].id))
                n += 1
            else:
                _fill_structure(row, it)
    db.flush()
    return n


def _fill_structure(row: LegalEvidence, it: dict) -> None:
    """Fill v2 structure on an existing row without overwriting anything the student set."""
    if not row.aliases and it.get("aliases"):
        row.aliases = list(it["aliases"])
    if (row.status or "unknown") == "unknown" and it.get("status") and it["status"] != "unknown":
        row.status = it["status"]
    if not row.superseded_by and it.get("superseded_by"):
        row.superseded_by = it["superseded_by"]
    if not row.sub_area and it.get("sub_area"):
        row.sub_area = it["sub_area"]


# ------------------------------------------------------------------------- upgrade ---


def _grouped_order(items: list[LearningPlanItem]) -> list[LearningPlanItem]:
    """Core topic, its sub-areas, the next core topic, its sub-areas, other items, then options;
    the relative order inside each group is kept."""
    items = sorted(items, key=lambda i: (i.position, i.id))
    used: set[int] = set()
    out: list[LearningPlanItem] = []
    for parent in [i for i in items if i.code in lp.CORE_TOPICS]:
        out.append(parent)
        used.add(parent.id)
        for k in items:
            if k.code.startswith(parent.code + "-"):
                out.append(k)
                used.add(k.id)
    rest = [i for i in items if i.id not in used]
    out += [i for i in rest if not lp.is_option(i)] + [i for i in rest if lp.is_option(i)]
    return out


def place_sub_areas(db: Session) -> bool:
    """Renumber Legal plan positions when sub-areas are out of their group (after an upgrade)."""
    items = lp.legal_items(db)
    order = _grouped_order(items)
    current = sorted(items, key=lambda i: (i.position, i.id))
    if [i.id for i in order] == [i.id for i in current] and len({i.position for i in items}) == len(items):
        return False
    for pos, it in enumerate(order, start=1):
        it.position = pos
    db.flush()
    return True


def init_sub_area_statuses(db: Session) -> None:
    """Once per database: a core topic already finished (LEARNED/REVISION) or LOCKED in v1 passes its
    status to every new sub-area; a topic being LEARNING keeps the defaults (first sub-area LEARNING,
    the rest LOCKED) so untaught content stays out of daily sessions."""
    if st.get(db, "legal_sub_areas_initialised"):
        return
    for code in lp.CORE_TOPICS:
        parent = _plan_item(db, code)
        if parent is None:
            continue
        kids = lp.sub_areas_of(db, parent)
        if parent.status in (LEARNED, REVISION, LOCKED):
            for k in kids:
                if k.status != parent.status:
                    k.status, k.status_changed_at = parent.status, utcnow()
        elif kids and not any(k.status != LOCKED for k in kids):
            kids[0].status, kids[0].status_changed_at = LEARNING, utcnow()
        lp.sync_parent(db, parent)
    st.set_(db, "legal_sub_areas_initialised", True)


def move_core_questions(db: Session) -> int:
    """Questions still attached to a core topic header move to their best sub-area (v1 data and
    imports). The move is recorded as a reviewable mapping."""
    moved = 0
    for code in lp.CORE_TOPICS:
        parent = _plan_item(db, code)
        if parent is None or not lp.sub_areas_of(db, parent):
            continue
        for q in db.execute(select(Question).where(Question.plan_item_id == parent.id)).scalars().all():
            target_code = sub_area_code({"topic": code, "text": q.question_text, "model": q.model_answer or ""})
            hits = lp.classify(f"{q.question_text} {q.model_answer or ''}", code)[1]
            target = _plan_item(db, target_code)
            if target is None:
                continue
            q.plan_item_id = target.id
            explicit = any(p in q.question_text.lower() for p, _ in V1_SUB_AREAS)
            db.add(QuestionMapping(
                question_id=q.id, mapped_topic_id=q.topic_id, outcome_id=q.syllabus_outcome_id, relevance_classification=q.relevance_status,
                relevance_score=q.relevance_score, mapping_confidence=q.mapping_confidence if explicit else min(q.mapping_confidence, 0.6),
                mapping_reason=(f"Moved from '{parent.title}' to the sub-area '{target.title}' when Legal sub-areas were added"
                                + ("." if explicit else f" (keyword match, {hits} hit(s)); check this placement.")),
                mapped_by="v2-upgrade", review_status="approved" if explicit else "pending"))
            moved += 1
    db.flush()
    return moved


def refresh_v1_questions(db: Session, seed_dir: Path | None = None) -> int:
    """Bring the app's own v1 seeded Legal questions up to date (model answers without editor notes,
    required elements, criteria) when the content file changes. Only questions from the app's own
    source are touched."""
    data = _load("questions_legal.json", seed_dir)
    if data is None:
        return 0
    digest = _digest(data)
    if st.get(db, "legal_refreshed:questions_legal.json") == digest:
        return 0
    src = legal_source(db)
    n = 0
    from app.services.fingerprint import fingerprint

    for q in data.get("questions", []):
        row = db.execute(select(Question).where(Question.fingerprint == fingerprint(q["text"]), Question.source_id == src.id)).scalars().first()
        if row is None:
            continue
        sol = dict(row.solution or {})
        sol.update(solution_for(q))
        row.solution = sol
        if q.get("model"):
            row.model_answer = q["model"]
        if q.get("criteria"):
            row.marking_guideline = criteria_text(q["criteria"])
        if q.get("legal_fact_currency"):
            row.legal_fact_currency = q["legal_fact_currency"]
        n += 1
    st.set_(db, "legal_refreshed:questions_legal.json", digest)
    db.flush()
    return n


def upgrade(db: Session, seed_dir: Path | None = None) -> dict:
    """Idempotent v2 upgrade of the Legal plan and content (called on every start)."""
    if db.execute(select(Subject).where(Subject.code == "LEGAL")).scalar_one_or_none() is None:
        return {}
    placed = place_sub_areas(db)
    init_sub_area_statuses(db)
    loaded = 0
    for name in ("questions_legal.json", "legal_v2.json"):
        data = _load(name, seed_dir)
        if data is not None and st.get(db, f"legal_seeded:{name}") != _digest(data):
            src = legal_source(db)
            for q in data.get("questions", []):
                if create_question(db, src, q) is not None:
                    loaded += 1
            st.set_(db, f"legal_seeded:{name}", _digest(data))
    moved = move_core_questions(db)
    refreshed = refresh_v1_questions(db, seed_dir)
    for code in lp.CORE_TOPICS:
        parent = _plan_item(db, code)
        if parent is not None:
            lp.sync_parent(db, parent)
    db.flush()
    return {"placed": placed, "loaded": loaded, "moved": moved, "refreshed": refreshed}
