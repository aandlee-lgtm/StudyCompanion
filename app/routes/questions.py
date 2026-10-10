from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingestion import pipeline
from app.models import Attempt, LearningPlanItem, Question, QuestionExposure, Source, Subject, SyllabusTopic
from app.models.common import ORIGIN_GENERATED, RELEVANCE
from app.routes.common import render
from app.services import question_bank as qb

router = APIRouter()


@router.get("/questions")
def library(request: Request, db: Session = Depends(get_db), subject: str = "", year: str = "", source: str = "", topic: str = "",
            marks: str = "", difficulty: str = "", relevance: str = "", approval: str = "", attempted: str = "", origin: str = "", page: int = 1):
    stmt = select(Question)
    if subject:
        stmt = stmt.join(Subject, Question.subject_id == Subject.id).where(Subject.code == subject)
    if year.isdigit():
        stmt = stmt.where(Question.source_year == int(year))
    if source.isdigit():
        stmt = stmt.where(Question.source_id == int(source))
    if topic.isdigit():
        stmt = stmt.where(Question.topic_id == int(topic))
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
    seen = select(QuestionExposure.question_id)
    if attempted == "yes":
        stmt = stmt.where(Question.id.in_(seen))
    elif attempted == "no":
        stmt = stmt.where(Question.id.not_in(seen))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    qs = db.execute(stmt.order_by(Question.subject_id, Question.id).offset((page - 1) * 50).limit(50)).scalars().all()
    exposure = {e.question_id: e for e in db.execute(select(QuestionExposure).where(QuestionExposure.question_id.in_([q.id for q in qs]))).scalars()}
    return render(request, "questions.html", qs=qs, total=total, page=page, exposure=exposure, f=request.query_params,
                  sources=db.execute(select(Source).order_by(Source.title)).scalars().all(),
                  topics=db.execute(select(SyllabusTopic).order_by(SyllabusTopic.subject_id, SyllabusTopic.position)).scalars().all(),
                  pending=db.execute(select(func.count(Question.id)).where(Question.approval_status == "pending")).scalar_one(),
                  relevances=RELEVANCE)


@router.get("/questions/{qid}")
def detail(qid: int, request: Request, db: Session = Depends(get_db)):
    q = db.get(Question, qid)
    if q is None:
        raise ValueError("Question not found.")
    attempts = db.execute(select(Attempt).where(Attempt.question_id == qid).order_by(Attempt.submitted_at)).scalars().all()
    exp = db.execute(select(QuestionExposure).where(QuestionExposure.question_id == qid)).scalar_one_or_none()
    item = db.get(LearningPlanItem, q.plan_item_id) if q.plan_item_id else None
    return render(request, "question_detail.html", q=q, attempts=attempts, exp=exp, item=item, code=db.get(Subject, q.subject_id).code)


@router.get("/admin/review")
def review_queue(request: Request, db: Session = Depends(get_db)):
    items = db.execute(select(LearningPlanItem).order_by(LearningPlanItem.subject_id, LearningPlanItem.position)).scalars().all()
    return render(request, "admin_review.html", queue=pipeline.review_queue(db), plan_items=items, relevances=RELEVANCE)


@router.post("/admin/review/{qid}/{action}")
def review_action(qid: int, action: str, db: Session = Depends(get_db), plan_item_id: int = Form(0), relevance: str = Form("DIRECT"),
                  reason: str = Form(""), answer_type: str = Form(""), answer_value: str = Form("")):
    q = db.get(Question, qid)
    if action == "approve":
        pipeline.approve(db, q)
    elif action == "adapt":
        q.relevance_status = "ADAPTABLE"
        pipeline.approve(db, q, adapted=True)
    elif action == "reject":
        pipeline.reject(db, q, reason)
    elif action == "edit":
        answer = None
        if answer_type and answer_value.strip():
            answer = {"type": answer_type, "value": answer_value.strip(), "tol": 0} if answer_type != "set" else {"type": "set", "values": [v.strip() for v in answer_value.split(",")]}
        pipeline.edit_mapping(db, q, plan_item_id=plan_item_id, relevance=relevance, reason=reason, answer=answer)
    db.commit()
    return RedirectResponse("/admin/review", status_code=303)


@router.get("/admin/import")
def import_form(request: Request, db: Session = Depends(get_db)):
    return render(request, "admin_import.html", report=None)


@router.post("/admin/import")
async def import_upload(request: Request, db: Session = Depends(get_db), paper: UploadFile = File(...), guideline: UploadFile | None = File(None),
                        title: str = Form(...), source_type: str = Form("hsc_exam"), subject: str = Form(""), year: str = Form(""),
                        url: str = Form(""), organisation: str = Form("")):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "paper.pdf"
        p.write_bytes(await paper.read())
        g = None
        if guideline is not None and guideline.filename:
            g = Path(tmp) / "guideline.pdf"
            g.write_bytes(await guideline.read())
        report = pipeline.import_paper(db, p, title=title, source_type=source_type, subject_code=subject or None,
                                       year=int(year) if year.isdigit() else None, url=url or None, guideline_pdf=g, organisation=organisation or None)
    db.commit()
    return render(request, "admin_import.html", report=report)


@router.post("/questions/new")
def new_question(db: Session = Depends(get_db), subject: str = Form(...), plan_item_id: int = Form(...), text: str = Form(...), marks: int = Form(1),
                 question_type: str = Form("short_answer"), difficulty: int = Form(2), directive_verb: str = Form(""), model_answer: str = Form(""),
                 answer_value: str = Form(""), source_title: str = Form("Manually entered questions"), origin: str = Form(ORIGIN_GENERATED)):
    item = db.get(LearningPlanItem, plan_item_id)
    subj = db.execute(select(Subject).where(Subject.code == subject)).scalar_one()
    src = qb.get_or_create_source(db, source_title, organisation="Entered by the student", subject_id=subj.id,
                                  source_type="trial" if origin == "TRIAL" else "generated", tier=3 if origin == "TRIAL" else 4)
    qb.create_question(db, subject_code=subject, source_id=src.id, question_text=text, marks=marks, question_type=question_type, difficulty=difficulty,
                       directive_verb=directive_verb or None, topic_id=item.topic_id, plan_item_id=item.id, historical_or_generated=origin,
                       model_answer=model_answer or None, answer={"type": "num" if subject == "MATHS" else "mcq", "value": answer_value, "tol": 0} if answer_value else None,
                       mapping_reason="Entered manually and mapped by the student.", mapped_by="human")
    db.commit()
    return RedirectResponse("/questions?subject=" + subject, status_code=303)


@router.get("/sources")
def sources(request: Request, db: Session = Depends(get_db)):
    rows = db.execute(select(Source, func.count(Question.id)).outerjoin(Question, Question.source_id == Source.id).group_by(Source.id).order_by(Source.tier, Source.title)).all()
    return render(request, "sources.html", rows=rows)
