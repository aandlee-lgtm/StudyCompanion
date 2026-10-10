from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LearningPlanItem, Mastery, PrescribedText, SyllabusOutcome, SyllabusTopic
from app.routes.common import render
from app.services import plan
from app.services import settings as st

router = APIRouter()


@router.get("/curriculum")
def curriculum(request: Request, subject: str = "MATHS", db: Session = Depends(get_db)):
    subject = subject if subject in ("MATHS", "ENGLISH", "LEGAL") else "MATHS"
    subj = plan.subject(db, subject)
    topics = db.execute(select(SyllabusTopic).where(SyllabusTopic.subject_id == subj.id).order_by(SyllabusTopic.position)).scalars().all()
    return render(
        request, "curriculum.html", subject=subject, items=plan.items(db, subject), topics=topics,
        topic_names={t.id: t.name for t in topics}, texts=db.execute(select(PrescribedText).where(PrescribedText.subject_id == subj.id)).scalars().all(),
        outcomes=db.execute(select(SyllabusOutcome).where(SyllabusOutcome.subject_id == subj.id).order_by(SyllabusOutcome.topic_id)).scalars().all(),
        mastery={m.plan_item_id: m for m in db.execute(select(Mastery)).scalars()}, enrichment=st.get(db, "enrichment_enabled"),
    )


def _back(item: LearningPlanItem) -> RedirectResponse:
    return RedirectResponse(f"/curriculum?subject={item.subject.code}", status_code=303)


@router.post("/curriculum/item/{iid}/status")
def set_status(iid: int, status: str = Form(...), db: Session = Depends(get_db)):
    item = plan.set_status(db, iid, status)
    db.commit()
    return _back(item)


@router.post("/curriculum/item/{iid}/start-here")
def start_here(iid: int, db: Session = Depends(get_db)):
    plan.start_from(db, iid)
    db.commit()
    return _back(db.get(LearningPlanItem, iid))


@router.post("/curriculum/item/{iid}/option")
def option(iid: int, active: int = Form(...), db: Session = Depends(get_db)):
    plan.set_option_active(db, iid, bool(active))
    db.commit()
    return _back(db.get(LearningPlanItem, iid))


@router.post("/curriculum/item/{iid}/position")
def position(iid: int, position: int = Form(...), db: Session = Depends(get_db)):
    item = db.get(LearningPlanItem, iid)
    ids = [i.id for i in plan.items(db, item.subject.code) if i.id != iid]
    ids.insert(max(0, min(len(ids), position - 1)), iid)
    plan.reorder(db, item.subject.code, ids)
    db.commit()
    return _back(item)


@router.post("/curriculum/{subject}/reorder")
def reorder(subject: str, ids: str = Form(...), db: Session = Depends(get_db)):
    plan.reorder(db, subject, [int(x) for x in ids.split(",") if x.strip().isdigit()])
    db.commit()
    return JSONResponse({"ok": True})


@router.post("/curriculum/{subject}/advance")
def advance(subject: str, db: Session = Depends(get_db)):
    plan.advance(db, subject)
    db.commit()
    return RedirectResponse(f"/curriculum?subject={subject}", status_code=303)


@router.post("/curriculum/{subject}/add")
def add(subject: str, code: str = Form(""), title: str = Form(...), topic_id: int = Form(0), enrichment: int = Form(0), db: Session = Depends(get_db)):
    subj = plan.subject(db, subject)
    pos = max([i.position for i in plan.items(db, subject)] or [0]) + 1
    db.add(LearningPlanItem(subject_id=subj.id, code=code.strip() or f"ITEM-{pos}", title=title.strip(), topic_id=topic_id or None,
                            position=pos, status="LOCKED", enrichment=bool(enrichment), source="custom"))
    db.commit()
    return RedirectResponse(f"/curriculum?subject={subject}", status_code=303)


@router.post("/curriculum/{subject}/import")
def import_sequence(subject: str, text: str = Form(...), db: Session = Depends(get_db)):
    n = plan.import_sequence(db, subject, text)
    if n == 0:
        raise ValueError("No subtopic lines were recognised. Use lines like '1A Sequences and how to specify them'.")
    db.commit()
    return RedirectResponse(f"/curriculum?subject={subject}", status_code=303)


@router.post("/curriculum/text/{tid}")
def save_text(tid: int, details: str = Form(None), verified: int = Form(0), db: Session = Depends(get_db)):
    t = db.get(PrescribedText, tid)
    if details is not None:
        t.details = details.strip()
    t.verified = bool(verified)
    if t.verified:
        t.verification_note = "Confirmed by the student against the NESA prescriptions."
    db.commit()
    return RedirectResponse("/curriculum?subject=ENGLISH", status_code=303)


@router.post("/curriculum/{subject}/outcome")
def add_outcome(subject: str, topic_id: int = Form(...), code: str = Form(...), description: str = Form(...), db: Session = Depends(get_db)):
    subj = plan.subject(db, subject)
    o = SyllabusOutcome(subject_id=subj.id, topic_id=topic_id, code=code.strip(), description=description.strip(), official=True)
    db.add(o)
    db.flush()
    # replace the placeholder outcome on questions mapped to this focus area
    from app.models import Question

    placeholder = db.execute(select(SyllabusOutcome).where(SyllabusOutcome.topic_id == topic_id, SyllabusOutcome.official.is_(False))).scalars().first()
    if placeholder:
        for q in db.execute(select(Question).where(Question.syllabus_outcome_id == placeholder.id)).scalars():
            q.syllabus_outcome_id = o.id
    db.commit()
    return RedirectResponse(f"/curriculum?subject={subject}", status_code=303)
