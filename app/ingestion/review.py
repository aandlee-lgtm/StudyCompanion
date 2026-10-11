"""Reviewer actions on imported questions (sources-12/13/18, english-11, legal-12).

Every action is recorded as a ``ReviewDecision`` (action, before, after, time). Approval always
passes through the validation gate; ADAPTABLE questions are never approved as written — the
adaptation editor creates a NEW question (origin ADAPTED, ``generated_from_question_id`` set)
and the original stays as a non-servable source question."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion import mapping as mp
from app.ingestion.validate import Issue, blocking, validate_question
from app.models import LearningPlanItem, Question, QuestionMapping, QuestionPart, Stimulus, Subject
from app.models.common import (
    ADAPTABLE,
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    DIRECT,
    ORIGIN_ADAPTED,
    RELEVANCE,
    REJECT,
)
from app.models.ingestion import QuestionStimulus, ReviewDecision
from app.services.fingerprint import import_fingerprint

APPROVAL_ADAPTED = "adapted"  # original kept as the non-servable source of an adapted copy
APPROVAL_RETIRED = "retired"  # was approved, withdrawn from the pool
APPROVAL_STATES = (APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_REJECTED, APPROVAL_ADAPTED, APPROVAL_RETIRED)
CURRENCIES = ("current", "check", "outdated")


class ValidationFailed(ValueError):
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        super().__init__("; ".join(i.message for i in issues))


def snapshot(db: Session, q: Question) -> dict:
    return {
        "question_text": q.question_text, "marks": q.marks, "question_type": q.question_type, "options": q.options, "answer": q.answer,
        "plan_item_id": q.plan_item_id, "required": (q.import_meta or {}).get("required_plan_item_ids"), "relevance": q.relevance_status,
        "approval": q.approval_status, "category": q.category, "legal_fact_currency": q.legal_fact_currency,
        "outcome_id": q.syllabus_outcome_id, "parts": [[p.label, p.marks] for p in q.parts], "directive_verb": q.directive_verb,
        "difficulty": q.difficulty, "stimulus_id": q.stimulus_id,
    }


def record(db: Session, q: Question | None, action: str, *, before: dict | None = None, after: dict | None = None, note: str | None = None,
           actor: str = "reviewer", source_id: int | None = None) -> ReviewDecision:
    d = ReviewDecision(question_id=q.id if q else None, source_id=source_id or (q.source_id if q else None), action=action, actor=actor,
                       before=_jsonable(before), after=_jsonable(after), note=(note or None) and note[:2000])
    db.add(d)
    return d


def _jsonable(d):
    if d is None:
        return None
    import json

    return json.loads(json.dumps(d, default=str))


def _subject_code(db: Session, q: Question) -> str:
    return db.get(Subject, q.subject_id).code


def gate(db: Session, q: Question) -> list[Issue]:
    return validate_question(db, q, _subject_code(db, q))


def refresh_validation(db: Session, q: Question) -> list[Issue]:
    issues = gate(db, q)
    meta = dict(q.import_meta or {})
    meta["validation"] = [i.as_dict() for i in issues]
    from app.ingestion.pipeline import STRUCTURAL

    meta["status"] = "needs_fix" if any(i.code in STRUCTURAL for i in blocking(issues)) else "ready"
    q.import_meta = meta
    return issues


# ------------------------------------------------------------------------ actions ---
def approve(db: Session, q: Question, *, note: str | None = None) -> None:
    issues = blocking(gate(db, q))
    if issues:
        refresh_validation(db, q)
        raise ValidationFailed(issues)
    before = snapshot(db, q)
    q.approval_status, q.approved = APPROVAL_APPROVED, True
    if _subject_code(db, q) == "LEGAL" and q.legal_fact_currency == "current" and q.facts_checked_on is None:
        q.facts_checked_on = date.today()
    if q.mappings:
        q.mappings[-1].review_status = "approved"
    meta = dict(q.import_meta or {})
    meta["reviewed_on"] = date.today().isoformat()
    meta.pop("retired", None)
    q.import_meta = meta
    refresh_validation(db, q)
    record(db, q, "approve", before=before, after=snapshot(db, q), note=note)
    db.flush()


def reject(db: Session, q: Question, reason: str = "") -> None:
    before = snapshot(db, q)
    q.approval_status, q.approved, q.relevance_status = APPROVAL_REJECTED, False, REJECT
    db.add(QuestionMapping(question_id=q.id, mapped_topic_id=q.topic_id, relevance_classification=REJECT, relevance_score=0,
                           mapping_confidence=1, mapping_reason=reason or "Rejected by reviewer.", mapped_by="human", review_status="rejected"))
    record(db, q, "reject", before=before, after=snapshot(db, q), note=reason)
    db.flush()


def retire(db: Session, q: Question, reason: str = "") -> None:
    """Withdraw an approved question from the pool (it keeps its attempts and history)."""
    before = snapshot(db, q)
    q.approval_status, q.approved = APPROVAL_RETIRED, False
    meta = dict(q.import_meta or {})
    meta["retired"] = {"on": date.today().isoformat(), "reason": reason}
    q.import_meta = meta
    record(db, q, "retire", before=before, after=snapshot(db, q), note=reason)
    db.flush()


def restore(db: Session, q: Question) -> None:
    """Back to the review queue (retired, rejected or adapted-source questions)."""
    before = snapshot(db, q)
    q.approval_status, q.approved = APPROVAL_PENDING, False
    if q.relevance_status == REJECT and not q.is_extension:
        q.relevance_status = (q.mappings[-2].relevance_classification if len(q.mappings) > 1 else "PARTIAL")
        if q.relevance_status == REJECT:
            q.relevance_status = "PARTIAL"
    refresh_validation(db, q)
    record(db, q, "restore", before=before, after=snapshot(db, q))
    db.flush()


def mark_adaptable(db: Session, q: Question, note: str = "") -> None:
    """'Mark adaptable' keeps the original unservable; the adaptation editor makes the copy."""
    before = snapshot(db, q)
    q.relevance_status = ADAPTABLE
    q.approval_status, q.approved = APPROVAL_PENDING, False
    refresh_validation(db, q)
    record(db, q, "mark_adaptable", before=before, after=snapshot(db, q), note=note)
    db.flush()


def _parse_answer(subject_code: str, qtype: str, letter: str | None, answer_type: str | None, answer_value: str | None) -> dict | None:
    if qtype == "mcq":
        if letter and letter.strip().upper() in ("A", "B", "C", "D"):
            return {"type": "mcq", "value": letter.strip().upper()}
        return None
    if answer_type and (answer_value or "").strip():
        if answer_type == "set":
            return {"type": "set", "values": [v.strip() for v in answer_value.split(",") if v.strip()]}
        return {"type": answer_type, "value": answer_value.strip(), "tol": 0}
    return None


def save_edits(db: Session, q: Question, data: dict, *, note: str | None = None) -> list[Issue]:
    """Apply reviewer edits. Keys (all optional): question_text, marks, question_type, options,
    answer (dict), answer_letter, answer_type, answer_value, plan_item_ids, primary_plan_item_id,
    relevance, reason, category, legal_fact_currency, student_rationale, directive_verb,
    difficulty, outcome_codes, parts [{id, text, marks}], segment_ack, stimulus_ids."""
    code = _subject_code(db, q)
    before = snapshot(db, q)
    meta = dict(q.import_meta or {})
    if "question_text" in data and data["question_text"] is not None and data["question_text"].strip() != (q.question_text or "").strip():
        q.question_text = data["question_text"].strip()
        meta["text_edited"] = True
    if data.get("marks") not in (None, ""):
        q.marks = int(data["marks"])
        meta["marks_missing"] = False
    if data.get("question_type") in ("mcq", "short_answer", "extended", "working", "stimulus"):
        q.question_type = data["question_type"]
    if data.get("options") is not None:
        opts = [o.strip() for o in data["options"] if o and o.strip()]
        q.options = [o if o[:2] in ("A.", "B.", "C.", "D.") else f"{'ABCD'[i]}. {o}" for i, o in enumerate(opts[:4])] or None
    ans = data.get("answer")
    if ans is None and any(data.get(k) for k in ("answer_letter", "answer_value")):
        ans = _parse_answer(code, q.question_type, data.get("answer_letter"), data.get("answer_type"), data.get("answer_value"))
    if ans is not None:
        q.answer = ans
    for p in data.get("parts") or []:
        part = db.get(QuestionPart, int(p["id"])) if p.get("id") else None
        if part is not None and part.question_id == q.id:
            if p.get("text") is not None:
                part.text = p["text"]
            if p.get("marks") not in (None, ""):
                part.marks = int(p["marks"])
    if data.get("segment_ack"):
        meta["segment_ack"] = True
    if data.get("category") in ("unseen", "course", "core", "option"):
        q.category = data["category"]
    if data.get("legal_fact_currency") in CURRENCIES:
        q.legal_fact_currency = data["legal_fact_currency"]
        if q.legal_fact_currency == "current":
            q.facts_checked_on = date.today()
    if data.get("student_rationale") is not None:
        meta["student_rationale"] = data["student_rationale"].strip() or None
    if data.get("directive_verb"):
        q.directive_verb = data["directive_verb"].strip()
    if data.get("difficulty") not in (None, ""):
        q.difficulty = max(1, min(3, int(data["difficulty"])))
    q.import_meta = meta
    mapping_changed = False
    ids = [int(i) for i in (data.get("plan_item_ids") or []) if str(i).strip() and int(i)]
    if ids and (sorted(ids) != sorted(meta.get("required_plan_item_ids") or ([q.plan_item_id] if q.plan_item_id else []))
                or (data.get("primary_plan_item_id") and int(data["primary_plan_item_id"]) != q.plan_item_id)):
        mp.set_required_items(db, q, ids, primary_id=int(data["primary_plan_item_id"]) if data.get("primary_plan_item_id") else None)
        meta = dict(q.import_meta or {})
        meta["mapping_state"] = "MAPPED" if q.plan_item_id else "UNMAPPED"
        q.import_meta = meta
        mapping_changed = True
    if data.get("relevance") in RELEVANCE and data["relevance"] != q.relevance_status:
        q.relevance_status = data["relevance"]
        q.relevance_score = 1.0 if q.relevance_status == DIRECT else (0.0 if q.relevance_status == REJECT else 0.6)
        mapping_changed = True
    if data.get("outcome_codes") is not None:
        mp.set_outcomes(db, q, [c for c in data["outcome_codes"] if c])
        mapping_changed = True
    if data.get("stimulus_ids") is not None:
        link_stimuli(db, q, [int(i) for i in data["stimulus_ids"] if str(i).strip()])
    if mapping_changed:
        item = db.get(LearningPlanItem, q.plan_item_id) if q.plan_item_id else None
        q.mapping_confidence = 1.0
        db.add(QuestionMapping(question_id=q.id, mapped_topic_id=q.topic_id, focus_area=item.topic.name if item and item.topic else None,
                               outcome_id=q.syllabus_outcome_id, relevance_classification=q.relevance_status, relevance_score=q.relevance_score,
                               mapping_confidence=1.0, mapping_reason=data.get("reason") or "Mapping edited by reviewer.", mapped_by="human",
                               review_status="edited", skill_relevance=(q.import_meta or {}).get("skill_relevance"),
                               legal_fact_currency=q.legal_fact_currency))
    q.fingerprint = import_fingerprint(q.question_text, q.marks, q.options)
    db.flush()
    db.refresh(q)
    issues = refresh_validation(db, q)
    if q.relevance_status == REJECT and q.approval_status != APPROVAL_REJECTED:
        q.approval_status, q.approved = APPROVAL_REJECTED, False
    elif q.approved and blocking(issues):
        q.approval_status, q.approved = APPROVAL_PENDING, False  # an edit that breaks a gate withdraws approval
    record(db, q, "edit" if not mapping_changed else "remap", before=before, after=snapshot(db, q), note=note or data.get("reason"))
    db.flush()
    return issues


def keep_parts(db: Session, q: Question, keep_ids: list[int], note: str = "") -> list[Issue]:
    """PARTIAL questions: keep only the aligned parts (the stem is kept)."""
    before = snapshot(db, q)
    keep = [p for p in q.parts if p.id in keep_ids]
    if not keep:
        raise ValueError("Choose at least one part to keep.")
    for p in list(q.parts):
        if p not in keep:
            q.parts.remove(p)
            db.delete(p)
    stem = (q.import_meta or {}).get("stem") or ""
    lines = [stem] if stem else []
    lines += [f"{p.label} {p.text}" + (f" ({p.marks} mark{'s' if p.marks != 1 else ''})" if p.marks else "") for p in keep]
    q.question_text = "\n\n".join(lines)
    q.marks = sum(p.marks or 0 for p in keep) or q.marks
    meta = dict(q.import_meta or {})
    meta["kept_parts"] = [p.label for p in keep]
    q.import_meta = meta
    q.fingerprint = import_fingerprint(q.question_text, q.marks, q.options)
    db.flush()
    db.refresh(q)
    issues = refresh_validation(db, q)
    record(db, q, "keep_parts", before=before, after=snapshot(db, q), note=note or f"Kept {', '.join(p.label for p in keep)}")
    db.flush()
    return issues


def link_stimuli(db: Session, q: Question, stimulus_ids: list[int]) -> None:
    from sqlalchemy import delete

    db.execute(delete(QuestionStimulus).where(QuestionStimulus.question_id == q.id))
    q.stimulus_id = None
    for pos, sid in enumerate(dict.fromkeys(stimulus_ids)):
        s = db.get(Stimulus, sid)
        if s is None:
            continue
        import re

        m = re.match(r"^(Text \d+)", s.title or "")
        db.add(QuestionStimulus(question_id=q.id, stimulus_id=s.id, label=m.group(1) if m else None, position=pos))
        if q.stimulus_id is None:
            q.stimulus_id = s.id
    db.flush()


def create_stimulus(db: Session, q: Question, *, title: str, body: str, form: str | None, attribution: str, provenance: str,
                    author: str | None = None, page: int | None = None) -> Stimulus:
    """'Paste text' form in the review card: a stimulus with attribution and provenance."""
    if not attribution.strip():
        raise ValueError("Attribution is required for a stimulus.")
    if provenance not in ("historical", "public_domain", "licensed", "generated_original"):
        raise ValueError("Choose the provenance of the text.")
    s = Stimulus(subject_id=q.subject_id, title=title.strip() or "Text", form=(form or None) and form[:60], body=body.strip() or None,
                 author=author or None, attribution=attribution.strip(), provenance=provenance, source_id=q.source_id, source_page=page)
    db.add(s)
    db.flush()
    existing = [r.stimulus_id for r in db.execute(select(QuestionStimulus).where(QuestionStimulus.question_id == q.id)).scalars()]
    link_stimuli(db, q, existing + [s.id])
    record(db, q, "edit", after={"stimulus_created": s.id, "title": s.title}, note="Stimulus created in review")
    refresh_validation(db, q)
    return s


def label_for(q: Question) -> str:
    src = q.source.title if q.source else "unknown source"
    return f"{src}" + (f" Q{q.question_number}" if q.question_number else "")


def adapt(db: Session, q: Question, *, text: str, marks: int, plan_item_ids: list[int], note: str, directive_verb: str | None = None,
          answer: dict | None = None, model_answer: str | None = None, legal_fact_currency: str | None = None, category: str | None = None,
          stimulus_ids: list[int] | None = None, options: list[str] | None = None, by: str = "reviewer", approve_now: bool = True) -> Question:
    """Create the ADAPTED copy. The original becomes a non-servable source question."""
    if not (text or "").strip() or len(text.split()) < 4:
        raise ValueError("Write the adapted question text.")
    if not (note or "").strip():
        raise ValueError("An adaptation note is required (what was changed and why).")
    if (text or "").strip() == (q.question_text or "").strip():
        raise ValueError("The adapted text is identical to the original: edit it (or approve the original if it is DIRECT).")
    code = _subject_code(db, q)
    meta = {
        "adaptation": {"from_question_id": q.id, "from_label": label_for(q), "note": note.strip(), "date": date.today().isoformat(), "by": by},
        "student_rationale": (q.import_meta or {}).get("student_rationale"), "status": "ready",
    }
    new = Question(subject_id=q.subject_id, source_id=q.source_id, source_year=q.source_year, source_exam=q.source_exam,
                   question_number=q.question_number, source_page=q.source_page, question_text=text.strip(), question_image=None,
                   marks=int(marks), question_type=q.question_type if q.question_type != "mcq" or options else "short_answer",
                   directive_verb=directive_verb or mp.detect_verb(text), difficulty=q.difficulty, estimated_minutes=q.estimated_minutes,
                   category=category or q.category, relevance_status=DIRECT, relevance_score=1.0, mapping_confidence=1.0,
                   historical_or_generated=ORIGIN_ADAPTED, generated_from_question_id=q.id, options=options or (q.options if q.question_type == "mcq" else None),
                   answer=answer, model_answer=model_answer or None, marking_guideline=None, guideline_official=False,
                   approval_status=APPROVAL_PENDING, approved=False, import_meta=meta)
    if code == "LEGAL":
        new.legal_fact_currency = legal_fact_currency or "current"
        if new.legal_fact_currency == "current":
            new.facts_checked_on = date.today()
    new.fingerprint = import_fingerprint(new.question_text, new.marks, new.options)
    db.add(new)
    db.flush()
    mp.set_required_items(db, new, plan_item_ids or (q.import_meta or {}).get("required_plan_item_ids") or ([q.plan_item_id] if q.plan_item_id else []))
    m = new.import_meta or {}
    m["mapping_state"] = "MAPPED" if new.plan_item_id else "UNMAPPED"
    new.import_meta = m
    item = db.get(LearningPlanItem, new.plan_item_id) if new.plan_item_id else None
    db.add(QuestionMapping(question_id=new.id, mapped_topic_id=new.topic_id, focus_area=item.topic.name if item and item.topic else None,
                           relevance_classification=DIRECT, relevance_score=1.0, mapping_confidence=1.0,
                           mapping_reason=f"Adapted from {label_for(q)}: {note.strip()}", mapped_by="human", review_status="edited",
                           legal_fact_currency=new.legal_fact_currency))
    link_stimuli(db, new, stimulus_ids if stimulus_ids is not None else
                 [r.stimulus_id for r in db.execute(select(QuestionStimulus).where(QuestionStimulus.question_id == q.id)).scalars()])
    before = snapshot(db, q)
    q.approval_status, q.approved = APPROVAL_ADAPTED, False
    if q.relevance_status == DIRECT:
        q.relevance_status = ADAPTABLE
    qm = dict(q.import_meta or {})
    qm.setdefault("adapted_into", []).append(new.id)
    q.import_meta = qm
    record(db, q, "adapt", before=before, after={"adapted_question_id": new.id, "text": new.question_text}, note=note)
    db.flush()
    db.refresh(new)
    if approve_now:
        try:
            approve(db, new, note="Approved on adaptation.")
        except ValidationFailed:
            pass  # stays in the queue with its issues shown
    else:
        refresh_validation(db, new)
    return new


def ai_adaptation_draft(db: Session, q: Question, provider, instructions: str = "") -> str:
    """Ask the AI for adapted wording (the reviewer edits and saves it)."""
    item = db.get(LearningPlanItem, q.plan_item_id) if q.plan_item_id else None
    ctx = {"subject": _subject_code(db, q), "subject_name": db.get(Subject, q.subject_id).name, "question": q.question_text,
           "marks": q.marks, "topic": item.title if item else "", "instructions": instructions or
           "Adapt this historical question to the 2027 syllabus and current law/prescribed texts; keep its skill and mark value."}
    res = provider.generate_question_variant(ctx)
    return res.question_text


def batch(db: Session, ids: list[int], action: str, reason: str = "") -> dict:
    done, failed = [], []
    for qid in ids:
        q = db.get(Question, qid)
        if q is None:
            failed.append({"id": qid, "error": "not found"})
            continue
        try:
            if action == "approve":
                approve(db, q, note="Batch approve")
            elif action == "reject":
                reject(db, q, reason or "Batch reject")
            elif action == "retire":
                retire(db, q, reason or "Batch retire")
            else:
                raise ValueError(f"Unknown batch action {action}")
            done.append(qid)
        except ValidationFailed as exc:
            failed.append({"id": qid, "error": "; ".join(i.message for i in exc.issues[:3])})
    return {"done": done, "failed": failed}
