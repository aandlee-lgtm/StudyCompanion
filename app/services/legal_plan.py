"""Legal Studies learning plan: syllabus sub-areas under each core topic, option slots and the
sub-area classifier (audit legal-09/11).

Sub-areas are ordinary ``LearningPlanItem`` rows whose ``topic_id`` is the core topic (Crime or
Human rights) and whose code starts with the core topic's code (``LS-CRIME-YOUNG``). Each has its
own status, so untaught content stays LOCKED. The core topic's own plan item becomes a group
header: its status mirrors its sub-areas and no question is attached to it once sub-areas exist.

Every sub-area name and the issue vocabulary are working labels to be confirmed against the
NESA Legal Studies syllabus that applies to the 2027 HSC."""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LearningPlanItem, LegalEvidence, LegalEvidenceTopic, Question, Subject, SyllabusTopic
from app.models.common import LEARNED, LEARNING, LOCKED, REVISION, utcnow

CORE_TOPICS = ("LS-CRIME", "LS-HR")
CONFIRM_NOTE = "Confirm against the NESA syllabus applicable to the 2027 HSC."

SUB_AREAS: dict[str, dict] = {
    "LS-CRIME-NATURE": {"core": "LS-CRIME", "title": "The nature of crime", "issues": [
        "elements of a crime", "strict liability", "categories of crime", "summary and indictable offences", "parties to a crime",
        "factors affecting criminal behaviour", "crime prevention"]},
    "LS-CRIME-INVESTIGATION": {"core": "LS-CRIME", "title": "The criminal investigation process", "issues": [
        "police powers", "reporting crime", "investigating crime", "arrest and charge", "bail and remand", "detention and interrogation",
        "rights of suspects"]},
    "LS-CRIME-TRIAL": {"core": "LS-CRIME", "title": "The criminal trial process", "issues": [
        "courts", "the adversary system", "legal personnel", "pleas and charge negotiation", "legal representation", "burden and standard of proof",
        "use of evidence", "defences", "the jury"]},
    "LS-CRIME-SENTENCING": {"core": "LS-CRIME", "title": "Sentencing and punishment", "issues": [
        "purposes of punishment", "factors affecting sentencing", "role of the victim", "appeals", "types of penalties",
        "alternative methods of sentencing", "post-sentencing considerations"]},
    "LS-CRIME-YOUNG": {"core": "LS-CRIME", "title": "Young offenders", "issues": [
        "age of criminal responsibility", "doli incapax", "rights of children", "the Children's Court", "diversion", "penalties for young offenders"]},
    "LS-CRIME-INTERNATIONAL": {"core": "LS-CRIME", "title": "International crime", "issues": [
        "categories of international crime", "dealing with international crime", "international courts", "extradition"]},
    "LS-HR-NATURE": {"core": "LS-HR", "title": "The nature and development of human rights", "issues": [
        "defining human rights", "developing recognition of human rights", "the International Bill of Rights", "self-determination",
        "collective rights"]},
    "LS-HR-ENFORCE": {"core": "LS-HR", "title": "Promoting and enforcing human rights", "issues": [
        "the United Nations", "courts and tribunals", "intergovernmental organisations", "non-government organisations", "the media",
        "the Australian Constitution", "statute and common law", "the bill of rights debate"]},
    "LS-HR-ISSUE": {"core": "LS-HR", "title": "A contemporary human rights issue (you choose the issue)", "issues": [
        "the chosen issue", "legal responses", "non-legal responses", "effectiveness"]},
}

# Word-boundary keyword lists used to place a question in a sub-area (offline, reviewable).
KEYWORDS: dict[str, list[str]] = {
    "LS-CRIME-YOUNG": ["young offender", "young offenders", "young person", "young people", "juvenile", "child", "children", "doli incapax",
                       "age of criminal responsibility", "youth", "children's court", "young offenders act", "diversion", "diversionary",
                       "youth justice conference", "aged 1[0-7]"],
    "LS-CRIME-SENTENCING": ["sentenc\\w*", "punishment", "penalt\\w+", "deterrence", "rehabilitation", "retribution", "incapacitation",
                            "aggravating", "mitigating", "parole", "imprisonment", "prison", "victim impact", "restorative justice",
                            "post-sentencing", "preventive detention", "community correction", "appeal against sentence"],
    "LS-CRIME-TRIAL": ["trial", "jury", "juries", "juror\\w*", "plea", "charge negotiation", "adversar\\w+", "burden of proof",
                       "standard of proof", "beyond reasonable doubt", "defences?", "self-defence", "legal aid", "legal representation",
                       "local court", "district court", "supreme court", "court hierarchy", "witness\\w*", "verdict", "acquit\\w*"],
    "LS-CRIME-INVESTIGATION": ["police", "arrest\\w*", "bail", "remand", "search", "warrants?", "interrogation", "detention",
                               "investigat\\w+", "suspects?", "right to silence", "reporting crime", "lepra", "surveillance", "summons"],
    "LS-CRIME-INTERNATIONAL": ["international crime", "transnational", "genocide", "war crimes?", "crimes against humanity",
                               "international criminal court", "rome statute", "extradit\\w+", "people smuggling", "trafficking", "piracy"],
    "LS-CRIME-NATURE": ["mens rea", "actus reus", "strict liability", "causation", "summary offences?", "indictable", "categories of crime",
                        "offences?", "parties to a crime", "accessor\\w+", "accomplice", "criminal behaviour", "crime prevention",
                        "elements of a crime", "murder", "manslaughter", "mental element"],
    "LS-HR-NATURE": ["universal declaration", "udhr", "international bill of rights", "iccpr", "icescr", "self-determination",
                     "collective rights", "inherent", "inalienable", "indivisible", "universal", "development of human rights",
                     "abolition of slavery", "magna carta", "universal suffrage", "definition of human rights"],
    "LS-HR-ENFORCE": ["united nations", "human rights council", "treaty bod\\w+", "ngos?", "non-government", "media", "courts?",
                      "tribunals?", "constitution\\w*", "bill of rights", "charter", "statute", "common law", "australian human rights commission",
                      "enforc\\w+", "promot\\w+", "sovereignty", "intergovernmental", "racial discrimination act"],
    "LS-HR-ISSUE": ["contemporary human rights issue", "one contemporary", "contemporary issue"],
}

OPTION_PREFIX = "LS-OPT-"


def legal_subject(db: Session) -> Subject:
    return db.execute(select(Subject).where(Subject.code == "LEGAL")).scalar_one()


def is_core_parent(item: LearningPlanItem) -> bool:
    return item.code in CORE_TOPICS


def is_sub_area(item: LearningPlanItem) -> bool:
    return any(item.code.startswith(c + "-") for c in CORE_TOPICS)


def is_option(item: LearningPlanItem) -> bool:
    return bool(item.topic and item.topic.is_option) or item.code.startswith(OPTION_PREFIX)


def legal_items(db: Session) -> list[LearningPlanItem]:
    s = legal_subject(db)
    return list(db.execute(select(LearningPlanItem).where(LearningPlanItem.subject_id == s.id)
                           .order_by(LearningPlanItem.position, LearningPlanItem.id)).scalars())


def sub_areas_of(db: Session, parent: LearningPlanItem) -> list[LearningPlanItem]:
    return [i for i in legal_items(db) if i.code.startswith(parent.code + "-")]


def sub_area_item(db: Session, code: str) -> LearningPlanItem | None:
    return db.execute(select(LearningPlanItem).where(LearningPlanItem.code == code)).scalar_one_or_none()


def _hits(text: str, words: list[str]) -> int:
    t = (text or "").lower()
    return sum(1 for w in words if re.search(rf"(?<![a-z]){w}(?![a-z])", t))


def classify(text: str, core: str) -> tuple[str, int]:
    """Best sub-area code for ``text`` within core topic ``core`` and the number of keyword hits
    (0 = no evidence: the first sub-area is returned)."""
    best, best_hits = None, 0
    for code, info in SUB_AREAS.items():
        if info["core"] != core:
            continue
        h = _hits(text, KEYWORDS.get(code, []))
        if h > best_hits:
            best, best_hits = code, h
    if best is None:
        best = next(c for c, i in SUB_AREAS.items() if i["core"] == core)
    return best, best_hits


def derived_parent_status(children: list[LearningPlanItem]) -> str:
    sts = [c.status for c in children if c.active]
    if not sts or all(s == LOCKED for s in sts):
        return LOCKED
    if all(s in (LEARNED, REVISION) for s in sts):
        return REVISION if REVISION in sts else LEARNED
    return LEARNING


def sync_parent(db: Session, parent: LearningPlanItem) -> None:
    """Keep the core topic's header status consistent with its sub-areas."""
    kids = sub_areas_of(db, parent)
    if not kids:
        return
    new = derived_parent_status(kids)
    if parent.status != new:
        parent.status, parent.status_changed_at = new, utcnow()
    db.flush()


def parent_of(db: Session, item: LearningPlanItem) -> LearningPlanItem | None:
    for c in CORE_TOPICS:
        if item.code.startswith(c + "-"):
            return db.execute(select(LearningPlanItem).where(LearningPlanItem.code == c)).scalar_one_or_none()
    return None


def set_all_sub_areas(db: Session, parent: LearningPlanItem, status: str) -> None:
    for k in sub_areas_of(db, parent):
        if k.active and k.status != status:
            k.status, k.status_changed_at = status, utcnow()
    sync_parent(db, parent)


def start_here(db: Session, item: LearningPlanItem) -> None:
    """Within one core topic only: earlier sub-areas LEARNED (REVISION kept), this one LEARNING,
    later ones LOCKED. The other core topic is untouched."""
    parent = parent_of(db, item)
    if parent is None:
        return
    kids = sub_areas_of(db, parent)
    for k in kids:
        if not k.active:
            continue
        if (k.position, k.id) < (item.position, item.id):
            new = k.status if k.status == REVISION else LEARNED
        elif k.id == item.id:
            new = LEARNING
        else:
            new = LOCKED
        if k.status != new:
            k.status, k.status_changed_at = new, utcnow()
    sync_parent(db, parent)


# ------------------------------------------------------------------------- options ---


def option_items(db: Session) -> list[LearningPlanItem]:
    return [i for i in legal_items(db) if is_option(i) and "retired" not in (i.notes or "").lower()]


def active_options(db: Session) -> list[LearningPlanItem]:
    return [i for i in option_items(db) if i.active]


def option_health(db: Session, item: LearningPlanItem) -> dict:
    """Content available for an option: approved questions and verified evidence items."""
    nq = db.execute(select(func.count(Question.id)).where(Question.plan_item_id == item.id, Question.approved.is_(True))).scalar_one()
    nev = 0
    if item.topic_id:
        nev = db.execute(select(func.count(LegalEvidence.id)).join(LegalEvidenceTopic)
                         .where(LegalEvidenceTopic.topic_id == item.topic_id, LegalEvidence.last_verified_date.is_not(None))).scalar_one()
    warn = []
    if nq < 10:
        warn.append(f"only {nq} question{'s' if nq != 1 else ''} (import past papers or add questions)")
    if nev < 5:
        warn.append(f"only {nev} verified evidence item{'s' if nev != 1 else ''} (add and verify items in the evidence bank)")
    return {"questions": nq, "verified_evidence": nev, "warnings": warn}


def set_option(db: Session, item: LearningPlanItem, active: bool, max_options: int = 2) -> None:
    if active and not item.active and len(active_options(db)) >= max_options:
        raise ValueError(f"You can study at most {max_options} Legal Studies options. Deactivate one first.")
    item.active = active
    if active and item.status == LOCKED:
        item.status = LEARNING
    if not active:
        item.status = LOCKED
    item.status_changed_at = utcnow()
    db.flush()


def set_option_slots(db: Session, chosen_ids: list[int], max_options: int = 2) -> list[LearningPlanItem]:
    """Make exactly the chosen options active (at most ``max_options``); returns the newly activated."""
    ids = []
    for i in chosen_ids:
        if i and i not in ids:
            ids.append(i)
    if len(ids) > max_options:
        raise ValueError(f"You can choose at most {max_options} Legal Studies options.")
    newly = []
    opts = option_items(db)
    for o in opts:  # deactivate first so the limit is checked against the final state
        if o.active and o.id not in ids:
            set_option(db, o, False, max_options)
    for o in opts:
        if o.id in ids and not o.active:
            set_option(db, o, True, max_options)
            newly.append(o)
    return newly


def create_option(db: Session, name: str, keywords: str = "", notes: str = "") -> LearningPlanItem:
    s = legal_subject(db)
    slug = re.sub(r"[^A-Z0-9]+", "", name.upper())[:20] or "OPTION"
    code, n = OPTION_PREFIX + slug, 2
    while db.execute(select(SyllabusTopic).where(SyllabusTopic.code == code)).scalar_one_or_none() is not None:
        code, n = f"{OPTION_PREFIX}{slug}{n}", n + 1
    ref = db.execute(select(SyllabusTopic).where(SyllabusTopic.subject_id == s.id)).scalars().first()
    pos = max([t.position for t in db.execute(select(SyllabusTopic).where(SyllabusTopic.subject_id == s.id)).scalars()] or [0]) + 1
    t = SyllabusTopic(subject_id=s.id, syllabus_version_id=ref.syllabus_version_id if ref else None, code=code, name=name.strip(), kind="option",
                      is_option=True, keywords=keywords.strip() or None, notes=(notes.strip() or "Option topic added by you.") + " " + CONFIRM_NOTE,
                      position=pos)
    db.add(t)
    db.flush()
    ipos = max([i.position for i in legal_items(db)] or [0]) + 1
    item = LearningPlanItem(subject_id=s.id, topic_id=t.id, code=code, title=f"Option — {name.strip()}", position=ipos, status=LOCKED,
                            active=False, source="custom", notes=CONFIRM_NOTE)
    db.add(item)
    db.flush()
    return item


def add_sub_area(db: Session, parent: LearningPlanItem, title: str, code: str = "") -> LearningPlanItem:
    code = (code or "").strip().upper()
    if not code.startswith(parent.code + "-"):
        code = parent.code + "-" + (re.sub(r"[^A-Z0-9]+", "", (code or title).upper())[:16] or "AREA")
    if db.execute(select(LearningPlanItem).where(LearningPlanItem.code == code)).scalar_one_or_none() is not None:
        raise ValueError(f"A plan item with code {code} already exists.")
    kids = sub_areas_of(db, parent)
    pos = (max([k.position for k in kids]) if kids else parent.position)
    for it in legal_items(db):  # make room directly after the last sub-area
        if it.position > pos:
            it.position += 1
    item = LearningPlanItem(subject_id=parent.subject_id, topic_id=parent.topic_id, code=code, title=title.strip(), position=pos + 1,
                            status=LOCKED, source="custom", notes="Sub-area added by you. " + CONFIRM_NOTE)
    db.add(item)
    db.flush()
    return item


def retire(db: Session, item: LearningPlanItem) -> None:
    item.active = False
    item.status = LOCKED
    item.status_changed_at = utcnow()
    item.notes = ((item.notes or "") + " Retired by you.").strip()
    db.flush()
    parent = parent_of(db, item)
    if parent is not None:
        sync_parent(db, parent)


# ------------------------------------------------------------------------- grouping ---


def grouped(db: Session) -> dict:
    """Plan items for the Learning plan page: core topics with their sub-areas, then options."""
    items = legal_items(db)
    cores = []
    for code in CORE_TOPICS:
        parent = next((i for i in items if i.code == code), None)
        if parent is None:
            continue
        kids = [i for i in items if i.code.startswith(code + "-")]
        cores.append({"parent": parent, "children": kids})
    used = {c["parent"].id for c in cores} | {k.id for c in cores for k in c["children"]}
    options = [i for i in items if i.id not in used and is_option(i)]
    other = [i for i in items if i.id not in used and not is_option(i)]
    return {"cores": cores, "options": options, "other": other}
