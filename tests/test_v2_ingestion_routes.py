"""v2 ingestion web routes: library filters, detail reveal gate (adaptive-01), review tool with
gates, batch actions and adaptation editor (sources-12/13, english-11, legal-12), audit line
(sources-19), import form (sources-08/17/23) and source pages."""
from __future__ import annotations

from pathlib import Path

import re

import pytest
from sqlalchemy import select

from app.ingestion import pipeline, review
from app.models import Attempt, Question
from app.models.common import APPROVAL_APPROVED
from app.services import settings as st
from tests import v2_ingestion_fixtures as fx
from tests.conftest import plan_item


@pytest.fixture(scope="module")
def pdfs(tmp_path_factory) -> dict[str, Path]:
    return fx.build_all(tmp_path_factory.mktemp("nesa_routes"))


def _plain(text: str) -> str:
    """The start of a text before any character the template escapes."""
    return re.split(r"['\"&<>\n]", text.strip())[0][:40].strip()


def _import_maths(db, pdfs, **kw):
    r = pipeline.import_paper(db, pdfs["maths"], title="NESA 2025 HSC Mathematics Advanced", guideline_pdf=pdfs["maths_mg"], **kw)
    db.commit()
    return {q.question_number: q for q in db.execute(select(Question).where(Question.source_id == r.source_id)).scalars()}, r


def test_library_filters_and_sorting(client, db, pdfs):
    _import_maths(db, pdfs)
    for qs in ["", "?subject=MATHS&q=limiting", "?band=never&revision=overdue", "?band=lt50", "?sort=marks&desc=1",
               "?approval=pending&origin=HISTORICAL&item=8", "?outcome=1&page=2"]:
        r = client.get("/questions" + qs)
        assert r.status_code == 200, qs
    r = client.get("/questions?q=limiting+sum")
    assert "limiting sum" in r.text and "Find the limiting sum" in r.text
    assert "New question" in client.get("/questions").text


def test_detail_hides_solutions_until_attempt_and_reveal_records_a_skip(client, db):
    q = db.execute(select(Question).where(Question.approved.is_(True), Question.model_answer.is_not(None))).scalars().first()
    assert q is not None
    secret = _plain(q.model_answer)
    assert len(secret) > 10
    page = client.get(f"/questions/{q.id}").text
    assert "hidden" in page.lower() and secret not in page
    r = client.post(f"/questions/{q.id}/reveal", follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    att = db.execute(select(Attempt).where(Attempt.question_id == q.id)).scalars().all()
    assert len(att) == 1 and att[0].skipped
    assert secret in client.get(f"/questions/{q.id}").text


def test_admin_mode_shows_solutions(client, db):
    q = db.execute(select(Question).where(Question.approved.is_(True), Question.model_answer.is_not(None))).scalars().first()
    st.set_(db, "admin_mode", True)
    db.commit()
    assert _plain(q.model_answer) in client.get(f"/questions/{q.id}").text


def test_review_queue_gate_edit_approve_and_batch(client, db, pdfs):
    qs, r = _import_maths(db, pdfs)
    page = client.get(f"/admin/review?source={r.source_id}")
    assert page.status_code == 200 and "Blocks approval" in page.text and f'id="q{qs["3"].id}"' in page.text
    assert client.get("/admin/review?status=needs_fix&conf=low&subject=MATHS").status_code == 200
    q = qs["11(c)"]  # UNMAPPED, PARTIAL, text too short ('x3e2x' lost its superscripts)
    # approval refused by the gate: redirected back to the card with the reason
    resp = client.post(f"/admin/review/{q.id}/approve", data={"back": "/admin/review"}, follow_redirects=False)
    loc = resp.headers["location"].replace("%20", "+")
    assert resp.status_code == 303 and "Not+approved" in loc and loc.endswith(f"#q{q.id}")
    db.expire_all()
    assert not db.get(Question, q.id).approved
    # edit text, subtopic and relevance, then approve
    item = plan_item(db, "4B")
    client.post(f"/admin/review/{q.id}/edit", data={"back": "/admin/review", "plan_item_ids": [str(item.id)], "relevance": "DIRECT",
                                                   "question_text": "Differentiate y = x^3 e^(2x) with respect to x.", "marks": "2",
                                                   "student_rationale": "Product rule with an exponential, as in 4B."})
    client.post(f"/admin/review/{q.id}/approve", data={"back": "/admin/review"})
    db.expire_all()
    q = db.get(Question, q.id)
    assert q.approved and q.plan_item_id == item.id and q.import_meta["student_rationale"].startswith("Product rule")
    # batch approve: MCQs with keys and a subtopic pass, the rest are reported
    ids = [qs[n].id for n in ("2", "3", "14")]
    resp = client.post("/admin/review/batch", data={"ids": [str(i) for i in ids], "action": "approve", "back": "/admin/review"}, follow_redirects=False)
    assert resp.status_code == 303 and "not+changed" in resp.headers["location"].replace("%20", "+")
    db.expire_all()
    assert db.get(Question, qs["2"].id).approved and not db.get(Question, qs["14"].id).approved  # Extension never approved


def test_single_card_page_and_mcq_key_editing(client, db, pdfs):
    qs, _ = _import_maths(db, pdfs)
    q = qs["5"]
    assert client.get(f"/admin/review/{q.id}").status_code == 200
    client.post(f"/admin/review/{q.id}/edit", data={"back": f"/admin/review/{q.id}", "answer_letter": "C", "plan_item_ids": [str(plan_item(db, "Y11-FUNC").id)],
                                                   "relevance": "DIRECT", "option_0": "A. a", "option_1": "B. b", "option_2": "C. c", "option_3": "D. d"})
    db.expire_all()
    q = db.get(Question, q.id)
    assert q.answer == {"type": "mcq", "value": "C"} and len(q.options) == 4


def test_adaptation_editor_creates_adapted_copy(client, db, pdfs):
    r = pipeline.import_paper(db, pdfs["english"], title="NESA 2025 HSC English Advanced Paper 1", guideline_pdf=pdfs["english_mg"],
                              stimulus_pdf=pdfs["english_stimulus"])
    db.commit()
    q5 = db.execute(select(Question).where(Question.source_id == r.source_id, Question.question_number == "5")).scalar_one()
    assert client.get(f"/admin/review/{q5.id}/adapt").status_code == 200
    resp = client.post(f"/admin/review/{q5.id}/adapt/save", data={
        "text": "\"Human experiences are rarely simple.\" To what extent does your prescribed text explore this idea? Refer to one scene.",
        "marks": "20", "plan_item_ids": [str(plan_item(db, "EN-THE").id)], "note": "Prescribed text replaced by the student's 2027 text.",
        "category": "course", "stimuli_present": "1", "approve_now": "1"}, follow_redirects=False)
    assert resp.status_code == 303 and "/admin/review/" in resp.headers["location"]
    db.expire_all()
    new = db.execute(select(Question).where(Question.generated_from_question_id == q5.id)).scalar_one()
    assert new.historical_or_generated == "ADAPTED" and new.approval_status == APPROVAL_APPROVED
    assert db.get(Question, q5.id).approval_status == review.APPROVAL_ADAPTED
    detail = client.get(f"/questions/{new.id}").text
    assert "Adapted from NESA 2025 HSC English Advanced Paper 1 Q5" in detail
    # a missing note is refused with a message, not a 500
    resp = client.post(f"/admin/review/{q5.id}/adapt/save", data={"text": "Explain how a text you studied represents memory.", "marks": "5", "note": ""},
                       follow_redirects=False)
    assert resp.status_code == 303 and "flash=" in resp.headers["location"]


def test_audit_line_on_question_page(client, db, pdfs):
    qs, _ = _import_maths(db, pdfs)
    q = qs["11(a)"]
    review.save_edits(db, q, {"plan_item_ids": [plan_item(db, "1A").id], "relevance": "DIRECT", "student_rationale": "Same skill in 2027."})
    review.approve(db, q)
    db.commit()
    page = client.get(f"/practice/{q.id}").text
    assert "Source: NESA 2025 HSC Mathematics Advanced Q11(a), p." in page
    assert "2027 mapping:" in page and "1A" in page and "Relevance: Direct (reviewed" in page and "Same skill in 2027." in page
    assert f'href="/questions/{q.id}">Details' not in page  # no route to the answers before an attempt


def test_import_form_dry_run_duplicate_and_stimulus(client, db, pdfs):
    files = {"paper": ("p.pdf", pdfs["maths"].read_bytes(), "application/pdf"), "guideline": ("g.pdf", pdfs["maths_mg"].read_bytes(), "application/pdf")}
    r = client.post("/admin/import", data={"title": "NESA 2025 HSC Mathematics Advanced", "dry_run": "1"}, files=files)
    assert r.status_code == 200 and "Dry run" in r.text and "11(b)" in r.text
    assert db.execute(select(Question).where(Question.source_exam == "NESA 2025 HSC Mathematics Advanced")).first() is None
    r = client.post("/admin/import", data={"title": "NESA 2025 HSC Mathematics Advanced"}, files=files)
    assert "Imported" in r.text and "answer key found for 10 of 10" in r.text
    r = client.post("/admin/import", data={"title": "again"}, files=files)
    assert r.status_code == 200 and "already imported" in r.text
    files = {"paper": ("e.pdf", pdfs["english"].read_bytes(), "application/pdf"),
             "stimulus": ("s.pdf", pdfs["english_stimulus"].read_bytes(), "application/pdf")}
    r = client.post("/admin/import", data={"title": "NESA 2025 HSC English Advanced Paper 1"}, files=files)
    assert "4 texts imported" in r.text
    bad = {"paper": ("x.pdf", b"not a pdf", "application/pdf")}
    r = client.post("/admin/import", data={"title": "bad"}, files=bad)
    assert r.status_code == 200 and "notice warn" in r.text


def test_sources_pages_and_pdf(client, db, pdfs):
    _, rep = _import_maths(db, pdfs)
    assert "NESA 2025 HSC Mathematics Advanced" in client.get("/sources").text
    page = client.get(f"/sources/{rep.source_id}")
    assert page.status_code == 200 and "segmented" in page.text
    pdf = client.get(f"/sources/{rep.source_id}/pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert client.get(f"/sources/{rep.source_id}/pdf?kind=marking_guideline").content[:4] == b"%PDF"
    r = client.post(f"/sources/{rep.source_id}/remove-unused", follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    assert db.execute(select(Question).where(Question.source_id == rep.source_id, Question.approval_status == "pending")).first() is None


def test_retire_and_restore_from_detail(client, db, pdfs):
    qs, _ = _import_maths(db, pdfs)
    q = qs["11(a)"]
    review.save_edits(db, q, {"plan_item_ids": [plan_item(db, "1A").id], "relevance": "DIRECT"})
    review.approve(db, q)
    db.commit()
    client.post(f"/questions/{q.id}/retire", data={"reason": "duplicate of a seed question"})
    db.expire_all()
    assert db.get(Question, q.id).approval_status == review.APPROVAL_RETIRED and not db.get(Question, q.id).approved
    client.post(f"/questions/{q.id}/restore")
    db.expire_all()
    assert db.get(Question, q.id).approval_status == "pending"
