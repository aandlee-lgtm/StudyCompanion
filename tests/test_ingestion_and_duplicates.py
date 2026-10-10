from datetime import timedelta
from pathlib import Path

import fitz
import pytest
from sqlalchemy import select

from app.ingestion import pipeline
from app.models import Question
from app.models.common import APPROVAL_APPROVED, APPROVAL_PENDING, APPROVAL_REJECTED
from app.selection.context import build_context
from app.selection.engine import build_daily_selection
from app.services import assessment, clock, question_bank
from app.services.fingerprint import fingerprint, similarity
from tests.conftest import TUESDAY, plan_item
from tests.fakes import FakeProvider


def make_pdf(path: Path, pages: list[str]) -> Path:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        y = 60
        for line in text.splitlines():
            page.insert_text((50, y), line, fontsize=10)
            y += 14
    doc.save(path)
    return path


PAPER = [
    "2023 HIGHER SCHOOL CERTIFICATE EXAMINATION\nMathematics Advanced\nSection I\n"
    "1 What is the sum of the first 10 terms of the arithmetic series 2 + 5 + 8 + ...?\nA. 155\nB. 145\nC. 165\nD. 175\n",
    "Section II\nQuestion 11 (14 marks)\n(a) Find the limiting sum of the geometric series 8 + 4 + 2 + ...\n2\n"
    "(b) Differentiate y = x e^(2x) and find any stationary points.\n3\n",
]
GUIDE = ["Marking guidelines\nQuestion 11 (a)\nCriteria: Provides correct solution 2 marks. Uses limiting sum formula 1 mark.\nSample answer: 16\n"]


def test_import_paper_pipeline_offline(db, tmp_path):
    paper = make_pdf(tmp_path / "p.pdf", PAPER)
    guide = make_pdf(tmp_path / "g.pdf", GUIDE)
    r = pipeline.import_paper(db, paper, title="NESA 2023 HSC Mathematics Advanced (test)", guideline_pdf=guide)
    db.commit()
    assert r.questions >= 3
    qs = db.execute(select(Question).where(Question.source_id == r.source_id)).scalars().all()
    # offline mapping is never trusted enough to auto-approve
    assert all(q.approval_status == APPROVAL_PENDING for q in qs)
    assert {q.question_number for q in qs} >= {"1", "11(a)", "11(b)"}
    q11a = next(q for q in qs if q.question_number == "11(a)")
    assert q11a.marks == 2 and q11a.guideline_official and "limiting sum" in q11a.marking_guideline
    assert q11a.source.local_file and Path(q11a.source.local_file).exists()  # original PDF retained
    mcq = next(q for q in qs if q.question_number == "1")
    assert mcq.question_type == "mcq" and len(mcq.options) == 4
    # pending questions are never served
    sel = build_daily_selection(db, build_context(db, TUESDAY))
    assert not {q.id for q in qs} & {s.question.id for s in sel.items}


def test_high_confidence_direct_ai_mapping_auto_approves(db, tmp_path):
    paper = make_pdf(tmp_path / "p.pdf", PAPER)
    fake = FakeProvider(default={"topic_code": "MA12-SEQ", "focus_area": "Sequences and series", "relevance": "DIRECT", "relevance_score": 0.95,
                                 "confidence": 0.93, "reason": "Arithmetic series: unchanged in the 2027 syllabus."})
    from app.ai import factory

    factory.set_test_provider(fake)
    r = pipeline.import_paper(db, paper, title="NESA 2023 (AI)")
    assert r.approved == r.questions


def test_extension_paper_refused(db, tmp_path):
    paper = make_pdf(tmp_path / "e.pdf", ["2022 HIGHER SCHOOL CERTIFICATE EXAMINATION\nMathematics Extension 1\nQuestion 11 (a) Prove by induction ... 3\n"])
    with pytest.raises(ValueError):
        pipeline.import_paper(db, paper, title="Ext 1")


def test_extension_content_rejected_by_mapping(db, tmp_path):
    paper = make_pdf(tmp_path / "p.pdf", ["2021 HIGHER SCHOOL CERTIFICATE EXAMINATION\nMathematics Advanced\nSection II\nQuestion 12\n(a) Use mathematical induction to prove that 6^n - 1 is divisible by 5.\n3\n"])
    r = pipeline.import_paper(db, paper, title="Mixed")
    q = db.execute(select(Question).where(Question.source_id == r.source_id)).scalars().first()
    assert q.approval_status == APPROVAL_REJECTED and q.is_extension


def test_review_actions(db, tmp_path):
    paper = make_pdf(tmp_path / "p.pdf", PAPER)
    r = pipeline.import_paper(db, paper, title="Review test")
    qs = db.execute(select(Question).where(Question.source_id == r.source_id)).scalars().all()
    item = plan_item(db, "1F")
    pipeline.edit_mapping(db, qs[0], plan_item_id=item.id, relevance="DIRECT", reason="AP sum", answer={"type": "num", "value": "155"})
    pipeline.approve(db, qs[0])
    pipeline.reject(db, qs[1], "obsolete")
    pipeline.approve(db, qs[2], adapted=True)
    assert qs[0].approved and qs[0].plan_item_id == item.id
    assert qs[1].approval_status == APPROVAL_REJECTED and qs[1].relevance_status == "REJECT"
    assert qs[2].historical_or_generated == "ADAPTED"


def test_fingerprint_ignores_numbering_and_spacing():
    assert fingerprint("Question 3 (a)  Find   the sum.") == fingerprint("find the sum.")
    assert similarity("Find the sum of the first 10 terms of 2 + 5 + 8", "Find the sum of the first 10 terms of 2 + 5 + 8 + ...") > 0.7


def test_duplicate_creation_returns_existing(db):
    item = plan_item(db, "1A")
    src = question_bank.template_source(db)
    a = question_bank.create_question(db, subject_code="MATHS", source_id=src.id, question_text="Find T_5 when T_n = 2n + 1.", marks=1,
                                      topic_id=item.topic_id, plan_item_id=item.id, answer={"type": "num", "value": "11"}, mapping_reason="t")
    b = question_bank.create_question(db, subject_code="MATHS", source_id=src.id, question_text="1. Find T_5 when T_n = 2n + 1.", marks=1,
                                      topic_id=item.topic_id, plan_item_id=item.id, answer={"type": "num", "value": "11"}, mapping_reason="t")
    assert a.id == b.id


def test_near_duplicate_of_recent_question_suppressed(db):
    item = plan_item(db, "1A")
    src = question_bank.template_source(db)
    text = "A sequence is defined by T_n = 4n^2 + 3. Find the value of the twelfth term of this sequence."
    seen = question_bank.create_question(db, subject_code="MATHS", source_id=src.id, question_text=text, marks=2, difficulty=2,
                                         topic_id=item.topic_id, plan_item_id=item.id, answer={"type": "num", "value": "579"}, mapping_reason="t")
    assessment.submit(db, seen, "579")
    near = question_bank.create_question(db, subject_code="MATHS", source_id=src.id, question_text=text + " Show working.", marks=2, difficulty=2,
                                         topic_id=item.topic_id, plan_item_id=item.id, answer={"type": "num", "value": "579"}, mapping_reason="t")
    db.commit()
    clock.set_today(TUESDAY + timedelta(days=1))
    sel = build_daily_selection(db, build_context(db, clock.today()))
    ids = {s.question.id for s in sel.items}
    assert seen.id not in ids and near.id not in ids
