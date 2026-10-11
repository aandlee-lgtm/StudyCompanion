"""v2 legal-logic: offline Legal marking on resolved citations and required elements, provenance,
currency and the feedback payload (audit legal-03/04/05/06/14/15/21)."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.ai import factory
from app.models import Attempt, AttemptFeedback, LegalEvidence, Question, Subject
from app.services import assessment, clock
from app.services import citations as cit
from app.services import legal_marking as lm
from app.services.assessment import legal as legal_fb
from tests.conftest import TUESDAY

TODAY = date(2026, 10, 13)


class Q:
    """A minimal stand-in for a Question row."""

    def __init__(self, marks=5, verb="Assess", text="Assess the effectiveness of bail laws in balancing the rights of the accused and community safety.",
                 required=None, guideline=None, criteria=None):
        self.marks, self.directive_verb, self.question_text = marks, verb, text
        self.marking_guideline = guideline
        self.solution = {"required_elements": required or [], "criteria": criteria or []}


BANK = cit.Bank([
    {"id": 1, "title": "Bail Act 2013 (NSW)", "item_type": "legislation", "status": "in_force", "last_verified_date": date(2026, 10, 1),
     "aliases": ["Bail Act"], "date": "2013"},
    {"id": 2, "title": "Bail Act 1978 (NSW)", "item_type": "legislation", "status": "repealed", "superseded_by": "Bail Act 2013 (NSW)"},
    {"id": 3, "title": "Bail (Amendment) Act 2024 (NSW)", "item_type": "legislation", "status": "in_force", "date": "2024"},
    {"id": 4, "title": "Crimes Act 1900 (NSW)", "item_type": "legislation", "status": "in_force", "last_verified_date": date(2026, 9, 1)},
])

GOOD = ("Bail laws are largely effective in balancing the rights of the accused with community safety. The Bail Act 2013 (NSW) "
        "requires the court to apply the unacceptable risk test, which protects the presumption of innocence because most accused people "
        "are released while awaiting trial. However, the Bail (Amendment) Act 2024 (NSW) introduced a stricter test for some young people, "
        "which shows law reform responding to community concern about safety. As a result, the law partially balances these interests, "
        "although remand rates remain high and this limits the effectiveness of the law for the accused.")


def test_invented_and_repealed_authorities_are_never_rewarded():
    q = Q()
    base = lm.estimate(q, GOOD, BANK, TODAY)
    invented = lm.estimate(q, GOOD + " The Community Safety Act 2022 (NSW) and Smith v Jones [2023] HCA 9 also apply.", BANK, TODAY)
    assert invented.mark < base.mark and invented.deduction > 0
    assert any("not in your evidence bank" in c for c in invented.corrections)
    assert {j["category"] for j in invented.journal} >= {"unverified/invented authority"}
    repealed = lm.estimate(q, GOOD.replace("Bail Act 2013 (NSW)", "Bail Act 1978 (NSW)"), BANK, TODAY)
    assert repealed.mark < base.mark
    assert any("Bail Act 2013 (NSW)" in c for c in repealed.corrections)  # points to the current law
    assert any(j["category"] == "outdated legislation" for j in repealed.journal)


def test_keyword_stuffing_and_short_answers_are_capped():
    q = Q(marks=15, verb="Evaluate", text="Evaluate the effectiveness of the criminal justice system in achieving justice for young offenders.")
    stuffed = "effective justice courts jury bail parole rights treaty law reform deterrence rehabilitation Bail Act 2013 (NSW) " * 2
    est = lm.estimate(q, stuffed, BANK, TODAY)
    assert est.mark <= 3 and est.caps
    assert lm.estimate(q, "idk", BANK, TODAY).mark == 0


def test_required_elements_drive_the_mark():
    req = ["unacceptable risk test in the Bail Act 2013", "presumption of innocence", "community safety concerns", "judgement on effectiveness"]
    q = Q(required=req)
    full = lm.estimate(q, GOOD, BANK, TODAY)
    partial_text = ("The Bail Act 2013 (NSW) has an unacceptable risk test. Courts apply this test to every bail decision and "
                    "consider the seriousness of the offence, the accused's criminal history and any risk of failing to appear. "
                    "The test is applied by magistrates and judges in the Local Court and higher courts, and decisions can be reviewed "
                    "by a higher court. Bail conditions such as reporting to police or a curfew can be imposed on the accused, and the "
                    "legislation sets out which offences carry a show cause requirement.")
    partial = lm.estimate(q, partial_text, BANK, TODAY)
    assert sum(e["met"] for e in full.elements) >= 3 and full.mark > partial.mark
    assert any(not e["met"] for e in partial.elements) and not partial.caps
    assert "Rewrite your answer so that it covers" in lm.improvement_task(partial, q, [])


def test_rubric_wording_and_alternative_lists_in_required_elements():
    q = Q(marks=2, verb="Identify", text="Identify TWO purposes of sentencing in NSW law.",
          required=["Two purposes from the legislation (punishment, deterrence, community protection, rehabilitation, denunciation)"])
    two = lm.estimate(q, "Two purposes are deterrence of the offender and others, and rehabilitation of the offender.", BANK, TODAY)
    one = lm.estimate(q, "One purpose is deterrence, which discourages the offender and the public.", BANK, TODAY)
    assert two.elements[0]["met"] and one.elements[0]["partly"]


def _legal_questions(db, written=True):
    leg = db.execute(select(Subject).where(Subject.code == "LEGAL")).scalar_one()
    qs = db.execute(select(Question).where(Question.subject_id == leg.id)).scalars().all()
    return [q for q in qs if (q.question_type != "mcq") == written]


def test_every_seeded_model_answer_scores_well_offline(db):
    """legal-05: the app's own model answers are not marked down by the offline estimate."""
    bank = cit.Bank.from_db(db)
    low, ratios = [], []
    for q in _legal_questions(db):
        if not q.model_answer:
            continue
        stim = q.stimulus.body if q.stimulus else None
        est = lm.estimate(q, q.model_answer, bank, TODAY, stimulus=stim)
        ratio = est.mark / q.marks
        ratios.append(ratio)
        floor = 2 / 3 if (q.solution or {}).get("required_elements") else 0.6  # v1 model answers are short and lack required elements
        if ratio < floor - 1e-9:
            low.append((q.id, q.marks, est.mark, [(c.key, round(c.score, 2)) for c in est.components], est.corrections))
    assert not low, low
    assert ratios and sum(ratios) / len(ratios) >= 0.75


def test_offline_feedback_payload_has_all_section_9_elements(db):
    factory.set_test_provider(None)
    q = next(q for q in _legal_questions(db) if q.model_answer and q.marks >= 4)
    resp = q.model_answer + " The Imaginary Justice Act 2021 (NSW) also applies."
    mark, payload, cats, method = assessment.written.mark_written(db, q, resp, {"ai_provider": "offline"}, None) \
        if hasattr(assessment, "written") else (None, None, None, None)
    if payload is None:
        from app.services.assessment.written import mark_written

        mark, payload, cats, method = mark_written(db, q, resp, {"ai_provider": "offline"}, None)
    assert method == "offline_estimate"
    r = payload["result"]
    assert payload["mark"] == mark == r["mark_awarded"]
    assert r["marking_rationale"].startswith("Offline estimate")
    assert any("Imaginary Justice Act 2021" in c for c in r["corrections"])
    assert "unverified/invented authority" in cats
    assert r["improvement_task"] and payload["scaffold"]["claim"] and payload["comparison_rows"]
    assert any(c["status"] == "not_in_bank" for c in payload["citations"])
    # legal-06: the seeded model is labelled as seeded, never as AI-written, and not copied into the offline result
    assert payload["model_answer"] == q.model_answer and r["model_answer"] == ""
    assert payload["model_answer_source"].startswith("Written for this question by HSC Companion")
    # legal-03: currency from the items shown, with the date of the oldest check
    assert payload["currency_line"].startswith("Current information checked")
    assert payload["currency"]["as_at"] == clock.today().isoformat()


def test_ai_marking_redacts_non_bank_authorities_and_resolves_suggestions(db):
    from app.ai.schemas import MarkingResult
    from app.services.assessment.written import written_ctx

    q = next(q for q in _legal_questions(db) if q.marks >= 4)
    bank_title = db.execute(select(LegalEvidence.title)).scalars().first()
    result = MarkingResult(mark_awarded=3, mark_possible=q.marks,
                           model_answer=f"The {bank_title} matters. The Fictional Rights Act 2019 (Cth) also protects people.",
                           evidence_suggestions=[bank_title, "Made Up v Imaginary [2020] HCA 99"],
                           corrections=["The law changed recently.", f"{bank_title} is the relevant authority."])
    ctx = written_ctx(db, q, "My answer cites the Fictional Rights Act 2019 (Cth).", {})
    payload = {"model_answer": result.model_answer}
    legal_fb.post_process(db, q, ctx, result, payload, "ai")
    assert "Fictional Rights Act" not in payload["model_answer"] and "authority removed" in payload["model_answer"]
    assert "Fictional Rights Act 2019 (Cth)" in payload["unverified_references"]
    assert [c["title"] for c in payload["suggestion_cards"]] == [bank_title]
    assert payload["ai_suggestions_not_in_bank"] == ["Made Up v Imaginary [2020] HCA 99"]
    assert result.corrections[0].startswith("Possible issue — verify:") and result.corrections[1].startswith(bank_title)
    assert payload["model_answer_origin"] == "ai" and payload["model_answer_source"].startswith("AI-written")
    assert payload["citations"][0]["status"] == "not_in_bank"


def test_feedback_page_renders_offline_legal_feedback(db, client):
    from tests.conftest import answer_correctly
    from app.services import sessions

    s = sessions.get_or_create_today(db)
    sq = next((sq for sq in s.questions if sq.question.question_type != "mcq" and db.get(Subject, sq.question.subject_id).code == "LEGAL"), None)
    if sq is None:
        pytest.skip("no written Legal question in today's session")
    q = sq.question
    assessment.submit(db, q, (q.model_answer or "An answer") + " The Imaginary Justice Act 2021 (NSW) applies.", sq=sq, confidence="confident", time_seconds=60)
    db.commit()
    att = db.execute(select(Attempt).where(Attempt.question_id == q.id)).scalars().first()
    fb = db.execute(select(AttemptFeedback).where(AttemptFeedback.attempt_id == att.id)).scalars().first()
    assert fb.payload["kind"] == "written" and fb.payload.get("currency_line")
    why = legal_fb.why_lost(q, fb.payload, att)
    assert why and "Imaginary Justice Act 2021" in why
    pos = [x.id for x in s.questions].index(sq.id) + 1
    page = client.get(f"/session/{s.id}/q/{pos}")
    assert page.status_code == 200
    assert "Authorities in your answer" in page.text and "not in your bank" in page.text
    assert "Current information checked" in page.text and "An improved argument" in page.text


def test_legal_marking_prompt_dimensions_date_and_correction_rule(db):
    from app.ai import prompts
    from app.services.assessment.written import written_ctx

    q = next(q for q in _legal_questions(db) if q.marks >= 4)
    text = prompts.marking(written_ctx(db, q, "My response.", {}))
    assert f"TODAY: {clock.today().isoformat()}" in text and "background, not contemporary" in text
    assert "LEGAL EVIDENCE BANK (verification status per item" in text and '"status": "unverified"' in text
    for dim in ("knowledge of relevant law", "law reform", "responsiveness to stimulus", "integration of evidence"):
        assert dim in text
    assert '"textual evidence"' not in text  # English dimensions are replaced for Legal
    assert "unverified/invented authority" in text and "Possible issue — verify:" in text
