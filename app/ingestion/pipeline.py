"""Historical paper ingestion pipeline (section 31).

check input -> read layout -> identify subject/course/year -> segment (coordinates) -> parse
guidelines (criteria, MCQ key, mapping grid) and stimulus booklet -> register source and retain
the PDFs -> per segment, in isolation: question + parts + guideline + stimulus links + crops ->
map to subtopics (offline or AI) -> validate -> auto-approve only when every gate passes,
otherwise the review queue.

Nothing in this module serves a question: approval only makes a question eligible, and the
selection engine still refuses it while any required subtopic is LOCKED."""
from __future__ import annotations

import re
import shutil
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIError
from app.ai.factory import get_provider
from app.config import config
from app.ingestion import mapping as mp
from app.ingestion import pdf as pdfmod
from app.ingestion.guidelines import GUIDELINE_KINDS, GuidelineSet, mcq_answer, parse_guidelines
from app.ingestion.layout import Layout, read_layout, render_regions
from app.ingestion.segment import SegmentResult, Unit, segment_layout
from app.ingestion.stimulus import READING_WPM, StimulusBlock, parse_stimulus_layout
from app.ingestion.validate import auto_approval_blockers, blocking, validate_question
from app.models import (
    LearningPlanItem,
    MarkingGuideline,
    Question,
    QuestionMapping,
    QuestionPart,
    Source,
    SourceDocument,
    Stimulus,
    Subject,
    SyllabusOutcome,
)
from app.models.common import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    ORIGIN_HISTORICAL,
    ORIGIN_SAMPLE,
    ORIGIN_TRIAL,
    REJECT,
)
from app.models.ingestion import QuestionStimulus, ReviewDecision
from app.services import question_bank as qb
from app.services import settings as st
from app.services.fingerprint import NEAR_DUPLICATE, import_fingerprint, shingles

ORIGIN_FOR_TYPE = {"hsc_exam": ORIGIN_HISTORICAL, "sample_exam": ORIGIN_SAMPLE, "trial": ORIGIN_TRIAL}
STRUCTURAL = {"text_short", "instruction", "no_directive", "marks_missing", "marks_range", "part_marks", "parts_sum", "segmentation",
              "mcq_options", "graph_crop"}

# sources-22: explicit allow-list and reject-list of courses
COURSES = [
    (re.compile(r"Mathematics Extension", re.I), "REJECT", "Mathematics Extension"),
    (re.compile(r"Mathematics Standard|Mathematics General", re.I), "REJECT", "Mathematics Standard"),
    (re.compile(r"English (Standard|Studies|Extension|EAL/?D)|English as an Additional Language", re.I), "REJECT", "a different English course"),
    (re.compile(r"Mathematics Advanced", re.I), "MATHS", None),
    (re.compile(r"English Advanced|English \(Advanced\)", re.I), "ENGLISH", None),
    (re.compile(r"Legal Studies", re.I), "LEGAL", None),
]


class ImportFailed(ValueError):
    """The paper could not be imported; nothing was registered."""


class DuplicateImport(ImportFailed):
    def __init__(self, message: str, source_id: int):
        super().__init__(message)
        self.source_id = source_id


@dataclass
class ImportReport:
    source_id: int | None
    document_id: int | None
    questions: int = 0
    approved: int = 0
    queued: int = 0
    rejected: int = 0
    needs_fix: int = 0
    duplicates: int = 0
    failed: int = 0
    stimuli: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    expected: list[dict] = field(default_factory=list)
    duplicate_list: list[dict] = field(default_factory=list)
    guideline_matched: int = 0
    guideline_total: int = 0
    mcq_keyed: int = 0
    mcq_total: int = 0
    segments: list[dict] = field(default_factory=list)
    question_ids: list[int] = field(default_factory=list)
    subject: str | None = None
    year: int | None = None
    status: str = "segmented"
    dry_run: bool = False

    @property
    def guideline_rate(self) -> float | None:
        return round(self.guideline_matched / self.guideline_total, 2) if self.guideline_total else None

    def as_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()}
        d["guideline_rate"] = self.guideline_rate
        return d


# ---------------------------------------------------------------------- detection ---
def detect_subject(text: str) -> str | None:
    """MATHS | ENGLISH | LEGAL, 'REJECT:<course>' for a course the app does not study, or None."""
    head = text[:3000]
    for pat, code, name in COURSES:
        if pat.search(head):
            return f"REJECT:{name}" if code == "REJECT" else code
    if re.search(r"\bMathematics\b", head):
        return "MATHS?"  # pre-2020 'Mathematics' (2 unit): needs confirmation
    return None


def detect_year(text: str) -> int | None:
    m = re.search(r"\b(19[89]\d|20[0-4]\d)\s+(HIGHER SCHOOL CERTIFICATE|HSC|Trial)", text[:3000], re.I) or re.search(r"\b(20[0-4]\d)\b", text[:1500])
    return int(m.group(1)) if m else None


def tier_for(db: Session, subject_id: int, source_type: str, year: int | None) -> tuple[int, str | None]:
    """Tier from the subject's syllabus version (sources-22). Returns (tier, note)."""
    if source_type == "sample_exam":
        return 1, None
    if source_type == "trial":
        return 3, None
    if source_type != "hsc_exam":
        return 4, None
    first = mp.first_hsc_year(db, subject_id)
    if first is None or year is None:
        return 2, "Tier to confirm: the paper year or the syllabus's first HSC year is unknown."
    return (1, None) if year >= first else (2, None)


def check_pdf(path: Path | None, label: str = "paper") -> None:
    if path is None:
        return
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise ImportFailed(f"The {label} file was not found: {p}")
    with open(p, "rb") as f:
        head = f.read(1024)
    if b"%PDF" not in head:
        raise ImportFailed(f"The {label} file is not a PDF ({p.name}).")


def store_pdf(path: Path, kind: str) -> tuple[Path, str]:
    digest = pdfmod.sha256(path)
    dest = config.sources_dir / f"{digest[:16]}_{kind}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(path, dest)
    return dest, digest


def register_source(db: Session, *, title: str, subject_code: str, year: int | None, source_type: str, url: str | None,
                    official: bool, organisation: str | None = None, notes: str | None = None) -> Source:
    subj = db.execute(select(Subject).where(Subject.code == subject_code)).scalar_one()
    tier, note = tier_for(db, subj.id, source_type, year)
    src = Source(title=title, organisation=organisation or ("NESA" if official else "School / trial"), year=year, subject_id=subj.id,
                 source_type=source_type, tier=tier, url=url, retrieved_date=date.today(), official=official,
                 notes="\n".join(x for x in [notes, note] if x) or None)
    db.add(src)
    db.flush()
    return src


# ----------------------------------------------------------------------- analysis ---
@dataclass
class Analysis:
    layout: Layout
    seg: SegmentResult
    guidelines: GuidelineSet | None
    stimuli: list[StimulusBlock]
    detected: str | None
    year: int | None
    text: str


def analyse(pdf_path: Path, guideline_pdf: Path | None = None, stimulus_pdf: Path | None = None) -> Analysis:
    lay = read_layout(pdf_path)
    text = lay.text
    seg = segment_layout(lay)
    seg.warnings = lay.warnings + seg.warnings
    gs = parse_guidelines(read_layout(guideline_pdf)) if guideline_pdf else None
    blocks = parse_stimulus_layout(read_layout(stimulus_pdf)) if stimulus_pdf else []
    return Analysis(lay, seg, gs, blocks, detect_subject(text), detect_year(text), text)


def segment_table(seg: SegmentResult, gs: GuidelineSet | None = None) -> list[dict]:
    rows = []
    for u in seg.units:
        matched = [k for k in u.keys if gs and gs.entry(k)]
        key = gs.mcq_key.get(int(u.number)) if (gs and u.section == "mcq" and u.number.isdigit()) else None
        rows.append({"number": u.number, "section": u.section_name or "", "type": u.section, "marks": u.marks, "pages": u.pages,
                     "parts": [p.label for p in u.parts], "options": len(u.options), "key": key, "guideline": bool(matched),
                     "visual": u.has_visual, "texts": u.stimulus_refs, "alternative": u.alternative_group,
                     "issues": list(u.issues), "preview": (u.text or "")[:110]})
    return rows


# ------------------------------------------------------------------------- import ---
def import_paper(db: Session, pdf_path: Path, *, title: str, source_type: str = "hsc_exam", subject_code: str | None = None,
                 year: int | None = None, url: str | None = None, guideline_pdf: Path | None = None, official: bool | None = None,
                 organisation: str | None = None, provider=None, stimulus_pdf: Path | None = None, guideline_kind: str | None = None,
                 dry_run: bool = False, replace: bool = False, confirm_subject: bool = False) -> ImportReport:
    pdf_path = Path(pdf_path)
    check_pdf(pdf_path, "paper")
    check_pdf(guideline_pdf, "marking guideline")
    check_pdf(stimulus_pdf, "stimulus booklet")
    try:
        an = analyse(pdf_path, guideline_pdf, stimulus_pdf)
    except Exception as exc:  # unreadable PDF: nothing has been registered or copied
        raise ImportFailed(f"The PDF could not be read: {exc}") from exc
    detected = an.detected
    if detected and detected.startswith("REJECT:"):
        raise ImportFailed(f"This looks like a {detected[7:]} paper, which is not one of your courses (Mathematics Advanced, "
                           "English Advanced, Legal Studies). Extension and other courses are never added to the question pool.")
    if subject_code and detected and detected.rstrip("?") != subject_code and not confirm_subject:
        raise ImportFailed(f"You chose {subject_code} but the paper looks like {detected.rstrip('?')}. Tick 'confirm subject' to import anyway.")
    if detected == "MATHS?" and not subject_code:
        an.seg.warnings.append("The paper says 'Mathematics' without 'Advanced' (pre-2020 2-unit course?): check the course before approving.")
    subject_code = subject_code or (detected.rstrip("?") if detected else None)
    if subject_code not in ("MATHS", "ENGLISH", "LEGAL"):
        raise ImportFailed("Could not identify the subject; choose it explicitly.")
    year = year or an.year
    official = (source_type in ("hsc_exam", "sample_exam")) if official is None else official
    kind = guideline_kind if guideline_kind in GUIDELINE_KINDS else (
        "official_nesa" if official and source_type in ("hsc_exam", "sample_exam") else ("school_trial" if source_type == "trial" else "third_party"))
    report = ImportReport(None, None, subject=subject_code, year=year, dry_run=dry_run)
    report.warnings += an.seg.warnings + (an.guidelines.warnings if an.guidelines else [])
    report.expected = an.seg.expected_vs_detected()
    report.segments = segment_table(an.seg, an.guidelines)
    _guideline_stats(report, an)
    report.stimuli = len(an.stimuli)
    if dry_run:
        report.status = "dry_run"
        return report

    digest = pdfmod.sha256(pdf_path)
    prev = db.execute(select(SourceDocument).where(SourceDocument.sha256 == digest, SourceDocument.kind == "paper",
                                                   SourceDocument.status != "deleted")).scalars().first()
    if prev is not None and not replace:
        raise DuplicateImport(f"This PDF was already imported as '{prev.source.title}' (source #{prev.source_id}). "
                              "Use 'Replace previous import' to re-segment it.", prev.source_id)
    subject = db.execute(select(Subject).where(Subject.code == subject_code)).scalar_one()
    if prev is not None and replace:
        src = prev.source
        removed = remove_unused_questions(db, src.id)
        report.warnings.append(f"Replacing the previous import: {removed} unattempted, unapproved question(s) removed; attempted or approved ones kept.")
        src.title, src.year, src.url = title, year, url or src.url
        prev.status = "replaced"
    else:
        src = register_source(db, title=title, subject_code=subject_code, year=year, source_type=source_type, url=url, official=official,
                              organisation=organisation)
    stored, _ = store_pdf(pdf_path, "paper")
    src.local_file = str(stored)
    doc = SourceDocument(source_id=src.id, kind="paper", local_file=str(stored), sha256=digest, page_count=len(an.layout.pages),
                         extraction_method=an.layout.method, status="extracted")
    db.add(doc)
    db.flush()
    report.source_id, report.document_id = src.id, doc.id
    log: list[str] = list(report.warnings)
    if guideline_pdf:
        gstored, gdigest = store_pdf(Path(guideline_pdf), "guideline")
        db.add(SourceDocument(source_id=src.id, kind="marking_guideline", local_file=str(gstored), sha256=gdigest,
                              page_count=0, extraction_method=an.layout.method, status="extracted", meta={"guideline_kind": kind}))
    stim_rows: dict[int, Stimulus] = {}
    if stimulus_pdf:
        sstored, sdigest = store_pdf(Path(stimulus_pdf), "stimulus")
        sdoc = SourceDocument(source_id=src.id, kind="stimulus", local_file=str(sstored), sha256=sdigest, page_count=0,
                              extraction_method=an.layout.method, status="extracted")
        db.add(sdoc)
        stim_rows = _create_stimuli(db, subject, src, an.stimuli, sstored, log)

    settings = st.all_settings(db)
    cands = mp.plan_candidates(db, subject.id)
    outcomes = [{"code": o.code, "description": o.description[:160]} for o in mp.official_outcomes(db, subject.id)]
    first_year = mp.first_hsc_year(db, subject.id)
    if provider is None:
        try:
            provider = get_provider(settings)
        except Exception as exc:  # pragma: no cover - misconfigured provider
            log.append(f"AI provider unavailable ({exc}); offline mapping used.")
            provider = None
    existing = _existing_index(db, subject.id)
    if not an.seg.units:
        report.warnings.append("No questions were detected automatically. Add them manually from the Question Library.")
        doc.status = "failed"
    for u in an.seg.units:
        try:
            with db.begin_nested():
                _import_unit(db, u, report=report, an=an, src=src, doc=doc, subject=subject, settings=settings, cands=cands,
                             outcomes=outcomes, first_year=first_year, provider=provider, kind=kind, official=official,
                             source_type=source_type, year=year, title=title, stim_rows=stim_rows, existing=existing, log=log)
        except Exception as exc:  # sources-03: one bad segment never aborts the paper
            report.failed += 1
            msg = f"Q{u.number}: could not be imported ({type(exc).__name__}: {exc})."
            report.errors.append(msg)
            log.append(msg + "\n" + traceback.format_exc(limit=3))
    if an.seg.units:
        doc.status = "segmented" if not report.failed else "segmented_with_errors"
    doc.log = "\n".join(log) or None
    doc.meta = {"expected": report.expected, "guideline_matched": report.guideline_matched, "guideline_total": report.guideline_total,
                "mcq_keyed": report.mcq_keyed, "mcq_total": report.mcq_total, "counts": {k: getattr(report, k) for k in
                ("questions", "approved", "queued", "rejected", "needs_fix", "duplicates", "failed", "stimuli")},
                "duplicates": report.duplicate_list, "errors": report.errors, "guideline_kind": kind if guideline_pdf else None}
    report.status = doc.status
    db.flush()
    return report


def _guideline_stats(report: ImportReport, an: Analysis) -> None:
    for u in an.seg.units:
        if u.section == "mcq":
            report.mcq_total += 1
            if an.guidelines and u.number.isdigit() and int(u.number) in an.guidelines.mcq_key:
                report.mcq_keyed += 1
        else:
            leaf = [p.key for p in u.parts] or u.keys[:1]
            for k in leaf:
                report.guideline_total += 1
                if an.guidelines and (an.guidelines.entry(k) or an.guidelines.entry(k.split("(")[0] if "(" in k else k)):
                    report.guideline_matched += 1


def _existing_index(db: Session, subject_id: int) -> dict:
    """Fingerprints and shingles of questions that count for duplicate matching (rejected and
    needs-fix questions are excluded, sources-17)."""
    fps: dict[str, Question] = {}
    sh: list[tuple[Question, set]] = []
    for q in db.execute(select(Question).where(Question.subject_id == subject_id, Question.approval_status != APPROVAL_REJECTED)).scalars():
        if (q.import_meta or {}).get("status") == "needs_fix":
            continue
        if q.fingerprint:
            fps[q.fingerprint] = q
        sh.append((q, shingles(q.question_text)))
    return {"fps": fps, "shingles": sh}


def _find_dup(existing: dict, fp: str, text: str) -> Question | None:
    if fp in existing["fps"]:
        return existing["fps"][fp]
    mine = shingles(text)
    if not mine:
        return None
    for q, s in existing["shingles"]:
        if s and min(len(s), len(mine)) / max(len(s), len(mine)) >= NEAR_DUPLICATE:
            if len(s & mine) / len(s | mine) >= NEAR_DUPLICATE:
                return q
    return None


def _qtype(subject_code: str, u: Unit, marks: int | None) -> str:
    if u.section == "mcq":
        return "mcq"
    if subject_code == "MATHS":
        return "working"
    if (marks or 0) >= 10:
        return "extended"
    if subject_code == "LEGAL" and re.search(r"\b(source|stimulus|scenario|table|extract)\b", u.text or "", re.I):
        return "stimulus"
    return "short_answer"


def _crop(db_doc_path: Path, u: Unit, qid: int, digest: str) -> str | None:
    regions = u.regions or []
    if not regions:
        return None
    label = re.sub(r"[^0-9a-z]+", "", u.number.lower()) or "q"
    out = config.renders_dir / f"{digest[:12]}_q{qid}_{label}.png"
    r = render_regions(db_doc_path, regions, out)
    return str(r) if r else None


def _import_unit(db: Session, u: Unit, *, report: ImportReport, an: Analysis, src: Source, doc: SourceDocument, subject: Subject,
                 settings: dict, cands, outcomes, first_year, provider, kind: str, official: bool, source_type: str, year: int | None,
                 title: str, stim_rows: dict[int, Stimulus], existing: dict, log: list[str]) -> None:
    code = subject.code
    gs = an.guidelines
    marks_missing = u.marks is None
    marks = u.marks if u.marks is not None else (u.heading_marks or 1)
    marks = max(1, min(int(marks), 40))  # impossible marks are clamped, never fatal (sources-03)
    qtype = _qtype(code, u, marks)
    fp = import_fingerprint(u.text, marks, u.options)
    dup = _find_dup(existing, fp, u.text)
    if dup is not None:
        report.duplicates += 1
        report.duplicate_list.append({"number": u.number, "existing_id": dup.id, "existing_source": dup.source.title if dup.source else None})
        return
    entries = gs.entries_for([p.key for p in u.parts] + u.keys) if gs else []
    if gs and not entries and u.section != "mcq":
        e = gs.entry(u.question) if u.question and u.question != u.number else None
        entries = [e] if e else []
    guideline_text = "\n\n".join(f"{e.label}\n{e.text}" for e in entries if e.text).strip() or None
    grid = gs.grid_for(u.keys) if gs else None
    forced, _ = mp.forced_topics(code, u, an.text)
    category = None
    if code == "ENGLISH":
        category = "unseen" if forced and forced[0] == "EN-UNSEEN" else "course"
    elif code == "LEGAL":
        category = "option" if forced and forced[0].startswith("LS-OPT") else "core"
    meta = {
        "status": "ready", "section": u.section_name, "section_title": u.section_title, "question_title": u.question_title,
        "heading_marks": u.heading_marks, "alternative_group": u.alternative_group, "keys": u.keys, "regions": [[p, list(r)] for p, r in u.regions],
        "figure_regions": [[p, list(r)] for p, r in u.figure_regions], "graph_options": u.graph_options, "stimulus_refs": u.stimulus_refs,
        "segment_issues": list(u.issues), "marks_missing": marks_missing, "guideline_kind": kind if entries else None,
        "document_id": doc.id, "pages": u.pages, "stem": u.stem or None,
    }
    if grid is not None:
        meta["grid"] = {"content": grid.content, "outcomes": grid.outcomes, "bands": grid.bands}
    if len(entries) == 1 and not u.parts:
        meta["guideline_top_mark"] = entries[0].top_mark
    q = Question(
        subject_id=subject.id, source_id=src.id, source_year=year, source_exam=title, question_number=u.number, source_page=u.page,
        question_text=u.text or "", marks=marks, question_type=qtype, options=u.options or None, category=category,
        historical_or_generated=ORIGIN_FOR_TYPE.get(source_type, ORIGIN_TRIAL), fingerprint=fp, approval_status=APPROVAL_PENDING,
        approved=False, marking_guideline=guideline_text, guideline_official=bool(entries) and kind == "official_nesa", import_meta=meta,
    )
    if u.section == "mcq" and gs and u.number.isdigit() and int(u.number) in gs.mcq_key:
        q.answer = mcq_answer(gs.mcq_key[int(u.number)])
    db.add(q)
    db.flush()
    # parts with their own marks and guidelines (sources-11)
    for i, sp in enumerate(u.parts):
        e = gs.entry(sp.key) if gs else None
        db.add(QuestionPart(question_id=q.id, label=sp.label, text=sp.text, marks=sp.marks or 0, position=i,
                            guideline=e.text if e else None,
                            meta={"key": sp.key, "hence": sp.hence, "guideline_top_mark": e.top_mark if e else None,
                                  "criteria": e.as_dict()["criteria"] if e else []}))
    for e in entries:
        db.add(MarkingGuideline(question_id=q.id, source_id=src.id, text=e.text or e.label, official=kind == "official_nesa", page=e.page,
                                label=e.key, kind=kind, criteria=e.as_dict()["criteria"], sample_answer=e.sample_answer or None, top_mark=e.top_mark))
    # stimuli ('Text 1', 'Texts 1 and 4')
    for pos, n in enumerate(u.stimulus_refs):
        s = stim_rows.get(n)
        if s is not None:
            db.add(QuestionStimulus(question_id=q.id, stimulus_id=s.id, label=f"Text {n}", position=pos))
            if q.stimulus_id is None:
                q.stimulus_id = s.id
    # crops: Maths written parts always (typeset maths extracts lossily), anything with a figure
    if u.has_visual or u.graph_options or (code == "MATHS" and u.section != "mcq"):
        img = _crop(Path(src.local_file), u, q.id, doc.sha256)
        if img:
            q.question_image = img
    db.flush()
    db.refresh(q)
    # mapping (offline first; AI when configured and generative)
    offline = mp.offline_proposal(code, u, cands, guideline_text=guideline_text or "", grid=grid, paper_text=an.text, year=year,
                                  first_hsc_year=first_year)
    prop = offline
    if provider is not None and getattr(provider, "generative", False):
        try:
            prop = mp.ai_proposal(provider, subject, u, cands, offline, guideline_text=guideline_text or "", grid=grid, source_title=title,
                                  year=year, first_hsc_year=first_year, outcomes=outcomes, paper_text=an.text)
        except (AIError, ValueError) as exc:
            offline.reason += f" (AI mapping failed: {exc})"
            prop = offline
    mp.apply_proposal(db, q, prop)
    verb = prop.directive_verb or mp.detect_verb(u.text or "")
    q.directive_verb = verb
    part_marks = [p.marks for p in u.parts if p.marks]
    q.difficulty = prop.difficulty or mp.difficulty_for(code, marks, part_marks, verb, grid.difficulty_hint if grid else None)
    reading = sum(len(re.findall(r"[A-Za-z’']+", s.body or "")) for s in {stim_rows[n] for n in u.stimulus_refs if n in stim_rows}) / READING_WPM
    q.estimated_minutes = round(qb.estimate_minutes(code, marks, qtype) + reading, 1)
    issues = validate_question(db, q, code)
    meta = dict(q.import_meta or {})
    meta["validation"] = [i.as_dict() for i in issues]
    meta["status"] = "needs_fix" if any(i.code in STRUCTURAL for i in blocking(issues)) else "ready"
    q.import_meta = meta
    threshold = float(settings.get("auto_approve_direct_confidence", 0.85))
    m = q.mappings[-1] if q.mappings else None
    if q.relevance_status == REJECT or q.is_extension:
        q.approval_status, q.approved = APPROVAL_REJECTED, False
        if m:
            m.review_status = "rejected"
        db.add(ReviewDecision(question_id=q.id, source_id=src.id, action="reject", actor="import", note=prop.reason[:500]))
        report.rejected += 1
    else:
        blockers = auto_approval_blockers(db, q, mapped_by=prop.mapped_by, subtopic_cited=prop.subtopic_cited, confidence=prop.confidence,
                                          threshold=threshold, tier=src.tier, subject_code=code)
        if not blockers and settings.get("auto_approve_imports", True) is not False:
            q.approval_status, q.approved = APPROVAL_APPROVED, True
            if m:
                m.review_status = "approved"
            db.add(ReviewDecision(question_id=q.id, source_id=src.id, action="auto_approve", actor="import",
                                  after={"plan_item_id": q.plan_item_id, "relevance": q.relevance_status}, note=prop.reason[:500]))
            report.approved += 1
        else:
            meta = dict(q.import_meta or {})
            meta["auto_approval_blockers"] = blockers[:8]
            q.import_meta = meta
            report.queued += 1
            if meta.get("status") == "needs_fix":
                report.needs_fix += 1
    report.questions += 1
    report.question_ids.append(q.id)
    db.flush()


def _create_stimuli(db: Session, subject: Subject, src: Source, blocks: list[StimulusBlock], stored: Path, log: list[str]) -> dict[int, Stimulus]:
    out: dict[int, Stimulus] = {}
    for b in blocks:
        try:
            with db.begin_nested():
                image = None
                if b.visual and b.regions:
                    r = render_regions(stored, b.regions, config.renders_dir / f"{stored.stem[:12]}_text{b.number}.png")
                    image = str(r) if r else None
                s = Stimulus(subject_id=subject.id, title=f"{b.title}", form=(b.form or None) and b.form[:60], body=b.body or None,
                             image_path=image, attribution=b.attribution or "", provenance="historical", source_id=src.id, source_page=b.page)
                db.add(s)
                db.flush()
                out[b.number] = s
                log.extend(b.issues)
        except Exception as exc:  # pragma: no cover - defensive
            log.append(f"Text {b.number}: could not be stored ({exc}).")
    return out


def remove_unused_questions(db: Session, source_id: int) -> int:
    """Delete a source's questions that were never attempted and never approved (used by
    'Replace previous import')."""
    from app.models import Attempt, QuestionExposure

    n = 0
    for q in db.execute(select(Question).where(Question.source_id == source_id)).scalars().all():
        used = db.execute(select(Attempt.id).where(Attempt.question_id == q.id).limit(1)).first() or \
            db.execute(select(QuestionExposure.id).where(QuestionExposure.question_id == q.id).limit(1)).first()
        if used or q.approval_status in (APPROVAL_APPROVED, "adapted", "retired"):  # keep sources of adapted copies
            continue
        delete_question_rows(db, q)
        n += 1
    db.flush()
    return n


def delete_question_rows(db: Session, q: Question) -> None:
    from sqlalchemy import delete, update

    from app.models.ingestion import QuestionOutcome, QuestionPlanItem

    for model in (QuestionPart, QuestionMapping, MarkingGuideline, QuestionStimulus, QuestionPlanItem, QuestionOutcome):
        db.execute(delete(model).where(model.question_id == q.id))
    db.execute(update(ReviewDecision).where(ReviewDecision.question_id == q.id).values(question_id=None))
    db.execute(update(Question).where(Question.generated_from_question_id == q.id).values(generated_from_question_id=None))
    db.delete(q)


# ----------------------------------------------------------- v1-compatible actions ---
def review_queue(db: Session) -> list[Question]:
    return list(db.execute(select(Question).where(Question.approval_status == APPROVAL_PENDING).order_by(Question.source_id, Question.id)).scalars())


def approve(db: Session, q: Question, *, adapted: bool = False) -> None:
    from app.ingestion import review

    if adapted:
        review.mark_adaptable(db, q)
        return
    review.approve(db, q)


def reject(db: Session, q: Question, reason: str = "") -> None:
    from app.ingestion import review

    review.reject(db, q, reason)


def edit_mapping(db: Session, q: Question, *, plan_item_id: int, relevance: str, reason: str, answer: dict | None = None) -> None:
    from app.ingestion import review

    review.save_edits(db, q, {"plan_item_ids": [plan_item_id], "relevance": relevance, "reason": reason, "answer": answer})


def map_question(db: Session, q: Question, subject: Subject, settings: dict, provider=None) -> QuestionMapping:
    """Re-map an existing question (v1 API): offline proposal, or AI when configured."""
    cands = mp.plan_candidates(db, subject.id)
    unit = Unit(number=q.question_number or "", text=q.question_text, marks=q.marks, page=q.source_page or 1,
                section="mcq" if q.question_type == "mcq" else "written", section_name=(q.import_meta or {}).get("section"),
                section_title=(q.import_meta or {}).get("section_title"), question_title=(q.import_meta or {}).get("question_title"))
    prop = mp.offline_proposal(subject.code, unit, cands, guideline_text=q.marking_guideline or "")
    provider = provider or get_provider(settings)
    if getattr(provider, "generative", False):
        try:
            prop = mp.ai_proposal(provider, subject, unit, cands, prop, guideline_text=q.marking_guideline or "",
                                  source_title=q.source.title if q.source else "", year=q.source_year)
        except (AIError, ValueError):
            pass
    return mp.apply_proposal(db, q, prop)


__all__ = ["import_paper", "ImportReport", "ImportFailed", "DuplicateImport", "detect_subject", "detect_year", "review_queue", "approve",
           "reject", "edit_mapping", "map_question", "LearningPlanItem", "SyllabusOutcome"]
