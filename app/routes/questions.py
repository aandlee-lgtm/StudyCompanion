"""Question library, question detail (reveal gate), review tool, adaptation editor, import and
source registry (owner: ingestion; sources-12/13/18/19/23, english-11, legal-12, adaptive-01)."""
from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingestion import pipeline, review
from app.ingestion.audit import audit_info
from app.ingestion.reveal import reveal_by_skipping, revealed
from app.ingestion.servable import blocked_reason
from app.models import (
    Attempt,
    LearningPlanItem,
    MarkingGuideline,
    Question,
    QuestionExposure,
    Source,
    SourceDocument,
    Stimulus,
    Subject,
    SyllabusOutcome,
    SyllabusTopic,
)
from app.models.common import APPROVAL_PENDING, ORIGIN_GENERATED, RELEVANCE
from app.models.ingestion import QuestionOutcome, QuestionStimulus, ReviewDecision
from app.routes.common import render, templates
from app.services import clock
from app.services import question_bank as qb
from app.services import settings as st

router = APIRouter()
templates.env.globals["audit_info"] = audit_info

PAGE = 50
BANDS = {"lt50": "Under 50%", "50to85": "50–85%", "gt85": "Over 85%", "never": "Never attempted"}
REVISION = {"overdue": "Overdue", "week": "Due this week", "later": "Later"}
SORTS = {"id": Question.id, "marks": Question.marks, "year": Question.source_year, "number": Question.question_number,
         "source": Question.source_id, "difficulty": Question.difficulty}


def _plan(db: Session) -> dict[int, LearningPlanItem]:
    return {p.id: p for p in db.execute(select(LearningPlanItem).order_by(LearningPlanItem.subject_id, LearningPlanItem.position)).scalars()}


def _get_q(db: Session, qid: int) -> Question:
    q = db.get(Question, qid)
    if q is None:
        raise ValueError("Question not found.")
    return q


def _back(url: str, qid: int | None = None, flash: str | None = None) -> RedirectResponse:
    if not url.startswith("/"):
        url = "/admin/review"
    base, _, frag = url.partition("#")
    if flash:
        base += ("&" if "?" in base else "?") + "flash=" + quote(flash[:300])
    frag = f"q{qid}" if qid else frag
    return RedirectResponse(base + (f"#{frag}" if frag else ""), status_code=303)


# ------------------------------------------------------------------------ library ---
@router.get("/questions")
def library(request: Request, db: Session = Depends(get_db), subject: str = "", year: str = "", source: str = "", topic: str = "",
            item: str = "", outcome: str = "", marks: str = "", difficulty: str = "", relevance: str = "", approval: str = "",
            attempted: str = "", origin: str = "", band: str = "", revision: str = "", q: str = "", sort: str = "id", desc: int = 0,
            page: int = 1):
    stmt = select(Question)
    if subject:
        stmt = stmt.join(Subject, Question.subject_id == Subject.id).where(Subject.code == subject)
    if year.isdigit():
        stmt = stmt.where(Question.source_year == int(year))
    if source.isdigit():
        stmt = stmt.where(Question.source_id == int(source))
    if topic.isdigit():
        stmt = stmt.where(Question.topic_id == int(topic))
    if item.isdigit():
        stmt = stmt.where(Question.plan_item_id == int(item))
    if outcome.isdigit():
        stmt = stmt.where(or_(Question.syllabus_outcome_id == int(outcome),
                              Question.id.in_(select(QuestionOutcome.question_id).where(QuestionOutcome.outcome_id == int(outcome)))))
    if marks.isdigit():
        stmt = stmt.where(Question.marks == int(marks))
    if difficulty.isdigit():
        stmt = stmt.where(Question.difficulty == int(difficulty))
    if relevance:
        stmt = stmt.where(Question.relevance_status == relevance)
    if approval:
        stmt = stmt.where(Question.approval_status == approval)
    if origin:
        stmt = stmt.where(Question.historical_or_generated == origin)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Question.question_text.ilike(like), Question.question_number.ilike(like), Question.source_exam.ilike(like)))
    seen = select(QuestionExposure.question_id)
    if attempted == "yes":
        stmt = stmt.where(Question.id.in_(seen))
    elif attempted == "no":
        stmt = stmt.where(Question.id.not_in(seen))
    if band == "never":
        stmt = stmt.where(Question.id.not_in(seen))
    elif band in BANDS:
        lo, hi = {"lt50": (-1, 0.5), "50to85": (0.5, 0.85), "gt85": (0.85, 2)}[band]
        stmt = stmt.where(Question.id.in_(select(QuestionExposure.question_id).where(QuestionExposure.mastery >= lo, QuestionExposure.mastery < hi)))
    if revision in REVISION:
        today = clock.today()
        e = QuestionExposure
        cond = {"overdue": e.next_revision_date < today,
                "week": (e.next_revision_date >= today) & (e.next_revision_date <= today + timedelta(days=7)),
                "later": e.next_revision_date > today + timedelta(days=7)}[revision]
        stmt = stmt.where(Question.id.in_(select(e.question_id).where(cond)))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    col = SORTS.get(sort, Question.id)
    stmt = stmt.order_by(col.desc() if desc else col, Question.id)
    page = max(1, page)
    qs = db.execute(stmt.offset((page - 1) * PAGE).limit(PAGE)).scalars().all()
    exposure = {e.question_id: e for e in db.execute(select(QuestionExposure).where(QuestionExposure.question_id.in_([x.id for x in qs]))).scalars()}
    plan = _plan(db)
    return render(request, "questions.html", qs=qs, total=total, page=page, page_size=PAGE, exposure=exposure, f=request.query_params,
                  sources=db.execute(select(Source).order_by(Source.title)).scalars().all(),
                  topics=db.execute(select(SyllabusTopic).order_by(SyllabusTopic.subject_id, SyllabusTopic.position)).scalars().all(),
                  plan=plan, plan_items=list(plan.values()),
                  outcomes=db.execute(select(SyllabusOutcome).order_by(SyllabusOutcome.subject_id, SyllabusOutcome.code)).scalars().all(),
                  pending=db.execute(select(func.count(Question.id)).where(Question.approval_status == APPROVAL_PENDING)).scalar_one(),
                  relevances=RELEVANCE, bands=BANDS, revisions=REVISION, blocked={x.id: blocked_reason(plan, x) for x in qs},
                  approvals=review.APPROVAL_STATES)


@router.get("/questions/{qid}")
def detail(qid: int, request: Request, db: Session = Depends(get_db)):
    q = db.get(Question, qid)
    if q is None:
        raise ValueError("Question not found.")
    attempts = db.execute(select(Attempt).where(Attempt.question_id == qid).order_by(Attempt.submitted_at)).scalars().all()
    exp = db.execute(select(QuestionExposure).where(QuestionExposure.question_id == qid)).scalar_one_or_none()
    plan = _plan(db)
    item = plan.get(q.plan_item_id) if q.plan_item_id else None
    decisions = db.execute(select(ReviewDecision).where(ReviewDecision.question_id == qid).order_by(ReviewDecision.id)).scalars().all()
    texts = db.execute(select(QuestionStimulus).where(QuestionStimulus.question_id == qid).order_by(QuestionStimulus.position)).scalars().all()
    guidelines = db.execute(select(MarkingGuideline).where(MarkingGuideline.question_id == qid).order_by(MarkingGuideline.id)).scalars().all()
    return render(request, "question_detail.html", q=q, attempts=attempts, exp=exp, item=item, code=db.get(Subject, q.subject_id).code,
                  revealed=revealed(db, q), admin_mode=bool(st.get(db, "admin_mode")), decisions=decisions, texts=texts,
                  guidelines=guidelines, required=[plan[i] for i in ((q.import_meta or {}).get("required_plan_item_ids") or []) if i in plan],
                  blocked=blocked_reason(plan, q), mapping=q.mappings[-1] if q.mappings else None,
                  adapted_from=db.get(Question, q.generated_from_question_id) if q.generated_from_question_id else None,
                  flash=request.query_params.get("flash"))


@router.post("/questions/{qid}/reveal")
def reveal(qid: int, db: Session = Depends(get_db)):
    q = db.get(Question, qid)
    if q is None:
        raise ValueError("Question not found.")
    reveal_by_skipping(db, q)
    review.record(db, q, "reveal", note="Solution revealed from the detail page (recorded as a skip).")
    db.commit()
    return RedirectResponse(f"/questions/{qid}#solution", status_code=303)


@router.post("/questions/{qid}/retire")
def retire(qid: int, reason: str = Form(""), db: Session = Depends(get_db)):
    review.retire(db, _get_q(db, qid), reason)
    db.commit()
    return _back(f"/questions/{qid}", flash="Retired: it will not be served again until restored.")


@router.post("/questions/{qid}/restore")
def restore(qid: int, db: Session = Depends(get_db)):
    review.restore(db, _get_q(db, qid))
    db.commit()
    return RedirectResponse(f"/admin/review/{qid}", status_code=303)


@router.post("/questions/new")
def new_question(db: Session = Depends(get_db), subject: str = Form(...), plan_item_id: int = Form(...), text: str = Form(...), marks: int = Form(1),
                 question_type: str = Form("short_answer"), difficulty: int = Form(2), directive_verb: str = Form(""), model_answer: str = Form(""),
                 answer_value: str = Form(""), source_title: str = Form("Manually entered questions"), origin: str = Form(ORIGIN_GENERATED)):
    item = db.get(LearningPlanItem, plan_item_id)
    subj = db.execute(select(Subject).where(Subject.code == subject)).scalar_one()
    if item is None or item.subject_id != subj.id:
        raise ValueError("Choose a subtopic of the same subject.")
    src = qb.get_or_create_source(db, source_title, organisation="Entered by the student", subject_id=subj.id,
                                  source_type="trial" if origin == "TRIAL" else "generated", tier=3 if origin == "TRIAL" else 4)
    qb.create_question(db, subject_code=subject, source_id=src.id, question_text=text, marks=marks, question_type=question_type, difficulty=difficulty,
                       directive_verb=directive_verb or None, topic_id=item.topic_id, plan_item_id=item.id, historical_or_generated=origin,
                       model_answer=model_answer or None, answer={"type": "num" if subject == "MATHS" else "mcq", "value": answer_value, "tol": 0} if answer_value else None,
                       mapping_reason="Entered manually and mapped by the student.", mapped_by="human")
    db.commit()
    return RedirectResponse("/questions?subject=" + subject, status_code=303)


# --------------------------------------------------------------------- review tool ---
def _review_ctx(db: Session) -> dict:
    plan = _plan(db)
    return {"plan": plan, "plan_items": list(plan.values()), "relevances": RELEVANCE,
            "outcomes": db.execute(select(SyllabusOutcome).where(SyllabusOutcome.official.is_(True)).order_by(SyllabusOutcome.code)).scalars().all(),
            "stimuli": db.execute(select(Stimulus).order_by(Stimulus.subject_id, Stimulus.id.desc())).scalars().all(),
            "currencies": review.CURRENCIES, "admin_mode": bool(st.get(db, "admin_mode"))}


def _links(db: Session, qs: list[Question]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    if qs:
        for r in db.execute(select(QuestionStimulus).where(QuestionStimulus.question_id.in_([q.id for q in qs]))
                            .order_by(QuestionStimulus.position)).scalars():
            out.setdefault(r.question_id, []).append(r.stimulus_id)
    return out


@router.get("/admin/review")
def review_queue(request: Request, db: Session = Depends(get_db), subject: str = "", source: str = "", status: str = "",
                 state: str = APPROVAL_PENDING, conf: str = "", page: int = 1):
    stmt = select(Question)
    if state in review.APPROVAL_STATES:
        stmt = stmt.where(Question.approval_status == state)
    if subject:
        stmt = stmt.join(Subject, Question.subject_id == Subject.id).where(Subject.code == subject)
    if source.isdigit():
        stmt = stmt.where(Question.source_id == int(source))
    if conf == "low":
        stmt = stmt.where(Question.mapping_confidence < 0.7)
    rows = db.execute(stmt.order_by(Question.source_id, Question.id)).scalars().all()
    if status in ("ready", "needs_fix"):
        rows = [q for q in rows if (q.import_meta or {}).get("status", "ready") == status]
    size = int(st.get(db, "review_page_size") or 25)
    page = max(1, page)
    total = len(rows)
    qs = rows[(page - 1) * size: page * size]
    srcs = db.execute(select(Source).where(Source.id.in_(select(Question.source_id).where(Question.approval_status == APPROVAL_PENDING)))
                      .order_by(Source.title)).scalars().all()
    return render(request, "admin_review.html", queue=qs, total=total, page=page, page_size=size, f=request.query_params, sources=srcs,
                  links=_links(db, qs), flash=request.query_params.get("flash"), back=str(request.url.path) + ("?" + request.url.query if request.url.query else ""),
                  single=False, **_review_ctx(db))


@router.get("/admin/review/{qid}")
def review_one(qid: int, request: Request, db: Session = Depends(get_db)):
    q = db.get(Question, qid)
    if q is None:
        raise ValueError("Question not found.")
    return render(request, "admin_review.html", queue=[q], total=1, page=1, page_size=1, f=request.query_params, sources=[],
                  links=_links(db, [q]), flash=request.query_params.get("flash"), back=f"/admin/review/{qid}", single=True, **_review_ctx(db))


@router.post("/admin/review/batch")
async def review_batch(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(i) for i in form.getlist("ids") if str(i).isdigit()]
    action = str(form.get("action") or "")
    if action not in ("approve", "reject", "retire"):
        raise ValueError("Choose a batch action.")
    if not ids:
        return _back(str(form.get("back") or "/admin/review"), flash="Tick at least one question.")
    res = review.batch(db, ids, action, str(form.get("reason") or ""))
    db.commit()
    msg = f"{action.capitalize()}: {len(res['done'])} done"
    if res["failed"]:
        msg += f"; {len(res['failed'])} not changed (" + "; ".join(f"#{x['id']}: {x['error']}" for x in res["failed"][:4]) + ")"
    return _back(str(form.get("back") or "/admin/review"), flash=msg)


@router.post("/admin/review/{qid}/{action}")
async def review_action(qid: int, action: str, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    q = db.get(Question, qid)
    if q is None:
        raise ValueError("Question not found.")
    back = str(form.get("back") or "/admin/review")
    flash = None
    try:
        if action == "approve":
            review.approve(db, q, note=str(form.get("note") or "") or None)
            flash = f"Approved Q{q.question_number or q.id}."
        elif action == "reject":
            review.reject(db, q, str(form.get("reason") or ""))
            flash = "Rejected."
        elif action in ("adapt", "adaptable"):
            review.mark_adaptable(db, q, str(form.get("reason") or ""))
            db.commit()
            return RedirectResponse(f"/admin/review/{qid}/adapt", status_code=303)
        elif action == "edit":
            issues = review.save_edits(db, q, _edit_data(form))
            n = len(review.blocking(issues))
            flash = "Saved." + (f" {n} issue{'s' if n != 1 else ''} still block approval." if n else " Ready to approve.")
        elif action == "keep_parts":
            review.keep_parts(db, q, [int(i) for i in form.getlist("keep") if str(i).isdigit()], str(form.get("reason") or ""))
            flash = "Parts kept."
        elif action == "stimulus":
            if (form.get("body") or "").strip():
                review.create_stimulus(db, q, title=str(form.get("title") or ""), body=str(form.get("body") or ""), form=str(form.get("form") or "") or None,
                                       attribution=str(form.get("attribution") or ""), provenance=str(form.get("provenance") or ""),
                                       author=str(form.get("author") or "") or None)
            else:
                review.link_stimuli(db, q, [int(i) for i in form.getlist("stimulus_ids") if str(i).isdigit()])
                review.refresh_validation(db, q)
            flash = "Texts updated."
        elif action == "retire":
            review.retire(db, q, str(form.get("reason") or ""))
            flash = "Retired."
        elif action == "restore":
            review.restore(db, q)
            flash = "Back in the review queue."
        else:
            raise ValueError(f"Unknown review action '{action}'.")
    except review.ValidationFailed as exc:
        db.commit()  # keep the refreshed validation list
        return _back(back, qid, "Not approved: " + "; ".join(i.message for i in exc.issues[:4]))
    except ValueError as exc:
        db.rollback()
        return _back(back, qid, str(exc))
    db.commit()
    return _back(back, qid, flash)


def _edit_data(form) -> dict:
    data: dict = {}
    for k in ("question_text", "marks", "question_type", "answer_letter", "answer_type", "answer_value", "relevance", "reason", "category",
              "legal_fact_currency", "student_rationale", "directive_verb", "difficulty", "primary_plan_item_id"):
        if k in form:
            data[k] = str(form.get(k))
    if "option_0" in form:
        data["options"] = [str(form.get(f"option_{i}") or "") for i in range(4)]
    if "plan_item_ids" in form:
        data["plan_item_ids"] = [i for i in form.getlist("plan_item_ids") if str(i).isdigit()]
    if form.get("outcomes_present"):
        data["outcome_codes"] = [str(c) for c in form.getlist("outcome_codes")]
    if form.get("segment_ack"):
        data["segment_ack"] = True
    parts = []
    for key in form.keys():
        if key.startswith("part_marks_"):
            pid = key.removeprefix("part_marks_")
            parts.append({"id": pid, "marks": str(form.get(key) or ""), "text": form.get(f"part_text_{pid}")})
    if parts:
        data["parts"] = parts
    if data.get("primary_plan_item_id") in ("", "0"):
        data.pop("primary_plan_item_id")
    return data


@router.post("/admin/mode")
def admin_mode_toggle(on: str = Form(""), back: str = Form("/admin/review"), db: Session = Depends(get_db)):
    """Administrator mode shows answer keys, guidelines and solutions before an attempt."""
    st.set_(db, "admin_mode", bool(on))
    db.commit()
    return _back(back, flash="Administrator mode is " + ("on: answers and guidelines are visible." if on else "off: answers stay hidden until you attempt a question."))


# --------------------------------------------------------------- adaptation editor ---
@router.get("/admin/review/{qid}/adapt")
def adapt_form(qid: int, request: Request, db: Session = Depends(get_db), draft: str = ""):
    q = db.get(Question, qid)
    if q is None:
        raise ValueError("Question not found.")
    ctx = _review_ctx(db)
    return render(request, "admin_adapt.html", q=q, draft=draft or q.question_text, label=review.label_for(q), links=_links(db, [q]).get(q.id, []),
                  required=(q.import_meta or {}).get("required_plan_item_ids") or ([q.plan_item_id] if q.plan_item_id else []),
                  flash=request.query_params.get("flash"), code=db.get(Subject, q.subject_id).code, **ctx)


@router.post("/admin/review/{qid}/adapt/draft")
def adapt_draft(qid: int, request: Request, instructions: str = Form(""), db: Session = Depends(get_db)):
    from app.ai.factory import get_provider

    q = _get_q(db, qid)
    provider = get_provider(st.all_settings(db))
    if not getattr(provider, "generative", False):
        return RedirectResponse(f"/admin/review/{qid}/adapt?flash=" + quote("AI is not configured: write the adapted wording yourself."), status_code=303)
    try:
        text = review.ai_adaptation_draft(db, q, provider, instructions)
    except Exception as exc:  # the editor stays usable when the AI fails
        return RedirectResponse(f"/admin/review/{qid}/adapt?flash=" + quote(f"The AI draft failed ({exc})."), status_code=303)
    return adapt_form(qid, request, db, draft=text)


@router.post("/admin/review/{qid}/adapt/save")
async def adapt_save(qid: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    q = _get_q(db, qid)
    opts = [str(form.get(f"option_{i}") or "").strip() for i in range(4)] if "option_0" in form else None
    answer = {"type": "mcq", "value": str(form.get("answer_letter")).upper()} if form.get("answer_letter") else None
    try:
        new = review.adapt(db, q, text=str(form.get("text") or ""), marks=int(form.get("marks") or q.marks or 1),
                           plan_item_ids=[int(i) for i in form.getlist("plan_item_ids") if str(i).isdigit()], note=str(form.get("note") or ""),
                           directive_verb=str(form.get("directive_verb") or "") or None, answer=answer,
                           model_answer=str(form.get("model_answer") or "") or None,
                           legal_fact_currency=str(form.get("legal_fact_currency") or "") or None,
                           category=str(form.get("category") or "") or None,
                           stimulus_ids=[int(i) for i in form.getlist("stimulus_ids") if str(i).isdigit()] if form.get("stimuli_present") else None,
                           options=[o for o in opts if o] if opts else None, approve_now=bool(form.get("approve_now")))
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(f"/admin/review/{qid}/adapt?flash=" + quote(str(exc)), status_code=303)
    db.commit()
    state = "approved" if new.approved else "saved; fix the listed issues, then approve"
    return RedirectResponse(f"/admin/review/{new.id}?flash=" + quote(f"Adapted copy {state}. The original stays unservable."), status_code=303)


# --------------------------------------------------------------------------- import ---
@router.get("/admin/import")
def import_form(request: Request, db: Session = Depends(get_db)):
    return render(request, "admin_import.html", report=None, error=None, form={})


@router.post("/admin/import")
async def import_upload(request: Request, db: Session = Depends(get_db), paper: UploadFile = File(...), guideline: UploadFile | None = File(None),
                        stimulus: UploadFile | None = File(None), title: str = Form(...), source_type: str = Form("hsc_exam"),
                        subject: str = Form(""), year: str = Form(""), url: str = Form(""), organisation: str = Form(""),
                        guideline_kind: str = Form(""), dry_run: str = Form(""), replace: str = Form(""), confirm_subject: str = Form("")):
    form = {"title": title, "source_type": source_type, "subject": subject, "year": year, "url": url, "organisation": organisation,
            "guideline_kind": guideline_kind}
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "paper.pdf"
        p.write_bytes(await paper.read())
        extra: dict[str, Path | None] = {"guideline": None, "stimulus": None}
        for key, up in (("guideline", guideline), ("stimulus", stimulus)):
            if up is not None and up.filename:
                extra[key] = Path(tmp) / f"{key}.pdf"
                extra[key].write_bytes(await up.read())
        try:
            report = pipeline.import_paper(db, p, title=title, source_type=source_type, subject_code=subject or None,
                                           year=int(year) if year.isdigit() else None, url=url or None, guideline_pdf=extra["guideline"],
                                           stimulus_pdf=extra["stimulus"], organisation=organisation or None, guideline_kind=guideline_kind or None,
                                           dry_run=bool(dry_run), replace=bool(replace), confirm_subject=bool(confirm_subject))
        except pipeline.ImportFailed as exc:
            db.rollback()
            return render(request, "admin_import.html", report=None, error=str(exc), form=form,
                          duplicate=isinstance(exc, pipeline.DuplicateImport))
    db.commit()
    return render(request, "admin_import.html", report=report, error=None, form=form)


# -------------------------------------------------------------------------- sources ---
@router.get("/sources")
def sources(request: Request, db: Session = Depends(get_db)):
    rows = db.execute(select(Source, func.count(Question.id)).outerjoin(Question, Question.source_id == Source.id).group_by(Source.id)
                      .order_by(Source.tier, Source.title)).all()
    docs: dict[int, list[SourceDocument]] = {}
    for d in db.execute(select(SourceDocument).order_by(SourceDocument.id)).scalars():
        docs.setdefault(d.source_id, []).append(d)
    return render(request, "sources.html", rows=rows, docs=docs, source=None)


@router.get("/sources/{sid}")
def source_detail(sid: int, request: Request, db: Session = Depends(get_db)):
    s = db.get(Source, sid)
    if s is None:
        raise ValueError("Source not found.")
    docs = db.execute(select(SourceDocument).where(SourceDocument.source_id == sid).order_by(SourceDocument.id)).scalars().all()
    qs = db.execute(select(Question).where(Question.source_id == sid).order_by(Question.id)).scalars().all()
    return render(request, "sources.html", rows=[], docs={sid: docs}, source=s, questions=qs, flash=request.query_params.get("flash"))


@router.get("/sources/{sid}/pdf")
def source_pdf(sid: int, kind: str = "paper", db: Session = Depends(get_db)):
    s = db.get(Source, sid)
    doc = db.execute(select(SourceDocument).where(SourceDocument.source_id == sid, SourceDocument.kind == kind)
                     .order_by(SourceDocument.id.desc())).scalars().first()
    path = Path(doc.local_file) if doc else (Path(s.local_file) if s and s.local_file and kind == "paper" else None)
    if path is None or not path.exists():
        raise ValueError("The PDF for this source is not stored.")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.post("/sources/{sid}/remove-unused")
def source_remove_unused(sid: int, db: Session = Depends(get_db)):
    n = pipeline.remove_unused_questions(db, sid)
    review.record(db, None, "delete_source", source_id=sid, note=f"Removed {n} unattempted, unapproved question(s).")
    db.commit()
    return RedirectResponse(f"/sources/{sid}?flash=" + quote(f"Removed {n} unattempted, unapproved question(s)."), status_code=303)
