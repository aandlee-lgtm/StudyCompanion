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


def test_start_here_only_changes_one_core_topic(db):
    trial = plan_item(db, "LS-CRIME-TRIAL")
    lp.start_here(db, trial)
    status = {i.code: i.status for i in lp.legal_items(db)}
    assert [status[c] for c in CRIME_SUBS] == ["LEARNED", "LEARNED", "LEARNING", "LOCKED", "LOCKED", "LOCKED"]
    assert status["LS-HR-NATURE"] == "LEARNING" and status["LS-HR-ENFORCE"] == "LOCKED"
    assert status["LS-CRIME"] == "LEARNING"
    lp.set_all_sub_areas(db, plan_item(db, "LS-CRIME"), "REVISION")
    assert plan_item(db, "LS-CRIME").status == "REVISION"
    lp.set_all_sub_areas(db, plan_item(db, "LS-CRIME"), "LOCKED")
    assert plan_item(db, "LS-CRIME").status == "LOCKED"


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
