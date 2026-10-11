from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import LegalEvidence, LegalEvidenceTopic, Subject, SyllabusTopic
from app.routes.common import render, templates
from app.services import clock
from app.services import legal_evidence as le
from app.services import legal_plan as lp
from app.services import settings as st

router = APIRouter()


def legal_topics_pending() -> bool:
    """Template global for the dashboard notice (v2-legal-logic, owner request): True until the
    student has answered 'Which Legal topics have you started?'. Never breaks a page."""
    from app.db import SessionLocal

    try:
        db = SessionLocal()
        try:
            return lp.topics_pending(db)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - a notice must never stop the dashboard rendering
        return False


def legal_evidence_due() -> int:
    """Template global for the dashboard (legal-19): evidence items whose re-check is due."""
    from app.db import SessionLocal

    try:
        db = SessionLocal()
        try:
            today, sett = clock.today(), st.all_settings(db)
            return sum(1 for e in db.execute(select(LegalEvidence).where(LegalEvidence.last_verified_date.is_not(None))).scalars()
                       if le.state_of(e, today, sett) == "recheck_due")
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        return 0


def legal_currency_line(question_id: int | None) -> str:
    """Template global for MCQ explanations / the question page (legal-03): 'Current information
    checked' from the items the question's explanation, model answer and evidence titles cite."""
    from app.db import SessionLocal
    from app.models import Question
    from app.services import citations as cit
    from app.services.assessment import legal as legal_fb

    if not question_id:
        return ""
    try:
        db = SessionLocal()
        try:
            q = db.get(Question, question_id)
            if q is None or lp.legal_subject(db).id != q.subject_id:
                return ""
            bank, today, sett = cit.Bank.from_db(db), clock.today(), st.all_settings(db)
            sol = q.solution or {}
            text = "\n".join([sol.get("explanation") or "", q.model_answer or "", *(sol.get("option_rationales") or {}).values()])
            res = cit.unique(cit.resolve(text, bank, today, sett))
            cards = [{"title": t} for t in sol.get("evidence_titles") or []]
            cur = legal_fb.currency_for(res, cards, bank, today)
            return legal_fb.currency_line(cur) if cur.get("cited") else ""
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        return ""


templates.env.globals.update(legal_topics_pending=legal_topics_pending, legal_evidence_due=legal_evidence_due,
                             legal_currency_line=legal_currency_line)
TYPES = ["legislation", "case", "law_reform", "report", "inquiry", "treaty", "institution", "media", "issue"]


def _ev(db: Session, eid: int) -> LegalEvidence:
    ev = db.get(LegalEvidence, eid)
    if ev is None:
        raise HTTPException(status_code=404, detail="That evidence item does not exist.")
    return ev


def _legal_topics(db: Session) -> list[SyllabusTopic]:
    legal = db.execute(select(Subject).where(Subject.code == "LEGAL")).scalar_one()
    return db.execute(select(SyllabusTopic).where(SyllabusTopic.subject_id == legal.id).order_by(SyllabusTopic.position)).scalars().all()


def _sub_area_choices(db: Session) -> list[tuple[str, str]]:
    return [(i.code, i.title) for i in lp.legal_items(db) if lp.is_sub_area(i) or lp.is_option(i)]


@router.get("/legal-evidence")
def bank(request: Request, topic: str = "", item_type: str = "", q: str = "", state: str = "", sub_area: str = "",
         db: Session = Depends(get_db)):
    stmt = select(LegalEvidence).order_by(LegalEvidence.item_type, LegalEvidence.title)
    if topic.isdigit():
        stmt = stmt.join(LegalEvidenceTopic).where(LegalEvidenceTopic.topic_id == int(topic))
    all_items = db.execute(select(LegalEvidence)).scalars().all()
    items = db.execute(stmt).scalars().unique().all()
    if item_type:
        items = [i for i in items if i.item_type == item_type]
    if sub_area:
        items = [i for i in items if (i.sub_area or "") == sub_area]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in " ".join([i.title, i.summary or "", i.issue or "", " ".join(i.aliases or [])]).lower()]
    today, sett = clock.today(), st.all_settings(db)
    if state in ("unverified", "recheck_due", "verified", "outdated"):
        items = [i for i in items if le.state_of(i, today, sett) == state]
    topics = _legal_topics(db)
    tnames = {t.id: t.name for t in topics}
    picker = lp.picker(db)
    return render(request, "legal.html", items=items, groups=le.grouped(db, items, today, sett), counts=le.counts(all_items, today, sett),
                  topics=topics, tnames=tnames, types=TYPES, f=request.query_params, sub_areas=_sub_area_choices(db),
                  statuses=le.STATUSES, picker=picker if picker["pending"] else None, picker_next="/legal-evidence",
                  msg=request.query_params.get("msg"))


@router.get("/legal-evidence/{eid}")
def item(eid: int, request: Request, db: Session = Depends(get_db)):
    """One item: details, the edit form (legal-18), the verification dialog and its history (legal-19)."""
    ev = _ev(db, eid)
    topics = _legal_topics(db)
    linked = {t.topic_id for t in ev.topics}
    return render(request, "legal_evidence_item.html", e=ev, topics=topics, linked=linked, types=TYPES, statuses=le.STATUSES,
                  sub_areas=_sub_area_choices(db), checklist=le.CHECKLIST, history=le.history(db, ev),
                  state=le.state_of(ev, clock.today(), st.all_settings(db)), msg=request.query_params.get("msg"))


@router.post("/legal-evidence/add")
def add(db: Session = Depends(get_db), title: str = Form(...), item_type: str = Form("media"), date: str = Form(""), jurisdiction: str = Form("NSW"),
        issue: str = Form(""), summary: str = Form(...), legal_significance: str = Form(""), syllabus_link: str = Form(""), source: str = Form(""),
        source_url: str = Form(""), topic_ids: list[int] = Form([]), verified: int = Form(0), aliases: str = Form(""), status: str = Form("unknown"),
        sub_area: str = Form(""), version_as_at: str = Form("")):
    if item_type not in TYPES:
        raise ValueError(f"Unknown item type '{item_type}'.")
    ev = le.add_manual(db, {"title": title.strip(), "item_type": item_type, "date": date or None, "jurisdiction": jurisdiction, "issue": issue or None,
                            "summary": summary, "legal_significance": legal_significance, "syllabus_link": syllabus_link or None, "source": source or None,
                            "source_url": source_url or None, "verified": bool(verified), "aliases": aliases, "status": status if status in le.STATUSES else "unknown",
                            "sub_area": sub_area or None, "version_as_at": version_as_at or None}, topic_ids)
    db.commit()
    return RedirectResponse(f"/legal-evidence#ev{ev.id}", status_code=303)


@router.post("/legal-evidence/fetch")
def fetch(db: Session = Depends(get_db), url: str = Form(...), topic_ids: list[int] = Form([])):
    le.add_from_url(db, url, topic_ids, st.all_settings(db))
    db.commit()
    return RedirectResponse("/legal-evidence", status_code=303)


@router.post("/legal-evidence/{eid}/edit")
def edit(eid: int, db: Session = Depends(get_db), title: str = Form(...), item_type: str = Form(...), date: str = Form(""), jurisdiction: str = Form(...),
         issue: str = Form(""), summary: str = Form(...), legal_significance: str = Form(""), syllabus_link: str = Form(""), source: str = Form(...),
         source_url: str = Form(""), source_type: str = Form("primary"), status: str = Form("unknown"), superseded_by: str = Form(""),
         sub_area: str = Form(""), version_as_at: str = Form(""), aliases: str = Form(""), issue_tags: str = Form(""), topic_ids: list[int] = Form([])):
    ev = _ev(db, eid)
    if item_type not in TYPES:
        raise ValueError(f"Unknown item type '{item_type}'.")
    try:
        reset = le.update_item(db, ev, {"title": title, "item_type": item_type, "date": date, "jurisdiction": jurisdiction, "issue": issue,
                                        "summary": summary, "legal_significance": legal_significance, "syllabus_link": syllabus_link,
                                        "source": source, "source_url": source_url, "source_type": source_type, "status": status,
                                        "superseded_by": superseded_by, "sub_area": sub_area, "version_as_at": version_as_at,
                                        "aliases": aliases, "issue_tags": issue_tags}, topic_ids)
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(f"/legal-evidence/{eid}?msg=" + quote(str(exc)), status_code=303)
    db.commit()
    msg = "Saved." + (" The edit changed checked facts, so the item needs verifying again." if reset else "")
    return RedirectResponse(f"/legal-evidence/{eid}?msg=" + quote(msg), status_code=303)


@router.post("/legal-evidence/{eid}/verify")
def verify(eid: int, db: Session = Depends(get_db), title_year: int = Form(0), jurisdiction: int = Form(0), summary: int = Form(0),
           current: int = Form(0), version_as_at: str = Form(""), note: str = Form(""), corrected_summary: str = Form(""), status: str = Form("")):
    """The verification dialog (legal-19): a checklist, the version read and an optional note."""
    ev = _ev(db, eid)
    try:
        le.record_check(db, ev, {"title_year": title_year, "jurisdiction": jurisdiction, "summary": summary, "current": current},
                        version_as_at=version_as_at, note=note, corrected_summary=corrected_summary, status=status or None)
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(f"/legal-evidence/{eid}?msg=" + quote(str(exc)) + "#verify", status_code=303)
    db.commit()
    return RedirectResponse(f"/legal-evidence/{eid}?msg=" + quote(f"Verified on {clock.today():%d %b %Y}."), status_code=303)


@router.post("/legal-evidence/{eid}/delete")
def delete(eid: int, db: Session = Depends(get_db)):
    le.delete_item(db, _ev(db, eid))
    db.commit()
    return RedirectResponse("/legal-evidence", status_code=303)
