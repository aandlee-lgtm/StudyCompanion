from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from urllib.parse import quote

from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LearningPlanItem, Mastery, PrescribedText, Question, SyllabusOutcome, SyllabusTopic
from app.routes.common import render
from app.services import legal_plan as lp
from app.services import plan
from app.services import settings as st

router = APIRouter()


@router.get("/curriculum")
def curriculum(request: Request, subject: str = "MATHS", db: Session = Depends(get_db)):
    subject = subject if subject in ("MATHS", "ENGLISH", "LEGAL") else "MATHS"
    subj = plan.subject(db, subject)
    topics = db.execute(select(SyllabusTopic).where(SyllabusTopic.subject_id == subj.id).order_by(SyllabusTopic.position)).scalars().all()
    legal = None
    if subject == "LEGAL":  # v2-legal-logic: sub-areas, option slots (legal-09/11)
        counts = dict(db.execute(select(Question.plan_item_id, func.count(Question.id)).where(Question.subject_id == subj.id, Question.approved.is_(True))
                                 .group_by(Question.plan_item_id)).all())
        groups = lp.grouped(db)
        options = lp.option_items(db)
        legal = {"groups": groups, "counts": counts, "options": options, "active": [o for o in options if o.active],
                 "health": {o.id: lp.option_health(db, o) for o in options if o.active}, "max_options": int(st.get(db, "legal_max_options") or 2),
                 "confirmed": bool(st.get(db, "legal_syllabus_confirmed")), "msg": request.query_params.get("msg"),
                 "retired": [i for i in lp.legal_items(db) if "retired by you" in (i.notes or "").lower()],
                 "labels": lp.STATUS_LABELS, "statuses": lp.STATUS_ORDER, "picker": lp.picker(db)}
    return render(
        request, "curriculum.html", subject=subject, items=plan.items(db, subject), topics=topics,
        topic_names={t.id: t.name for t in topics}, texts=db.execute(select(PrescribedText).where(PrescribedText.subject_id == subj.id)).scalars().all(),
        outcomes=db.execute(select(SyllabusOutcome).where(SyllabusOutcome.subject_id == subj.id).order_by(SyllabusOutcome.topic_id)).scalars().all(),
        mastery={m.plan_item_id: m for m in db.execute(select(Mastery)).scalars()}, enrichment=st.get(db, "enrichment_enabled"), legal=legal,
    )


def _back(item: LearningPlanItem, msg: str | None = None) -> RedirectResponse:
    url = f"/curriculum?subject={item.subject.code}"
    if msg:
        url += "&msg=" + quote(msg)
    if item.subject.code == "LEGAL":
        url += f"#item{item.id}"
    return RedirectResponse(url, status_code=303)


def _legal_back(msg: str | None = None, anchor: str = "") -> RedirectResponse:
    return RedirectResponse("/curriculum?subject=LEGAL" + ("&msg=" + quote(msg) if msg else "") + (f"#{anchor}" if anchor else ""), status_code=303)


def _item(db: Session, iid: int) -> LearningPlanItem:
    item = db.get(LearningPlanItem, iid)
    if item is None:
        raise ValueError("That learning-plan item no longer exists.")
    return item


@router.post("/curriculum/item/{iid}/status")
def set_status(iid: int, status: str = Form(...), db: Session = Depends(get_db)):
    item = _item(db, iid)
    if item.subject.code == "LEGAL":
        # v2-legal-logic: each sub-area / option is set on its own, in any order (no sequence)
        if lp.is_core_parent(item) and lp.sub_areas_of(db, item):
            if status not in lp.STATUS_ORDER:
                raise ValueError(f"unknown status {status}")
            lp.set_all_sub_areas(db, item, status)  # a core topic's status is its sub-areas' status
        else:
            try:
                lp.set_item_status(db, item, status, int(st.get(db, "legal_max_options") or 2))
            except ValueError as exc:
                return _back(item, str(exc))
        st.set_(db, "legal_topics_chosen", True)  # changing a topic's status answers the first-use picker
    else:
        item = plan.set_status(db, iid, status)
    db.commit()
    return _back(item)


@router.post("/curriculum/item/{iid}/start-here")
def start_here(iid: int, db: Session = Depends(get_db)):
    item = _item(db, iid)
    if item.subject.code == "LEGAL":
        return _back(item, lp.NO_SEQUENCE_MSG)  # Legal topics have no fixed teaching order
    plan.start_from(db, iid)
    db.commit()
    return _back(item)


@router.post("/curriculum/item/{iid}/option")
def option(iid: int, active: int = Form(...), db: Session = Depends(get_db)):
    item = _item(db, iid)
    try:
        lp.set_option(db, item, bool(active), int(st.get(db, "legal_max_options") or 2))
    except ValueError as exc:
        return _back(item, str(exc))
    msg = None
    if active:
        warn = lp.option_health(db, item)["warnings"]
        msg = f"{item.title} is now active." + (" Content check: " + "; ".join(warn) + "." if warn else "")
    db.commit()
    return _back(item, msg)


# ---------------------------------------------------------------- Legal Studies (v2-legal-logic) ---


@router.post("/curriculum/LEGAL/options")
def legal_option_slots(option1: int = Form(0), option2: int = Form(0), db: Session = Depends(get_db)):
    """The two option slots (legal-11): exactly the chosen options become active."""
    max_opts = int(st.get(db, "legal_max_options") or 2)
    try:
        newly = lp.set_option_slots(db, [option1, option2][:max_opts], max_opts)
    except ValueError as exc:
        return _legal_back(str(exc), "options")
    notes = []
    for o in newly:
        warn = lp.option_health(db, o)["warnings"]
        notes.append(f"{o.title} is now active" + (" — content check: " + "; ".join(warn) if warn else "") + ".")
    db.commit()
    return _legal_back(" ".join(notes) or "Option choices saved.", "options")


@router.post("/curriculum/LEGAL/option/new")
def legal_new_option(name: str = Form(...), keywords: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db)):
    if not name.strip():
        raise ValueError("Give the option topic a name.")
    item = lp.create_option(db, name, keywords, notes)
    db.commit()
    return _legal_back(f"Added the option topic '{name.strip()}'. Choose it in an option slot to study it.", f"item{item.id}")


@router.post("/curriculum/LEGAL/sub-area")
def legal_new_sub_area(parent_id: int = Form(...), title: str = Form(...), code: str = Form(""), db: Session = Depends(get_db)):
    parent = _item(db, parent_id)
    if not lp.is_core_parent(parent) or not title.strip():
        raise ValueError("Choose Crime or Human rights and give the sub-area a title.")
    try:
        item = lp.add_sub_area(db, parent, title, code)
    except ValueError as exc:
        return _legal_back(str(exc))
    db.commit()
    return _legal_back(f"Added the sub-area '{item.title}' (LOCKED until you start it).", f"item{item.id}")


@router.post("/curriculum/item/{iid}/rename")
def rename(iid: int, title: str = Form(...), db: Session = Depends(get_db)):
    item = _item(db, iid)
    if not title.strip():
        raise ValueError("The title cannot be empty.")
    item.title = title.strip()[:300]
    if item.topic is not None and lp.is_option(item):
        item.topic.name = item.title.replace("Option — ", "", 1)
    db.commit()
    return _back(item)


@router.post("/curriculum/item/{iid}/retire")
def retire(iid: int, db: Session = Depends(get_db)):
    item = _item(db, iid)
    if item.subject.code != "LEGAL" or lp.is_core_parent(item):
        raise ValueError("Only Legal Studies sub-areas and option topics can be retired here.")
    lp.retire(db, item)
    db.commit()
    return _back(item, f"Retired '{item.title}'. Its questions are no longer served; nothing was deleted.")


@router.post("/curriculum/item/{iid}/restore")
def restore(iid: int, db: Session = Depends(get_db)):
    item = _item(db, iid)
    item.notes = (item.notes or "").replace(" Retired by you.", "").replace("Retired by you.", "").strip() or None
    if not lp.is_option(item):
        item.active = True
    db.commit()
    return _back(item, f"Restored '{item.title}' (LOCKED).")


SAFE_NEXT = ("/", "/legal-evidence", "/curriculum?subject=LEGAL")


@router.post("/curriculum/LEGAL/started")
def legal_started(started: list[int] = Form([]), next: str = Form("/curriculum?subject=LEGAL"), db: Session = Depends(get_db)):
    """The first-use picker 'Which Legal topics have you started?' (owner request): ticked topics
    become Learning now, the rest Not taught yet; any later change is made per topic."""
    target = next if next in SAFE_NEXT else "/curriculum?subject=LEGAL"
    try:
        res = lp.apply_started(db, started, int(st.get(db, "legal_max_options") or 2))
    except ValueError as exc:
        return RedirectResponse(target + ("&" if "?" in target else "?") + "msg=" + quote(str(exc)) + "#legal-topics", status_code=303)
    db.commit()
    n = len(started)
    msg = (f"Saved: {n} Legal topic{'s' if n != 1 else ''} started. Only these are used in your daily sessions; change any topic on the Learning plan at any time."
           if n else "Saved: no Legal topics started yet, so no Legal questions will be served until you start one on the Learning plan.")
    if res["stopped"]:
        msg += " Now Not taught yet: " + ", ".join(res["stopped"]) + "."
    return RedirectResponse(target + ("&" if "?" in target else "?") + "msg=" + quote(msg), status_code=303)


@router.post("/curriculum/LEGAL/syllabus-confirmed")
def legal_syllabus_confirmed(confirmed: int = Form(0), db: Session = Depends(get_db)):
    st.set_(db, "legal_syllabus_confirmed", bool(confirmed))
    db.commit()
    return _legal_back("Saved." if confirmed else "Marked as not yet confirmed.")


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
    if subject == "LEGAL":  # v2-legal-logic: nothing auto-advances to a "next" Legal topic
        return _legal_back(lp.NO_SEQUENCE_MSG)
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
