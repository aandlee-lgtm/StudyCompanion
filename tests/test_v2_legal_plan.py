"""v2 legal-logic: Legal sub-areas as plan items, option slots and the v1/v2 content loaders (legal-09/11)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import LearningPlanItem, LegalEvidence, Question, QuestionMapping, Setting, Stimulus
from app.services import legal_content, legal_plan as lp
from app.services import settings as st
from app.services.seed import SEED_DIR, seed_all
from tests.conftest import plan_item

FIXTURES = Path(__file__).parent / "fixtures" / "legal"
CRIME_SUBS = ["LS-CRIME-NATURE", "LS-CRIME-INVESTIGATION", "LS-CRIME-TRIAL", "LS-CRIME-SENTENCING", "LS-CRIME-YOUNG", "LS-CRIME-INTERNATIONAL"]
HR_SUBS = ["LS-HR-NATURE", "LS-HR-ENFORCE", "LS-HR-ISSUE"]


def _codes(db):
    return [i.code for i in lp.legal_items(db)]


def _on(db, code):
    return db.execute(select(Question).where(Question.plan_item_id == plan_item(db, code).id)).scalars().all()


@pytest.fixture()
def v2_seed_dir(tmp_path, monkeypatch):
    """A seed directory with the real v1 files plus the v2-format fixtures."""
    d = tmp_path / "seed"
    d.mkdir()
    for name in ("questions_legal.json", "legal_evidence.json"):
        shutil.copy(SEED_DIR / name, d / name)
    for name in ("legal_v2.json", "legal_evidence_v2.json"):
        shutil.copy(FIXTURES / name, d / name)
    monkeypatch.setattr(legal_content, "SEED_DIR", d)
    return d


def test_sub_areas_seeded_in_order_with_statuses(db):
    codes = _codes(db)
    assert codes[:11] == ["LS-CRIME", *CRIME_SUBS, "LS-HR", *HR_SUBS]
    assert all(c.startswith("LS-OPT-") for c in codes[11:])
    status = {i.code: i.status for i in lp.legal_items(db)}
    assert status["LS-CRIME-NATURE"] == "LEARNING" and status["LS-HR-NATURE"] == "LEARNING"
    assert all(status[c] == "LOCKED" for c in CRIME_SUBS[1:] + HR_SUBS[1:])
    for c in CRIME_SUBS + HR_SUBS:
        assert "confirm against the nesa" in (plan_item(db, c).notes or "").lower()
    # the core topics are group headers: no question attached, status follows the sub-areas
    assert _on(db, "LS-CRIME") == [] and _on(db, "LS-HR") == []
    assert status["LS-CRIME"] == "LEARNING"


def test_v1_questions_placed_in_sensible_sub_areas(db):
    def where(fragment):
        q = db.execute(select(Question).where(Question.question_text.like(f"%{fragment}%"))).scalar_one()
        return db.get(LearningPlanItem, q.plan_item_id).code

    assert where("bail laws") == "LS-CRIME-INVESTIGATION"
    assert where("doli incapax") == "LS-CRIME-YOUNG"
    assert where("summary and indictable") == "LS-CRIME-NATURE"
    assert where("criminal trial process as a means") == "LS-CRIME-TRIAL"
    assert where("non-government organisations") == "LS-HR-ENFORCE"
    assert where("ONE contemporary human rights issue") == "LS-HR-ISSUE"
    assert where("Universal Declaration") == "LS-HR-NATURE"


def test_v2_files_loaded_with_their_exact_shape(db, v2_seed_dir):
    legal_content.seed_evidence(db)
    legal_content.upgrade(db)
    db.flush()
    qs = {q.question_text: q for q in db.execute(select(Question).where(Question.question_text.like("FIXTURE:%"))).scalars()}
    assert len(qs) == 4
    mcq = qs["FIXTURE: Which statement best describes a strict liability offence?"]
    assert db.get(LearningPlanItem, mcq.plan_item_id).code == "LS-CRIME-NATURE"
    assert mcq.question_type == "mcq" and mcq.answer == {"type": "mcq", "value": "B"} and len(mcq.options) == 4
    assert set(mcq.solution["option_rationales"]) == {"A", "B", "C", "D"}
    assert mcq.solution["explanation"].startswith("Strict liability")
    assert mcq.legal_fact_currency == "current" and mcq.historical_or_generated == "GENERATED" and mcq.approved

    sa = qs["FIXTURE: Explain how bail laws balance the rights of the accused with community safety."]
    assert db.get(LearningPlanItem, sa.plan_item_id).code == "LS-CRIME-INVESTIGATION"
    assert sa.solution["required_elements"][1].startswith("The unacceptable risk test")
    assert sa.solution["evidence_titles"] == ["Bail Act 2013 (NSW)"]
    assert sa.solution["currency_note"].startswith("Before you rely on this")
    assert sa.solution["model_answer_origin"] == "seeded"
    assert sa.marking_guideline.splitlines()[0] == "4 marks: Explains the balance with reference to the bail test"
    assert sa.legal_fact_currency == "check"

    stim_q = qs["FIXTURE: With reference to the hypothetical scenario, explain the burden of proof in Sam's trial."]
    assert stim_q.question_type == "stimulus" and stim_q.stimulus_id
    stim = db.get(Stimulus, stim_q.stimulus_id)
    assert stim.title == "FIXTURE hypothetical scenario: Sam's trial" and stim.form == "hypothetical scenario"
    assert "Hypothetical" in stim.attribution and "invented" in stim.body
    assert stim_q.solution["stimulus_evidence_titles"] == ["Crimes Act 1900 (NSW)"]
    assert "3–4 marks: Explains the burden of proof" in stim_q.marking_guideline

    ext = qs["FIXTURE: Evaluate the effectiveness of legal and non-legal responses to ONE contemporary human rights issue."]
    assert ext.question_type == "extended" and ext.marks == 15
    assert db.get(LearningPlanItem, ext.plan_item_id).code == "LS-HR-ISSUE"
    assert ext.solution["criteria"][0] == {"mark": 15, "range": "13–15", "descriptor": "Sustained judgement"}
    assert ext.solution["model_note"].startswith("Adapt")

    lepra = db.execute(select(LegalEvidence).where(LegalEvidence.title.like("Law Enforcement%"))).scalar_one()
    assert lepra.aliases == ["LEPRA", "Law Enforcement (Powers and Responsibilities) Act"]
    assert lepra.status == "in_force" and lepra.sub_area == "LS-CRIME-INVESTIGATION"
    assert lepra.last_verified_date is None and lepra.reliability == "unrated"
    assert [t.topic_id for t in lepra.topics] == [plan_item(db, "LS-CRIME").topic_id]
    ak = db.execute(select(LegalEvidence).where(LegalEvidence.title.like("Al-Kateb%"))).scalar_one()
    assert ak.status == "superseded"

    # idempotent: a second run creates nothing new
    nq = db.execute(select(func.count(Question.id))).scalar_one()
    ne = db.execute(select(func.count(LegalEvidence.id))).scalar_one()
    ns = db.execute(select(func.count(Stimulus.id))).scalar_one()
    legal_content.seed_evidence(db)
    legal_content.upgrade(db)
    assert db.execute(select(func.count(Question.id))).scalar_one() == nq
    assert db.execute(select(func.count(LegalEvidence.id))).scalar_one() == ne
    assert db.execute(select(func.count(Stimulus.id))).scalar_one() == ns


def test_v1_evidence_has_structure_and_a_repealed_act(db):
    bail = db.execute(select(LegalEvidence).where(LegalEvidence.title == "Bail Act 2013 (NSW)")).scalar_one()
    assert "Bail Act" in bail.aliases and bail.status == "in_force" and bail.sub_area == "LS-CRIME-INVESTIGATION"
    old = db.execute(select(LegalEvidence).where(LegalEvidence.title == "Bail Act 1978 (NSW)")).scalar_one()
    assert old.status == "repealed" and old.superseded_by == "Bail Act 2013 (NSW)"
    assert db.execute(select(func.count(LegalEvidence.id)).where(LegalEvidence.last_verified_date.is_not(None))).scalar_one() == 0


def _make_v1_database(db, crime_status="LEARNED"):
    """Turn the seeded database back into a v1-shaped one: no sub-areas, questions on the core topics."""
    crime, hr = plan_item(db, "LS-CRIME"), plan_item(db, "LS-HR")
    for q in db.execute(select(Question).where(Question.category == "core")).scalars():
        q.plan_item_id = crime.id if q.topic_id == crime.topic_id else hr.id
    for it in lp.legal_items(db):
        if lp.is_sub_area(it):
            db.delete(it)
    crime.position, hr.position, crime.status, hr.status = 1, 2, crime_status, "LEARNING"
    for n, it in enumerate([i for i in lp.legal_items(db) if lp.is_option(i)]):
        it.position = 10 + n
    for key in ("legal_sub_areas_initialised",):
        row = db.get(Setting, key)
        if row is not None:
            db.delete(row)
    db.flush()


def test_upgrade_of_a_v1_database(db):
    _make_v1_database(db, crime_status="LEARNED")
    assert not any(lp.is_sub_area(i) for i in lp.legal_items(db))
    seed_all(db, with_templates=False)
    db.flush()
    assert _codes(db)[:11] == ["LS-CRIME", *CRIME_SUBS, "LS-HR", *HR_SUBS]
    status = {i.code: i.status for i in lp.legal_items(db)}
    # Crime was finished in v1: every new sub-area inherits LEARNED; Human rights keeps the defaults
    assert all(status[c] == "LEARNED" for c in CRIME_SUBS) and status["LS-CRIME"] == "LEARNED"
    assert status["LS-HR-NATURE"] == "LEARNING" and status["LS-HR-ENFORCE"] == "LOCKED"
    assert _on(db, "LS-CRIME") == [] and _on(db, "LS-HR") == []
    bail = db.execute(select(Question).where(Question.question_text.like("%bail laws%"))).scalar_one()
    assert db.get(LearningPlanItem, bail.plan_item_id).code == "LS-CRIME-INVESTIGATION"
    m = db.execute(select(QuestionMapping).where(QuestionMapping.question_id == bail.id, QuestionMapping.mapped_by == "v2-upgrade")).scalar_one()
    assert "Moved from 'Crime'" in m.mapping_reason
    # a second start changes nothing
    before = [(i.code, i.position, i.status) for i in lp.legal_items(db)]
    seed_all(db, with_templates=False)
    assert [(i.code, i.position, i.status) for i in lp.legal_items(db)] == before


def test_upgrade_moves_an_imported_question_by_keywords(db):
    crime = plan_item(db, "LS-CRIME")
    from app.services import question_bank as qb

    src = legal_content.legal_source(db)
    q = qb.create_question(db, subject_code="LEGAL", source_id=src.id, question_text="Assess the role of juries in achieving justice in criminal trials.",
                           marks=5, question_type="short_answer", topic_id=crime.topic_id, plan_item_id=crime.id, mapping_reason="import")
    legal_content.upgrade(db)
    assert db.get(LearningPlanItem, q.plan_item_id).code == "LS-CRIME-TRIAL"
    m = db.execute(select(QuestionMapping).where(QuestionMapping.question_id == q.id, QuestionMapping.mapped_by == "v2-upgrade")).scalar_one()
    assert m.review_status == "pending" and "check this placement" in m.mapping_reason


def test_classifier():
    assert lp.classify("Explain the role of the Children's Court for young offenders aged 15.", "LS-CRIME")[0] == "LS-CRIME-YOUNG"
    assert lp.classify("Evaluate the effectiveness of sentencing in achieving deterrence.", "LS-CRIME")[0] == "LS-CRIME-SENTENCING"
    assert lp.classify("Discuss the role of police powers of search and arrest.", "LS-CRIME")[0] == "LS-CRIME-INVESTIGATION"
    assert lp.classify("Explain the significance of the ICCPR in the development of human rights.", "LS-HR")[0] == "LS-HR-NATURE"
    assert lp.classify("Assess the role of NGOs and the media in enforcing human rights.", "LS-HR")[0] == "LS-HR-ENFORCE"
    # word boundaries: 'act' inside 'actually' is not a hit
    assert lp.classify("It actually happened.", "LS-CRIME") == ("LS-CRIME-NATURE", 0)


def test_each_sub_area_is_set_independently_in_any_order(db):
    """Owner request: the teaching order is unknown, so statuses are independent and nothing
    auto-advances; several sub-areas can be Learning now at once."""
    before = {i.code: i.status for i in lp.legal_items(db)}
    lp.set_item_status(db, plan_item(db, "LS-CRIME-SENTENCING"), "LEARNING")
    lp.set_item_status(db, plan_item(db, "LS-HR-ISSUE"), "LEARNING")
    lp.set_item_status(db, plan_item(db, "LS-CRIME-NATURE"), "LEARNED")
    lp.set_item_status(db, plan_item(db, "LS-CRIME-YOUNG"), "REVISION")
    after = {i.code: i.status for i in lp.legal_items(db)}
    changed = {c for c in after if after[c] != before[c]}
    assert changed == {"LS-CRIME-SENTENCING", "LS-HR-ISSUE", "LS-CRIME-NATURE", "LS-CRIME-YOUNG"}
    assert after["LS-CRIME-INVESTIGATION"] == "LOCKED" and after["LS-CRIME-TRIAL"] == "LOCKED"  # nothing in between is touched
    assert sum(1 for c in CRIME_SUBS + HR_SUBS if after[c] == "LEARNING") == 3  # HR nature + sentencing + HR issue
    # finishing a sub-area never unlocks a "next" one
    lp.set_item_status(db, plan_item(db, "LS-CRIME-SENTENCING"), "LEARNED")
    assert plan_item(db, "LS-CRIME-YOUNG").status == "REVISION" and plan_item(db, "LS-CRIME-INTERNATIONAL").status == "LOCKED"
    assert not hasattr(lp, "start_here")
    with pytest.raises(ValueError):
        lp.set_item_status(db, plan_item(db, "LS-CRIME-TRIAL"), "DONE")
    lp.set_all_sub_areas(db, plan_item(db, "LS-CRIME"), "REVISION")
    assert plan_item(db, "LS-CRIME").status == "REVISION"
    lp.set_all_sub_areas(db, plan_item(db, "LS-CRIME"), "LOCKED")
    assert plan_item(db, "LS-CRIME").status == "LOCKED"
    assert lp.STATUS_LABELS == {"LOCKED": "Not taught yet", "LEARNING": "Learning now", "LEARNED": "Learnt", "REVISION": "Revision"}


def test_option_status_set_directly_respects_the_slots(db):
    opts = {i.code: i for i in lp.option_items(db)}
    lp.set_item_status(db, opts["LS-OPT-FAMILY"], "LEARNING")  # choosing by status takes a slot
    lp.set_item_status(db, opts["LS-OPT-WORKPLACE"], "LEARNED")
    assert opts["LS-OPT-FAMILY"].active and opts["LS-OPT-WORKPLACE"].active and opts["LS-OPT-WORKPLACE"].status == "LEARNED"
    with pytest.raises(ValueError):
        lp.set_item_status(db, opts["LS-OPT-GEP"], "LEARNING")
    lp.set_item_status(db, opts["LS-OPT-FAMILY"], "LOCKED")  # chosen, not taught yet: keeps its slot
    assert opts["LS-OPT-FAMILY"].active and opts["LS-OPT-FAMILY"].status == "LOCKED"


def test_first_use_picker(db):
    assert lp.topics_pending(db)
    pk = lp.picker(db)
    titles = [g["title"] for g in pk["groups"]]
    assert titles[-1] == "Option topics" and len(pk["groups"]) == 3
    ticked = {it["id"] for g in pk["groups"] for it in g["items"] if it["status"] != "LOCKED"}
    assert ticked == {plan_item(db, "LS-CRIME-NATURE").id, plan_item(db, "LS-HR-NATURE").id}  # the suggested defaults
    plan_item(db, "LS-HR-ENFORCE").status = "REVISION"
    chosen = [plan_item(db, c).id for c in ("LS-CRIME-TRIAL", "LS-CRIME-YOUNG", "LS-HR-ENFORCE", "LS-OPT-FAMILY")]
    res = lp.apply_started(db, chosen)
    status = {i.code: i.status for i in lp.legal_items(db)}
    assert status["LS-CRIME-TRIAL"] == "LEARNING" and status["LS-CRIME-YOUNG"] == "LEARNING"
    assert status["LS-HR-ENFORCE"] == "REVISION"  # already further along: kept
    assert status["LS-CRIME-NATURE"] == "LOCKED" and status["LS-HR-NATURE"] == "LOCKED"  # unticked
    assert plan_item(db, "LS-OPT-FAMILY").active and status["LS-OPT-FAMILY"] == "LEARNING"
    assert status["LS-CRIME"] == "LEARNING" and status["LS-HR"] == "REVISION"
    assert "The nature of crime" in " ".join(res["stopped"]) or res["stopped"]
    assert not lp.topics_pending(db)
    opts = [o.id for o in lp.option_items(db)][:3]
    with pytest.raises(ValueError):
        lp.apply_started(db, opts)
    # ticking two new options frees the slot of an unticked chosen option
    lp.apply_started(db, [plan_item(db, "LS-OPT-GEP").id, plan_item(db, "LS-OPT-WORKPLACE").id])
    assert {o.code for o in lp.active_options(db)} == {"LS-OPT-GEP", "LS-OPT-WORKPLACE"}
    assert all(plan_item(db, c).status == "LOCKED" for c in CRIME_SUBS + HR_SUBS)


def test_selection_serves_legal_only_from_unlocked_sub_areas(db):
    """Daily selection uses plan-item status: questions on Not-taught-yet sub-areas are never served."""
    from app.selection import engine
    from app.services import clock, sessions
    from tests.conftest import answer_correctly, TUESDAY
    from datetime import timedelta

    lp.apply_started(db, [plan_item(db, "LS-CRIME-TRIAL").id, plan_item(db, "LS-HR-ENFORCE").id, plan_item(db, "LS-CRIME-YOUNG").id])
    db.commit()
    allowed = {plan_item(db, c).id for c in ("LS-CRIME-TRIAL", "LS-HR-ENFORCE", "LS-CRIME-YOUNG")}
    served = set()
    for d in range(3):
        clock.set_today(TUESDAY + timedelta(days=d))
        s = sessions.get_or_create_today(db)
        legal = [sq.question for sq in s.questions if sq.question.subject_id == lp.legal_subject(db).id]
        assert legal, "Legal questions are still served from the started sub-areas"
        served |= {q.plan_item_id for q in legal}
        answer_correctly(db, s)
    assert served and served <= allowed
    # the hard eligibility rule itself
    locked_q = _on(db, "LS-CRIME-NATURE")[0]
    open_q = _on(db, "LS-CRIME-TRIAL")[0]
    from app.selection.context import build_context

    ctx = build_context(db, clock.today())
    assert not engine.is_servable(ctx, locked_q) and engine.is_servable(ctx, open_q)


def test_option_slots_limit_two(db):
    opts = {i.code: i for i in lp.option_items(db)}
    lp.set_option_slots(db, [opts["LS-OPT-FAMILY"].id, opts["LS-OPT-WORKPLACE"].id])
    assert {i.code for i in lp.active_options(db)} == {"LS-OPT-FAMILY", "LS-OPT-WORKPLACE"}
    assert opts["LS-OPT-FAMILY"].status == "LEARNING"
    with pytest.raises(ValueError):
        lp.set_option(db, opts["LS-OPT-GEP"], True)
    with pytest.raises(ValueError):
        lp.set_option_slots(db, [opts["LS-OPT-FAMILY"].id, opts["LS-OPT-GEP"].id, opts["LS-OPT-SHELTER"].id])
    # swapping a slot deactivates the old option first, so the limit is never exceeded
    lp.set_option_slots(db, [opts["LS-OPT-FAMILY"].id, opts["LS-OPT-GEP"].id])
    assert {i.code for i in lp.active_options(db)} == {"LS-OPT-FAMILY", "LS-OPT-GEP"}
    assert opts["LS-OPT-WORKPLACE"].status == "LOCKED"
    health = lp.option_health(db, opts["LS-OPT-GEP"])
    assert health["questions"] == 0 and len(health["warnings"]) == 2


def test_create_option_and_sub_area_and_retire(db):
    item = lp.create_option(db, "Consumers 2027", keywords="consumer, contract")
    assert item.code.startswith("LS-OPT-") and not item.active and item.topic.is_option
    assert item in lp.option_items(db)
    crime = plan_item(db, "LS-CRIME")
    sub = lp.add_sub_area(db, crime, "Policing technology")
    codes = _codes(db)
    assert codes.index(sub.code) == codes.index("LS-CRIME-INTERNATIONAL") + 1 and sub.code.startswith("LS-CRIME-")
    with pytest.raises(ValueError):
        lp.add_sub_area(db, crime, "Again", code=sub.code)
    lp.retire(db, item)
    assert item not in lp.option_items(db)
    lp.retire(db, sub)
    assert not sub.active and sub.status == "LOCKED"


@pytest.mark.skipif(not (SEED_DIR / "legal_v2.json").exists(), reason="v2 Legal content not merged into data/seed yet")
def test_real_v2_content_loads_cleanly(db):
    """When the legal-content package's files are merged: every question loads onto its sub-area."""
    import json

    data = json.loads((SEED_DIR / "legal_v2.json").read_text(encoding="utf-8"))
    for q in data["questions"]:
        assert q["type"] in legal_content.QUESTION_TYPES
        assert q["sub_area"] in lp.SUB_AREAS
        row = db.execute(select(Question).where(Question.question_text == q["text"])).scalars().first()
        assert row is not None, q["text"][:80]
        assert db.get(LearningPlanItem, row.plan_item_id).code == q["sub_area"]
        if q["type"] == "stimulus":
            assert row.stimulus_id
    assert st.get(db, "legal_seeded:legal_v2.json")


# ------------------------------------------------------------------ Learning plan page (routes) ---


def test_legal_plan_page_and_controls(db, client):
    page = client.get("/curriculum?subject=LEGAL")
    assert page.status_code == 200
    assert "The criminal investigation process" in page.text and "Option 1" in page.text and "Option 2" in page.text
    assert "confirm them against the NESA Legal Studies syllabus" in page.text

    crime, trial = plan_item(db, "LS-CRIME"), plan_item(db, "LS-CRIME-TRIAL")
    assert "Which Legal topics have you started?" in page.text and "Learning now" in page.text and "Not taught yet" in page.text
    assert "Start here" not in page.text
    r = client.post(f"/curriculum/item/{trial.id}/start-here", follow_redirects=False)  # no sequence for Legal
    assert r.status_code == 303 and "any%20order" in r.headers["location"]
    r = client.post("/curriculum/LEGAL/advance", follow_redirects=False)
    assert "any%20order" in r.headers["location"]
    db.expire_all()
    assert plan_item(db, "LS-CRIME-INVESTIGATION").status == "LOCKED" and plan_item(db, "LS-CRIME-NATURE").status == "LEARNING"
    r = client.post(f"/curriculum/item/{trial.id}/status", data={"status": "LEARNING"}, follow_redirects=False)
    assert r.status_code == 303 and f"#item{trial.id}" in r.headers["location"]
    db.expire_all()
    assert plan_item(db, "LS-CRIME-TRIAL").status == "LEARNING" and plan_item(db, "LS-CRIME-NATURE").status == "LEARNING"
    assert plan_item(db, "LS-CRIME-INVESTIGATION").status == "LOCKED" and plan_item(db, "LS-HR-ENFORCE").status == "LOCKED"
    assert st.get(db, "legal_topics_chosen") is True  # a status change answers the first-use picker
    assert "Update which Legal topics you have started" in client.get("/curriculum?subject=LEGAL").text

    client.post(f"/curriculum/item/{crime.id}/status", data={"status": "REVISION"})
    db.expire_all()
    assert all(plan_item(db, c).status == "REVISION" for c in CRIME_SUBS)
    client.post(f"/curriculum/item/{plan_item(db, 'LS-CRIME-YOUNG').id}/status", data={"status": "LOCKED"})
    db.expire_all()
    assert plan_item(db, "LS-CRIME").status == "REVISION"  # header: the most active sub-area status
    client.post(f"/curriculum/item/{plan_item(db, 'LS-CRIME-TRIAL').id}/status", data={"status": "LEARNING"})
    db.expire_all()
    assert plan_item(db, "LS-CRIME").status == "LEARNING"

    fam, wp, gep = (plan_item(db, c) for c in ("LS-OPT-FAMILY", "LS-OPT-WORKPLACE", "LS-OPT-GEP"))
    r = client.post("/curriculum/LEGAL/options", data={"option1": fam.id, "option2": wp.id}, follow_redirects=False)
    assert "is%20now%20active" in r.headers["location"] and "content%20check" in r.headers["location"]
    db.expire_all()
    assert plan_item(db, "LS-OPT-FAMILY").active and plan_item(db, "LS-OPT-WORKPLACE").active
    r = client.post(f"/curriculum/item/{gep.id}/option", data={"active": 1}, follow_redirects=False)
    assert "at%20most%202" in r.headers["location"]
    db.expire_all()
    assert not plan_item(db, "LS-OPT-GEP").active
    page = client.get("/curriculum?subject=LEGAL&msg=hello")
    assert "Not much to practise yet" in page.text and ">hello<" in page.text

    r = client.post("/curriculum/LEGAL/sub-area", data={"parent_id": crime.id, "title": "Crime — Technology and policing"}, follow_redirects=False)
    db.expire_all()
    new = db.execute(select(LearningPlanItem).where(LearningPlanItem.title == "Crime — Technology and policing")).scalar_one()
    assert new.code.startswith("LS-CRIME-") and new.status == "LOCKED"
    client.post(f"/curriculum/item/{new.id}/rename", data={"title": "Crime — Technology and investigation"})
    client.post(f"/curriculum/item/{new.id}/retire")
    db.expire_all()
    assert not db.get(LearningPlanItem, new.id).active
    assert "Retired (1)" in client.get("/curriculum?subject=LEGAL").text
    client.post(f"/curriculum/item/{new.id}/restore")
    db.expire_all()
    assert db.get(LearningPlanItem, new.id).active and "retired" not in (db.get(LearningPlanItem, new.id).notes or "").lower()

    client.post("/curriculum/LEGAL/option/new", data={"name": "Technology and the law", "keywords": "privacy"})
    assert "Technology and the law" in client.get("/curriculum?subject=LEGAL").text
    client.post("/curriculum/LEGAL/syllabus-confirmed", data={"confirmed": 1})
    db.expire_all()
    assert st.get(db, "legal_syllabus_confirmed") is True
    # other subjects keep the generic list
    assert "Import a textbook sequence" in client.get("/curriculum?subject=MATHS").text


def test_picker_routes_and_dashboard_notice(db, client):
    assert "Which Legal topics have you started?" in client.get("/").text
    page = client.get("/legal-evidence")
    assert "Which Legal topics have you started?" in page.text and 'name="next" value="/legal-evidence"' in page.text
    ids = [plan_item(db, c).id for c in ("LS-CRIME-SENTENCING", "LS-HR-NATURE")]
    r = client.post("/curriculum/LEGAL/started", data={"started": ids, "next": "/legal-evidence"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/legal-evidence?msg=Saved")
    db.expire_all()
    assert plan_item(db, "LS-CRIME-SENTENCING").status == "LEARNING" and plan_item(db, "LS-CRIME-NATURE").status == "LOCKED"
    assert "Which Legal topics have you started?" not in client.get("/").text
    assert "Which Legal topics have you started?" not in client.get("/legal-evidence").text
    # an unknown return address falls back to the plan page; too many options is refused with a message
    opts = [o.id for o in lp.option_items(db)][:3]
    r = client.post("/curriculum/LEGAL/started", data={"started": opts, "next": "https://example.com"}, follow_redirects=False)
    assert r.headers["location"].startswith("/curriculum?subject=LEGAL&msg=You%20can%20study%20at%20most")
    r = client.post("/curriculum/LEGAL/started", data={}, follow_redirects=False)
    assert "no%20Legal%20topics%20started" in r.headers["location"]

