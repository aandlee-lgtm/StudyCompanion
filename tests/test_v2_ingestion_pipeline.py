"""v2 ingestion on realistic NESA-style PDFs (sources-24) built at test time by
``tests/v2_ingestion_fixtures.py``: segmentation, marks, MCQ keys, guidelines, stimuli, Legal
sections/options, per-segment isolation, the validation gate and never-serve-before-unlock."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.ingestion import pipeline, review
from app.ingestion.servable import blocked_reason, requirements_unlocked
from app.models import LearningPlanItem, Question, ReviewDecision, Stimulus
from app.models.common import APPROVAL_APPROVED, APPROVAL_PENDING, APPROVAL_REJECTED, LEARNING, LOCKED
from app.models.ingestion import QuestionPlanItem, QuestionStimulus
from app.selection.context import build_context
from app.selection.engine import build_daily_selection, is_servable
from tests import v2_ingestion_fixtures as fx
from tests.conftest import TUESDAY, plan_item
from tests.fakes import FakeProvider

GARBAGE = ("Office Use Only", "End of Question", "continues on page", "(continued)", "End of paper", "Attempt Questions", "Allow about")


@pytest.fixture(scope="module")
def pdfs(tmp_path_factory) -> dict[str, Path]:
    return fx.build_all(tmp_path_factory.mktemp("nesa"))


def _qs(db, source_id) -> dict[str, Question]:
    return {q.question_number: q for q in db.execute(select(Question).where(Question.source_id == source_id)).scalars()}


def _codes(q: Question) -> set[str]:
    return {i["code"] for i in (q.import_meta or {}).get("validation", []) if i.get("blocking", True)}


# ---------------------------------------------------------------- segmentation ---
def test_maths_paper_segmentation_marks_parts_and_mcq(pdfs):
    an = pipeline.analyse(pdfs["maths"], pdfs["maths_mg"])
    units = {u.number: u for u in an.seg.units}
    assert [str(n) for n in range(1, 11)] == [n for n in units if n.isdigit() and int(n) <= 10]
    for n in range(1, 11):  # every MCQ has exactly four options and a key from the guideline
        assert len(units[str(n)].options) == 4, (n, units[str(n)].options)
    assert an.guidelines.mcq_key == fx.MATHS_KEY
    # marks from the right margin, sub-parts with their own marks, continuation across a page break
    assert units["11(a)"].marks == 2
    assert [(p.label, p.marks) for p in units["11(b)"].parts] == [("(i)", 3), ("(ii)", 2)] and units["11(b)"].marks == 5
    assert [(p.label, p.marks) for p in units["13(b)"].parts] == [("(i)", 2), ("(ii)", 2)]
    assert "nearest cent" in units["13(b)"].text  # (ii) after 'Question 13 (continued)' stays in (b)
    assert units["12"].marks == 3 and units["14"].marks == 2
    # graph labels and table values are never read as marks
    assert units["11(d)"].marks == 6 and units["13(e)"].marks == 4
    # no garbage segments: instructions, footers, barcodes and continuation lines are noise
    for u in an.seg.units:
        assert not any(g in u.text for g in GARBAGE), (u.number, u.text[:80])
    exp = {e["section"]: e for e in an.seg.expected_vs_detected()}
    assert exp["I"]["expected"] == exp["I"]["detected"] == 10


def test_ruled_booklet_segments_like_the_plain_paper(pdfs):
    plain = {u.number: (u.marks, [p.label for p in u.parts], len(u.options)) for u in pipeline.analyse(pdfs["maths"]).seg.units}
    ruled = {u.number: (u.marks, [p.label for p in u.parts], len(u.options)) for u in pipeline.analyse(pdfs["maths_booklet"]).seg.units}
    assert plain == ruled


def test_guidelines_keyed_by_full_label_with_criteria_rows(pdfs):
    an = pipeline.analyse(pdfs["maths"], pdfs["maths_mg"])
    gs = an.guidelines
    e = gs.entry("11(b)(ii)")
    assert e is not None and e.top_mark == 2 and "sketch" in e.text.lower()
    assert gs.entry("11(b)(i)").top_mark == 3  # sub-parts are not overwritten by their siblings
    rows = gs.entry("11(a)").as_dict()["criteria"]
    assert rows and rows[0]["max"] == 2 and "Provides correct solution" in rows[0]["criterion"]
    assert "Marking Guidelines" not in (gs.entry("12").text or "")  # running header stripped


# ----------------------------------------------------------------------- import ---
def test_offline_import_queues_everything_and_rejects_extension(db, pdfs):
    r = pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced", guideline_pdf=pdfs["maths_mg"])
    qs = _qs(db, r.source_id)
    assert r.approved == 0 and r.failed == 0 and r.mcq_keyed == r.mcq_total == 10
    assert r.guideline_matched == r.guideline_total
    assert qs["1"].answer == {"type": "mcq", "value": "B"} and len(qs["1"].options) == 4
    assert [(p.label, p.marks) for p in qs["11(b)"].parts] == [("(i)", 3), ("(ii)", 2)]
    assert qs["11(b)"].parts[0].guideline and "stationary" in qs["11(b)"].parts[0].guideline
    assert qs["14"].approval_status == APPROVAL_REJECTED and qs["14"].is_extension  # induction is Extension 1
    assert all(q.approval_status == APPROVAL_PENDING for n, q in qs.items() if n != "14")
    # every pending question records why it was not approved automatically
    assert all((q.import_meta or {}).get("auto_approval_blockers") for n, q in qs.items() if n != "14")
    assert db.execute(select(ReviewDecision).where(ReviewDecision.question_id == qs["14"].id, ReviewDecision.actor == "import")).scalars().first()


def test_ai_import_auto_approves_only_gate_passing_questions(db, pdfs):
    fake = FakeProvider(default={"plan_item_codes": ["1H"], "relevance": "DIRECT", "relevance_score": 0.95, "confidence": 0.95,
                                 "reason": "Limiting sums are unchanged.", "student_rationale": "Same skill as the 2027 course."})
    r = pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced", guideline_pdf=pdfs["maths_mg"], provider=fake)
    qs = _qs(db, r.source_id)
    assert r.approved >= 10
    for q in qs.values():
        if q.approval_status == APPROVAL_APPROVED:
            assert not review.blocking(review.gate(db, q)), q.question_number
            assert db.execute(select(ReviewDecision).where(ReviewDecision.question_id == q.id, ReviewDecision.action == "auto_approve")).scalars().first()
    assert qs["14"].approval_status == APPROVAL_REJECTED  # Extension stays rejected whatever the AI says


def test_ai_reply_without_a_valid_subtopic_is_never_auto_approved(db, pdfs):
    fake = FakeProvider(default={"plan_item_codes": ["ZZ-NOPE"], "relevance": "DIRECT", "confidence": 0.99, "reason": "Looks fine."})
    r = pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced", guideline_pdf=pdfs["maths_mg"], provider=fake)
    assert r.approved == 0
    q = _qs(db, r.source_id)["1"]
    assert any("did not cite a valid subtopic" in b for b in q.import_meta["auto_approval_blockers"])


def test_english_stimulus_booklet_creates_linked_attributed_texts(db, pdfs):
    r = pipeline.import_paper(db, pdfs["english"], title="NESA 2025 HSC English Advanced Paper 1", guideline_pdf=pdfs["english_mg"],
                              stimulus_pdf=pdfs["english_stimulus"])
    assert r.stimuli == 4 and r.failed == 0
    stims = db.execute(select(Stimulus).where(Stimulus.source_id == r.source_id)).scalars().all()
    assert len(stims) == 4 and all(s.attribution and s.attribution.startswith("©") for s in stims)
    poem = next(s for s in stims if "Poem" in s.title)
    assert "\n" in poem.body  # verse keeps its line breaks
    qs = _qs(db, r.source_id)
    q4 = qs["4"]
    labels = [row.label for row in db.execute(select(QuestionStimulus).where(QuestionStimulus.question_id == q4.id)
                                              .order_by(QuestionStimulus.position)).scalars()]
    assert labels == ["Text 1", "Text 4"]
    assert q4.category == "unseen" and "stimulus_refs" not in _codes(q4)
    # Section II on a superseded text is ADAPTABLE: never approvable as written
    q5 = qs["5"]
    assert q5.relevance_status == "ADAPTABLE" and "needs_adaptation" in _codes(q5)
    with pytest.raises(review.ValidationFailed):
        review.approve(db, q5)


def test_english_unseen_question_without_its_text_is_blocked(db, pdfs):
    r = pipeline.import_paper(db, pdfs["english"], title="NESA 2025 HSC English Advanced Paper 1")
    q1 = _qs(db, r.source_id)["1"]
    assert {"stimulus_missing", "stimulus_refs"} & _codes(q1)
    with pytest.raises(review.ValidationFailed):
        review.approve(db, q1)


def test_legal_sections_options_either_or_and_mcq_key(db, pdfs):
    r = pipeline.import_paper(db, pdfs["legal"], title="NESA 2025 HSC Legal Studies", guideline_pdf=pdfs["legal_mg"])
    assert r.failed == 0 and r.mcq_keyed == r.mcq_total == 5  # 'Section IV – 50 marks' no longer crashes the import
    qs = _qs(db, r.source_id)
    a, b = qs["23(a)"], qs["23(b)"]
    assert a.marks == b.marks == 25 and a.import_meta["alternative_group"] == b.import_meta["alternative_group"] == "23"
    consumers = plan_item(db, "LS-OPT-CONSUMERS")
    assert a.plan_item_id == consumers.id and a.category == "option"  # option questions never map to core Crime
    assert qs["24(a)"].plan_item_id == plan_item(db, "LS-OPT-FAMILY").id
    assert all(q.legal_fact_currency == "check" for q in qs.values())  # offline Legal imports default to check
    assert "legal_check" in _codes(qs["1"])  # section 8C: currency must be confirmed before approval
    for q in qs.values():
        assert not any(g in q.question_text for g in GARBAGE + ("Answer EITHER", "Section III", "Section IV"))


# ------------------------------------------------------------- isolation / input ---
def test_one_bad_segment_never_aborts_the_paper(db, pdfs, monkeypatch):
    real = pipeline._qtype

    def boom(code, u, marks):
        if u.number == "12":
            raise RuntimeError("synthetic failure")
        return real(code, u, marks)

    monkeypatch.setattr(pipeline, "_qtype", boom)
    r = pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced")
    assert r.failed == 1 and r.questions >= 19 and any("Q12" in e for e in r.errors)
    assert "12" not in _qs(db, r.source_id)
    assert r.status == "segmented_with_errors"


def test_input_checks_dry_run_and_duplicate_import(db, pdfs, tmp_path):
    with pytest.raises(pipeline.ImportFailed):
        pipeline.import_paper(db, tmp_path / "missing.pdf", title="x")
    txt = tmp_path / "notes.pdf"
    txt.write_text("not a pdf")
    with pytest.raises(pipeline.ImportFailed):
        pipeline.import_paper(db, txt, title="x")
    before = db.execute(select(Question.id)).all()
    dry = pipeline.import_paper(db, pdfs["maths"], title="dry", guideline_pdf=pdfs["maths_mg"], dry_run=True)
    assert dry.dry_run and dry.segments and db.execute(select(Question.id)).all() == before
    pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced")
    with pytest.raises(pipeline.DuplicateImport):
        pipeline.import_paper(db, pdfs["maths"], title="again")
    again = pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced", replace=True)
    assert again.questions >= 19  # unattempted, unapproved questions were re-segmented


# --------------------------------------------------------- validation gate (review) ---
def test_review_approval_requires_every_gate(db, pdfs):
    r = pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced")  # no guideline: no MCQ key
    qs = _qs(db, r.source_id)
    mcq = qs["3"]
    assert "mcq_key" in _codes(mcq)
    with pytest.raises(review.ValidationFailed) as exc:
        review.approve(db, mcq)
    assert any(i.code == "mcq_key" for i in exc.value.issues) and not mcq.approved
    review.save_edits(db, mcq, {"answer_letter": "A", "plan_item_ids": [plan_item(db, "1B").id], "relevance": "DIRECT"})
    review.approve(db, mcq)
    assert mcq.approved and mcq.approval_status == APPROVAL_APPROVED
    # an edit that breaks a gate withdraws the approval
    review.save_edits(db, mcq, {"options": ["A. 1", "B. 2", "C. 3"]})
    assert not mcq.approved and "mcq_options" in _codes(mcq)
    actions = [d.action for d in db.execute(select(ReviewDecision).where(ReviewDecision.question_id == mcq.id)
                                               .order_by(ReviewDecision.id)).scalars()]
    assert actions[-3:] == ["remap", "approve", "edit"]


def test_partial_needs_kept_parts_and_parts_must_add_up(db, pdfs):
    r = pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced")
    q = _qs(db, r.source_id)["11(b)"]
    review.save_edits(db, q, {"plan_item_ids": [plan_item(db, "2B").id], "relevance": "PARTIAL"})
    assert "partial" in _codes(q)
    review.keep_parts(db, q, [q.parts[0].id])
    assert q.marks == 3 and [p.label for p in q.parts] == ["(i)"] and "partial" not in _codes(q)
    review.save_edits(db, q, {"marks": 5})
    assert "parts_sum" in _codes(q)
    with pytest.raises(review.ValidationFailed):
        review.approve(db, q)


def test_legal_currency_gate_and_adaptation(db, pdfs):
    r = pipeline.import_paper(db, pdfs["legal"], title="NESA 2025 HSC Legal Studies", guideline_pdf=pdfs["legal_mg"])
    q = _qs(db, r.source_id)["21(a)"]
    review.save_edits(db, q, {"plan_item_ids": [plan_item(db, "LS-CRIME").id], "relevance": "DIRECT"})
    with pytest.raises(review.ValidationFailed):
        review.approve(db, q)  # currency 'check'
    review.save_edits(db, q, {"legal_fact_currency": "outdated"})
    assert "legal_outdated" in _codes(q)
    new = review.adapt(db, q, text="Outline the role of police discretion when officers decide whether to arrest a suspect.", marks=3,
                       plan_item_ids=[plan_item(db, "LS-CRIME").id], note="Reworded for current NSW powers.", legal_fact_currency="current")
    assert new.historical_or_generated == "ADAPTED" and new.generated_from_question_id == q.id
    assert new.approved and new.import_meta["adaptation"]["from_label"].endswith("Q21(a)")
    assert q.approval_status == review.APPROVAL_ADAPTED and not q.approved
    with pytest.raises(ValueError):
        review.adapt(db, q, text=q.question_text, marks=3, plan_item_ids=[], note="same")


# ------------------------------------------------------------- never serve early ---
def test_approved_import_on_locked_subtopic_is_never_served(db, pdfs):
    r = pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced", guideline_pdf=pdfs["maths_mg"])
    q = _qs(db, r.source_id)["11(a)"]  # limiting sum: 1H, LOCKED on day 1
    review.save_edits(db, q, {"plan_item_ids": [plan_item(db, "1H").id], "relevance": "DIRECT"})
    review.approve(db, q)
    ctx = build_context(db, TUESDAY)
    assert q.approved and not is_servable(ctx, q)
    assert blocked_reason(ctx.plan, q) == "Waits for 1H"
    sel = build_daily_selection(db, ctx)
    assert q.id not in {s.question.id for s in sel.items}


def test_multi_topic_question_waits_for_every_required_subtopic(db, pdfs):
    r = pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced", guideline_pdf=pdfs["maths_mg"])
    q = _qs(db, r.source_id)["11(a)"]
    a, h = plan_item(db, "1A"), plan_item(db, "1H")
    review.save_edits(db, q, {"plan_item_ids": [a.id, h.id], "relevance": "DIRECT"})
    assert q.plan_item_id == h.id  # the primary is the LATEST subtopic: released late, never early
    rows = db.execute(select(QuestionPlanItem).where(QuestionPlanItem.question_id == q.id)).scalars().all()
    assert {x.plan_item_id for x in rows} == {a.id, h.id}
    review.approve(db, q)
    # even with the reviewer forcing an unlocked primary, the LOCKED requirement (1H) still blocks it
    review.save_edits(db, q, {"plan_item_ids": [a.id, h.id], "primary_plan_item_id": a.id})
    assert q.plan_item_id == a.id and q.approved
    ctx = build_context(db, TUESDAY)
    assert ctx.plan[a.id].status == LEARNING and ctx.plan[h.id].status == LOCKED
    assert not requirements_unlocked(ctx.plan, q) and not is_servable(ctx, q)
    h.status = LEARNING
    db.flush()
    ctx = build_context(db, TUESDAY)
    assert requirements_unlocked(ctx.plan, q) and is_servable(ctx, q)


def test_unmapped_and_inactive_option_questions_are_never_served(db, pdfs):
    r = pipeline.import_paper(db, pdfs["legal"], title="NESA 2025 HSC Legal Studies", guideline_pdf=pdfs["legal_mg"])
    qs = _qs(db, r.source_id)
    opt = qs["23(a)"]
    review.save_edits(db, opt, {"legal_fact_currency": "current", "relevance": "DIRECT"})
    review.approve(db, opt)
    ctx = build_context(db, TUESDAY)
    assert opt.approved and not is_servable(ctx, opt)  # the Consumers option is not active
    unm = next(q for q in qs.values() if (q.import_meta or {}).get("mapping_state") == "UNMAPPED")
    assert not requirements_unlocked(ctx.plan, unm)
    with pytest.raises(review.ValidationFailed):
        review.approve(db, unm)


def test_plan_items_have_expected_day_one_status(db):
    # guards the assumptions above: 1A LEARNING, 1H LOCKED, options inactive
    assert plan_item(db, "1A").status == LEARNING and plan_item(db, "1H").status == LOCKED
    assert not db.execute(select(LearningPlanItem).where(LearningPlanItem.code == "LS-OPT-CONSUMERS")).scalar_one().active
