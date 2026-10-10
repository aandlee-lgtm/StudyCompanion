"""Historical paper ingestion pipeline (section 31):

register source -> keep original PDF -> extract text -> identify subject/year -> question
boundaries -> marks -> diagrams/stimuli -> marking guideline -> syllabus mapping ->
relevance -> review queue (uncertain) / pool (DIRECT, high confidence)."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIError
from app.ai.factory import get_provider
from app.ai.offline import OfflineProvider
from app.config import config
from app.ingestion import pdf as pdfmod
from app.ingestion.segment import segment, split_guideline
from app.models import LearningPlanItem, MarkingGuideline, Question, QuestionMapping, Source, SourceDocument, Subject, SyllabusTopic
from app.models.common import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    DIRECT,
    ORIGIN_HISTORICAL,
    ORIGIN_SAMPLE,
    ORIGIN_TRIAL,
    REJECT,
)
from app.services import question_bank as qb
from app.services import settings as st

SUBJECT_PATTERNS = {"MATHS": r"Mathematics Advanced|Mathematics\b(?! Extension)", "ENGLISH": r"English Advanced|English \(Advanced\)|English Paper",
                    "LEGAL": r"Legal Studies"}
ORIGIN_FOR_TYPE = {"hsc_exam": ORIGIN_HISTORICAL, "sample_exam": ORIGIN_SAMPLE, "trial": ORIGIN_TRIAL}


@dataclass
class ImportReport:
    source_id: int
    document_id: int
    questions: int = 0
    approved: int = 0
    queued: int = 0
    rejected: int = 0
    duplicates: int = 0
    warnings: list[str] = field(default_factory=list)


def detect_subject(text: str) -> str | None:
    if re.search(r"Mathematics Extension", text[:3000], re.I):
        return "MATHS_EXTENSION"
    for code, pat in SUBJECT_PATTERNS.items():
        if re.search(pat, text[:3000], re.I):
            return code
    return None


def detect_year(text: str) -> int | None:
    m = re.search(r"\b(19[89]\d|20[0-4]\d)\s+(HIGHER SCHOOL CERTIFICATE|HSC|Trial)", text[:3000], re.I) or re.search(r"\b(20[0-4]\d)\b", text[:1500])
    return int(m.group(1)) if m else None


def register_source(db: Session, *, title: str, subject_code: str, year: int | None, source_type: str, url: str | None,
                    official: bool, organisation: str | None = None, notes: str | None = None) -> Source:
    subj = db.execute(select(Subject).where(Subject.code == subject_code)).scalar_one()
    if source_type == "sample_exam":
        tier = 1
    elif source_type == "hsc_exam":
        tier = 1 if (year or 0) >= 2027 else 2
    elif source_type == "trial":
        tier = 3
    else:
        tier = 4
    src = Source(title=title, organisation=organisation or ("NESA" if official else "School / trial"), year=year, subject_id=subj.id,
                 source_type=source_type, tier=tier, url=url, retrieved_date=date.today(), official=official, notes=notes)
    db.add(src)
    db.flush()
    return src


def store_pdf(path: Path, kind: str) -> tuple[Path, str]:
    digest = pdfmod.sha256(path)
    dest = config.sources_dir / f"{digest[:16]}_{kind}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(path, dest)
    return dest, digest


def _topics(db: Session, subject_id: int) -> list[dict]:
    return [{"code": t.code, "name": t.name, "keywords": t.keywords or "", "kind": t.kind}
            for t in db.execute(select(SyllabusTopic).where(SyllabusTopic.subject_id == subject_id)).scalars()]


def map_question(db: Session, q: Question, subject: Subject, settings: dict, provider=None) -> QuestionMapping:
    provider = provider or get_provider(settings)
    ctx = {"subject": subject.code, "subject_name": subject.name, "question": q.question_text, "topics": _topics(db, subject.id),
           "source": q.source.title, "year": q.source_year}
    try:
        res = provider.map_to_syllabus(ctx)
        mapped_by = "ai" if provider.generative else "offline"
    except AIError as exc:
        res = OfflineProvider().map_to_syllabus(ctx)
        mapped_by = "offline"
        res.reason += f" (AI mapping failed: {exc})"
    topic = db.execute(select(SyllabusTopic).where(SyllabusTopic.code == res.topic_code)).scalar_one_or_none()
    relevance = REJECT if res.is_extension_content else res.relevance
    m = QuestionMapping(question_id=q.id, mapped_topic_id=topic.id if topic else None, focus_area=res.focus_area or (topic.name if topic else None),
                        content_descriptor=res.content_descriptor, relevance_classification=relevance, relevance_score=res.relevance_score,
                        mapping_confidence=res.confidence, mapping_reason=res.reason, skill_relevance=res.skill_relevance,
                        legal_fact_currency=res.legal_fact_currency, mapped_by=mapped_by, review_status="pending")
    db.add(m)
    q.topic_id = topic.id if topic else None
    q.relevance_status, q.relevance_score, q.mapping_confidence = relevance, res.relevance_score, res.confidence
    q.is_extension = res.is_extension_content
    q.legal_fact_currency = res.legal_fact_currency
    if topic:
        item = db.execute(select(LearningPlanItem).where(LearningPlanItem.topic_id == topic.id).order_by(LearningPlanItem.position)).scalars().first()
        q.plan_item_id = item.id if item else None
        q.syllabus_outcome_id = qb.outcome_for_topic(db, topic.id)
    threshold = float(settings.get("auto_approve_direct_confidence", 0.85))
    if relevance == REJECT:
        q.approval_status, q.approved, m.review_status = APPROVAL_REJECTED, False, "rejected"
    elif relevance == DIRECT and res.confidence >= threshold and mapped_by == "ai" and q.plan_item_id:
        q.approval_status, q.approved, m.review_status = APPROVAL_APPROVED, True, "approved"
    else:
        q.approval_status, q.approved = APPROVAL_PENDING, False  # PARTIAL / ADAPTABLE / uncertain -> review queue
    db.flush()
    return m


def import_paper(db: Session, pdf_path: Path, *, title: str, source_type: str = "hsc_exam", subject_code: str | None = None,
                 year: int | None = None, url: str | None = None, guideline_pdf: Path | None = None, official: bool | None = None,
                 organisation: str | None = None, provider=None) -> ImportReport:
    settings = st.all_settings(db)
    extracted = pdfmod.extract(pdf_path)
    text = extracted.text
    detected = detect_subject(text)
    if detected == "MATHS_EXTENSION" and (subject_code in (None, "MATHS")):
        raise ValueError("This looks like a Mathematics Extension paper. Extension content is never added to the question pool.")
    subject_code = subject_code or detected
    if subject_code not in ("MATHS", "ENGLISH", "LEGAL"):
        raise ValueError("Could not identify the subject; pass it explicitly.")
    year = year or detect_year(text)
    official = (source_type in ("hsc_exam", "sample_exam")) if official is None else official
    src = register_source(db, title=title, subject_code=subject_code, year=year, source_type=source_type, url=url, official=official, organisation=organisation)
    stored, digest = store_pdf(pdf_path, "paper")
    src.local_file = str(stored)
    doc = SourceDocument(source_id=src.id, kind="paper", local_file=str(stored), sha256=digest, page_count=len(extracted.pages),
                         extraction_method=extracted.method, status="extracted", log="\n".join(extracted.warnings))
    db.add(doc)
    db.flush()
    report = ImportReport(source_id=src.id, document_id=doc.id, warnings=list(extracted.warnings))

    guide_map: dict[str, str] = {}
    guide_src = None
    if guideline_pdf:
        g = pdfmod.extract(guideline_pdf)
        guide_map = split_guideline(g.text)
        gstored, gdigest = store_pdf(guideline_pdf, "guideline")
        guide_src = register_source(db, title=f"{title} — marking guidelines", subject_code=subject_code, year=year,
                                    source_type="marking_guideline", url=None, official=official, organisation=organisation)
        guide_src.local_file = str(gstored)
        db.add(SourceDocument(source_id=guide_src.id, kind="marking_guideline", local_file=str(gstored), sha256=gdigest,
                              page_count=len(g.pages), extraction_method=g.method, status="extracted"))

    subject = db.execute(select(Subject).where(Subject.code == subject_code)).scalar_one()
    segs = segment(extracted)
    if not segs:
        report.warnings.append("No questions were detected automatically. Add them manually from the Question Library.")
        doc.status = "failed"
    for sgm in segs:
        if qb.find_duplicate(db, subject.id, sgm.text, check_similar=True):
            report.duplicates += 1
            continue
        image = None
        if sgm.has_visual:
            region = pdfmod.find_region(stored, sgm.page, sgm.text.split("\n")[0][:40])
            out = config.renders_dir / f"{digest[:16]}_q{re.sub(r'[^0-9a-z]', '', sgm.number)}_p{sgm.page}.png"
            r = pdfmod.render_page(stored, sgm.page, out, clip=region)
            image = str(r) if r else None
        cls = (provider or OfflineProvider()).classify_question({"subject": subject_code, "subject_name": subject.name, "question": sgm.text}) \
            if sgm.section != "mcq" else None
        marks = sgm.marks or (cls.marks if cls and cls.marks else 1)
        qtype = "mcq" if sgm.section == "mcq" else (cls.question_type if cls else "short_answer")
        q = Question(
            subject_id=subject.id, source_id=src.id, source_year=year, source_exam=title, question_number=sgm.number, source_page=sgm.page,
            question_text=sgm.text, question_image=image, marks=marks, question_type=qtype, options=sgm.options or None,
            directive_verb=cls.directive_verb if cls else None, difficulty=(cls.difficulty if cls else 1),
            estimated_minutes=qb.estimate_minutes(subject_code, marks, qtype), historical_or_generated=ORIGIN_FOR_TYPE.get(source_type, ORIGIN_TRIAL),
            fingerprint=qb.fingerprint(sgm.text), approval_status=APPROVAL_PENDING, approved=False,
        )
        gl = guide_map.get(sgm.number) or guide_map.get(sgm.number.split("(")[0])
        if gl:
            q.marking_guideline, q.guideline_official = gl, bool(official)
        db.add(q)
        db.flush()
        if gl:
            db.add(MarkingGuideline(question_id=q.id, source_id=guide_src.id if guide_src else None, text=gl, official=bool(official)))
        m = map_question(db, q, subject, settings, provider)
        report.questions += 1
        if q.approval_status == APPROVAL_APPROVED:
            report.approved += 1
        elif q.approval_status == APPROVAL_REJECTED:
            report.rejected += 1
        else:
            report.queued += 1
    doc.status = "segmented" if segs else doc.status
    db.flush()
    return report


def review_queue(db: Session) -> list[Question]:
    return list(db.execute(select(Question).where(Question.approval_status == APPROVAL_PENDING).order_by(Question.source_id, Question.id)).scalars())


def approve(db: Session, q: Question, *, adapted: bool = False) -> None:
    q.approval_status, q.approved = APPROVAL_APPROVED, True
    if adapted:
        q.historical_or_generated = "ADAPTED"
    if q.mappings:
        q.mappings[-1].review_status = "approved"
    db.flush()


def reject(db: Session, q: Question, reason: str = "") -> None:
    q.approval_status, q.approved, q.relevance_status = APPROVAL_REJECTED, False, REJECT
    db.add(QuestionMapping(question_id=q.id, mapped_topic_id=q.topic_id, relevance_classification=REJECT, relevance_score=0,
                           mapping_confidence=1, mapping_reason=reason or "Rejected by reviewer.", mapped_by="human", review_status="rejected"))
    db.flush()


def edit_mapping(db: Session, q: Question, *, plan_item_id: int, relevance: str, reason: str, answer: dict | None = None) -> None:
    item = db.get(LearningPlanItem, plan_item_id)
    q.plan_item_id, q.topic_id = item.id, item.topic_id
    q.syllabus_outcome_id = qb.outcome_for_topic(db, item.topic_id)
    q.relevance_status = relevance
    q.mapping_confidence = 1.0
    if answer is not None:
        q.answer = answer
    db.add(QuestionMapping(question_id=q.id, mapped_topic_id=item.topic_id, focus_area=item.topic.name if item.topic else None,
                           relevance_classification=relevance, relevance_score=1.0 if relevance == DIRECT else 0.6, mapping_confidence=1.0,
                           mapping_reason=reason or "Mapping edited by reviewer.", mapped_by="human", review_status="edited"))
    if relevance == REJECT:
        q.approval_status, q.approved = APPROVAL_REJECTED, False
    db.flush()
