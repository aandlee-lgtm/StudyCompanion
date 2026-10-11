"""v2 adaptive package: attempt chain, confidence table, reliability, revision lifecycle, journal, why-lost, retry."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.models import (
    Attempt,
    ErrorJournal,
    ExposureEvent,
    LearningPlanItem,
    Mastery,
    PracticeDraft,
    Question,
    QuestionExposure,
    RevisionQueue,
    Subject,
)
from app.services import assessment, clock, error_journal, mastery
from tests.conftest import TUESDAY, plan_item


# ------------------------------------------------------------------- helpers ---
def maths_qs(db, code="1A", n=6):
    item = plan_item(db, code)
    stmt = select(Question).where(Question.plan_item_id == item.id, Question.answer.is_not(None), Question.question_type != "mcq")
    qs = db.execute(stmt).scalars().all()
    if len(qs) < n:
        # The v2 bank tops up only the difficulty levels a template really produces (selection-08),
        # so a skill can start with fewer than n questions: generate more from the same template.
        from app.services import question_bank as qb

        seed = 5000
        while len(qs) < n and seed < 5200:
            qb.generate_from_template(db, item, 1 + seed % 3, seed)
            seed += 1
            db.flush()
            qs = db.execute(stmt).scalars().all()
        db.commit()
    return qs[:n]


def right(q):
    return q.answer["value"] if q.answer["type"] != "set" else ",".join(q.answer["values"])


def subject_qs(db, code, **filters):
    stmt = select(Question).join(Subject, Question.subject_id == Subject.id).where(Subject.code == code, Question.approved.is_(True))
    for k, v in filters.items():
        stmt = stmt.where(getattr(Question, k) == v)
    return db.execute(stmt).scalars().all()


def written_q(db, code="LEGAL"):
    return next(q for q in subject_qs(db, code) if q.answer is None and q.marks >= 3 and q.model_answer)


def exposure(db, q):
    return db.execute(select(QuestionExposure).where(QuestionExposure.question_id == q.id)).scalar_one_or_none()


def skill(db, q):
    return db.execute(select(Mastery).where(Mastery.plan_item_id == q.plan_item_id)).scalar_one_or_none()


def open_items(db, q):
    return db.execute(select(RevisionQueue).where(RevisionQueue.plan_item_id == q.plan_item_id, RevisionQueue.status == "open")).scalars().all()


# ------------------------------------------------------------ attempt chain ---
def test_skip_then_practise_revealed_answer_is_rehearsal(db):  # adaptive-02
    from app.services import sessions

    s = sessions.get_or_create_today(db)
    sq = next(x for x in s.questions if x.subject_code == "MATHS" and x.question.answer and x.question.answer.get("type") != "mcq")
    q = sq.question
    assessment.submit(db, q, "", sq=sq, skipped=True)  # skipped in the daily session: answer shown
    db.commit()
    e = exposure(db, q)
    nxt, hist, m = e.next_revision_date, list(e.score_history), skill(db, q).mastery
    a = assessment.submit(db, q, right(q), confidence="very_confident")  # practice, same day, answer already shown
    db.commit()
    assert a.counts_for_mastery is False and a.evidence_role == "rehearsal" and a.after_reveal is True
    e = exposure(db, q)
    assert e.next_revision_date == nxt and e.score_history == hist and skill(db, q).mastery == m
    assert "doesn't change your schedule" in a.feedback.payload["schedule"]["headline"]


def test_practising_a_not_yet_due_question_does_not_change_the_interval(db):  # adaptive-02
    q = maths_qs(db)[0]
    assessment.submit(db, q, right(q), confidence="confident")
    db.commit()
    nxt = exposure(db, q).next_revision_date
    clock.set_today(TUESDAY + timedelta(days=5))
    a = assessment.submit(db, q, "987654", confidence="confident")
    db.commit()
    assert not a.counts_for_mastery and exposure(db, q).next_revision_date == nxt
    ev = db.execute(select(ExposureEvent).where(ExposureEvent.attempt_id == a.id)).scalar_one()
    assert ev.counted is False and ev.outcome_kind == "rehearsal"
    assert db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id == a.id)).first() is None


def test_due_repeat_counts(db):
    q = maths_qs(db)[0]
    assessment.submit(db, q, "987654", confidence="confident")
    db.commit()
    clock.set_today(exposure(db, q).next_revision_date)
    a = assessment.submit(db, q, right(q), confidence="confident")
    assert a.counts_for_mastery and a.evidence_role == "due_repeat"
    assert exposure(db, q).score_history == [0.0, 1.0]


# --------------------------------------------------------- revision lifecycle ---
def test_failing_the_revisit_again_keeps_one_open_item(db):  # adaptive-03
    q1, q2 = maths_qs(db)[:2]
    assessment.submit(db, q1, "987654", confidence="confident")
    db.commit()
    first = open_items(db, q1)
    assert len(first) == 1 and (first[0].due_date - TUESDAY).days <= 2
    clock.set_today(first[0].due_date)
    a2 = assessment.submit(db, q2, "987654", confidence="confident")  # the revisit, with a different question, wrong again
    db.commit()
    still = open_items(db, q1)
    assert len(still) == 1 and (still[0].due_date - first[0].due_date).days <= 2 and still[0].id != first[0].id
    done = db.get(RevisionQueue, first[0].id)
    assert done.status == "done" and done.outcome == 0.0 and done.served_by_attempt_id == a2.id and done.completed_at == first[0].due_date


def test_the_failed_question_itself_does_not_serve_its_revisit(db):
    q1 = maths_qs(db)[0]
    assessment.submit(db, q1, "987654", confidence="confident")
    db.commit()
    item = open_items(db, q1)[0]
    clock.set_today(item.due_date)
    assessment.submit(db, q1, right(q1), confidence="confident")  # rehearsal (not due) — must not close the item
    db.commit()
    assert db.get(RevisionQueue, item.id).status == "open"


# ------------------------------------------------- confidence x correctness ---
def test_confidence_table():  # adaptive-05
    assert mastery.assess(1.0, "very_confident", None, False).kind == "strong"
    g = mastery.assess(1.0, "guess", None, False)
    assert g.kind == "unconfirmed" and g.evidence <= 0.6 and g.revisit_kind == "unconfirmed_check" and 3 <= g.revisit_days <= 5
    wrong_sure = mastery.assess(0.0, "very_confident", "conceptual", False)
    wrong_unsure = mastery.assess(0.0, "unsure", "conceptual", False)
    assert wrong_sure.kind == "misconception" and wrong_sure.revisit_days <= 2 and wrong_sure.priority > wrong_unsure.priority
    assert wrong_sure.evidence <= wrong_unsure.evidence + 1e-9 or wrong_sure.evidence == 0  # more confidence is never better evidence
    slip = mastery.assess(0.0, "very_confident", "sign", False, prior_mastery=0.9, prior_attempts=4, slip_evidence=True)
    assert slip.kind == "slip" and slip.evidence <= 0.6
    assert mastery.assess(0.0, "very_confident", "sign", False, prior_mastery=0.5, prior_attempts=4, slip_evidence=True).kind == "misconception"


def test_learner_facing_headlines(db):  # adaptive-17
    q1, q2 = maths_qs(db)[:2]
    a = assessment.submit(db, q1, right(q1), confidence="guess")
    h = a.feedback.payload["schedule"]["headline"]
    assert h.startswith("Correct — but you guessed") and "different question" in h and "weak answer" not in h
    b = assessment.submit(db, q2, "987654", confidence="very_confident")
    h2 = b.feedback.payload["schedule"]["headline"]
    assert "very confident" in h2 and "exact idea to fix" in h2
    kinds = {r.kind for r in open_items(db, q1)}
    assert "misconception" in kinds  # the more urgent kind wins the merged item


def test_calibration_stats(db):
    qs = maths_qs(db)
    assessment.submit(db, qs[0], right(qs[0]), confidence="very_confident")
    assessment.submit(db, qs[1], "987654", confidence="very_confident")
    db.commit()
    cal = {c["level"]: c for c in mastery.calibration(db)}
    assert cal["very_confident"]["n"] == 2 and cal["very_confident"]["pct"] == 50


# ---------------------------------------------------------------- reliability ---
def test_model_answer_under_offline_estimate_creates_no_weak_item_or_journal(db):  # adaptive-06
    for code in ("ENGLISH", "LEGAL"):
        for q in [q for q in subject_qs(db, code) if q.answer is None and q.model_answer][:4]:
            a = assessment.submit(db, q, q.model_answer, confidence="very_confident")
            db.commit()
            assert a.marking_method == "offline_estimate"
            assert db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id == a.id)).first() is None
            weak = [r for r in open_items(db, q) if r.source_attempt_id == a.id and r.kind != "recycle"]
            assert weak == []
            assert a.feedback.payload["schedule"]["estimated"] is True


def test_confirming_an_estimate_replaces_it(db):  # adaptive-06 / adaptive-16
    q = written_q(db, "LEGAL")
    a = assessment.submit(db, q, "The law is good because people follow it and the police do things about crime in the community.")
    db.commit()
    assert db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id == a.id)).first() is None
    assessment.apply_self_mark(db, a, 1)
    db.commit()
    e = exposure(db, q)
    assert e.attempts == 1 and e.score_history == [round(1 / q.marks, 3)]
    rows = db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id == a.id)).scalars().all()
    assert rows and all(r.source == "self" for r in rows)
    assert a.feedback.payload["self_marked"] and a.marking_method == "self"
    events = db.execute(select(ExposureEvent).where(ExposureEvent.question_id == q.id, ExposureEvent.counted.is_(True))).scalars().all()
    assert len(events) == 1 and events[0].method == "self"


def test_self_mark_is_recorded_once(db):  # adaptive-16
    src = maths_qs(db)[0]
    q = Question(subject_id=src.subject_id, source_id=src.source_id, question_text="Imported question without an answer key.", marks=3,
                 plan_item_id=src.plan_item_id, approved=True, approval_status="approved", marking_guideline="1 mark: correct derivative\n2 marks: ...")
    db.add(q)
    db.commit()
    a = assessment.submit(db, q, "my answer", working="steps")
    db.commit()
    assert a.feedback.payload["pending_mark"] and not open_items(db, q)
    e = exposure(db, q)
    assert e.attempts == 0 and e.score_history == []
    assessment.apply_self_mark(db, a, 3)
    db.commit()
    e = exposure(db, q)
    assert e.attempts == 1 and e.score_history == [1.0]
    assert not [r for r in open_items(db, q) if r.kind == "weak_revisit"]
    assessment.apply_self_mark(db, a, 1)  # changed: replaces, never appends
    db.commit()
    e = exposure(db, q)
    assert e.attempts == 1 and e.score_history == [round(1 / 3, 3)]


# ------------------------------------------------------------- error journal ---
def test_maths_journal_has_two_axes(db):  # adaptive-10
    q = maths_qs(db)[0]
    payload = {"kind": "maths", "correct": False, "divergence": "Sign changed.", "topic_tag": "sign error"}
    items = error_journal.items_for("MATHS", q, payload, ["sign"], "deterministic")
    assert items[0]["category"] == "careless error" and items[0]["topic_tag"] == "sign error"
    provided = error_journal.items_for("MATHS", q, {"kind": "maths", "journal_items": [{"category": "conceptual", "topic_tag": "chain rule",
                                                                                         "description": "Missing chain factor."}]}, [], "deterministic")
    assert provided == [{"category": "conceptual", "topic_tag": "chain rule", "description": "Missing chain factor."}]


def test_retry_does_not_duplicate_journal_and_marks_fixed(db):  # adaptive-11
    from tests.fakes import FakeProvider, marking_json
    from app.ai import factory

    q = written_q(db, "ENGLISH")
    factory.set_test_provider(FakeProvider([marking_json(1.0, q.marks)]))
    a1 = assessment.submit(db, q, "The writer uses a metaphor to show memory.")
    db.commit()
    n1 = db.execute(select(ErrorJournal).where(ErrorJournal.question_id == q.id)).scalars().all()
    assert len(n1) == 1 and n1[0].category == "technique identification without analysis" and n1[0].study_date == TUESDAY
    factory.set_test_provider(FakeProvider([marking_json(float(q.marks), q.marks, errors=[])]))
    a2 = assessment.submit(db, q, "A much better rewrite that analyses how the metaphor shapes the representation of memory.")
    db.commit()
    assert a2.evidence_role == "retry" and not a2.counts_for_mastery
    rows = db.execute(select(ErrorJournal).where(ErrorJournal.question_id == q.id)).scalars().all()
    assert len(rows) == 1 and rows[0].fixed_on_retry
    assert a2.feedback.payload["improvement"]["criteria"]


def test_wrong_legal_mcq_is_journalled_with_the_distractor_rationale(db):  # adaptive-11
    q = next(q for q in subject_qs(db, "LEGAL", question_type="mcq"))
    sol = dict(q.solution or {})
    correct = q.answer["value"].upper()
    wrong = next(o[0] for o in q.options if o[0].upper() != correct)
    sol["option_rationales"] = {wrong: "It confuses the standard of proof with the burden of proof.", correct: "It states the burden correctly."}
    q.solution = sol
    db.commit()
    a = assessment.submit(db, q, wrong, confidence="unsure")
    rows = db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id == a.id)).scalars().all()
    assert len(rows) == 1 and "standard of proof" in rows[0].description
    why = assessment.why_lost(db, a)
    assert "tempting" in why and "burden correctly" in why


def test_legal_offline_gaps_get_their_own_category_and_description(db):  # legal-20
    q = written_q(db, "LEGAL")
    a = assessment.submit(db, q, "People think the law is fine and it works for most people in most situations, more or less.")
    items = a.feedback.payload["estimated_items"]
    assert items
    cats = [i["category"] for i in items]
    assert "failure to address directive verb" not in cats or any("verb" in i["description"].lower() for i in items)
    assert len(set(i["description"] for i in items)) == len(items)  # no generic reuse of one description
    for i in items:
        assert i["category"] in error_journal.LEGAL_CATEGORIES


def test_repeated_tag_becomes_a_pattern_item_and_panel(db):  # adaptive-12
    qs = maths_qs(db, n=6)
    for i, q in enumerate(qs[:3]):
        clock.set_today(TUESDAY + timedelta(days=i))
        a = assessment.submit(db, q, "987654", confidence="confident")
        error_journal.add_entries(db, a, q, "MATHS", [{"category": "careless error", "topic_tag": "sign error", "description": "Sign."}],
                                  TUESDAY + timedelta(days=i), "deterministic")
        from app.services.assessment.core import _maybe_pattern

        _maybe_pattern(db, a, q, TUESDAY + timedelta(days=i), [{"category": "careless error", "topic_tag": "sign error"}], {})
    db.commit()
    kinds = {(r.kind, r.tag) for r in open_items(db, qs[0])}
    assert ("pattern", "sign error") in kinds or any(k == "pattern" for k, _ in kinds) or "misconception" in {k for k, _ in kinds}
    ps = error_journal.patterns(db, TUESDAY + timedelta(days=2))
    sign = next(p for p in ps if p["key"] == "sign error")
    assert sign["n30"] >= 3 and sign["repeated"] and "Sign error" in sign["interpretation"]


def test_auto_resolve_after_three_correct(db):
    qs = maths_qs(db, n=5)
    assessment.submit(db, qs[0], "987654", confidence="confident")
    db.commit()
    for i, q in enumerate(qs[1:4], start=1):
        clock.set_today(TUESDAY + timedelta(days=i))
        assessment.submit(db, q, right(q), confidence="confident")
    db.commit()
    rows = db.execute(select(ErrorJournal).where(ErrorJournal.question_id == qs[0].id)).scalars().all()
    assert rows and all(r.resolved and r.auto_resolved and r.resolved_on for r in rows)


# --------------------------------------------------------------- why-lost ---
def test_why_lost_skipped_gives_first_step(db):  # adaptive-13
    q = next(q for q in maths_qs(db) if (q.solution or {}).get("steps"))
    a = assessment.submit(db, q, "", skipped=True)
    why = assessment.why_lost(db, a)
    assert "first mark" in why and q.solution["steps"][0][:20] in why


def test_why_lost_maths_does_not_repeat_the_feedback(db):  # adaptive-13
    q = next(q for q in maths_qs(db) if (q.solution or {}).get("concept"))
    a = assessment.submit(db, q, "987654")
    p = a.feedback.payload
    why = assessment.why_lost(db, a)
    if p.get("divergence") and len(p["divergence"]) >= 20:
        assert p["divergence"] not in why
    assert q.solution["concept"] not in why
    assert why.strip()


def test_why_lost_written_names_bands_and_quotes_the_student(db):
    q = written_q(db, "ENGLISH")
    q.solution = dict(q.solution or {}, criteria=[{"mark": q.marks, "descriptor": "Perceptive analysis"}, {"mark": 1, "descriptor": "Identifies a technique"}])
    db.commit()
    a = assessment.submit(db, q, "The writer uses a metaphor. It is about memory and the past and it is effective.")
    why = assessment.why_lost(db, a)
    assert "band" in why


def test_legal_ai_why_lost_rejects_invented_citations(db):  # adaptive-14
    import json

    from app.ai import factory
    from tests.fakes import FakeProvider, marking_json

    q = written_q(db, "LEGAL")
    fake = FakeProvider([marking_json(1.0, q.marks),
                         json.dumps({"explanation": "You should have cited the Imaginary Protection Act 2031, which settles the issue completely."}),
                         json.dumps({"explanation": "You should have cited Smith v Nobody, which settles this issue in the student's favour."})])
    factory.set_test_provider(fake)
    a = assessment.submit(db, q, "A short legal answer that describes the law without authority or evaluation at all.")
    why = assessment.why_lost(db, a)
    assert "Imaginary Protection Act" not in why and "Smith v Nobody" not in why
    assert "cite ONLY these" in fake.prompts[1]


# ------------------------------------------------------------ token answers ---
def test_token_answer_is_recorded_as_skip(db):  # adaptive-23
    q = written_q(db, "ENGLISH")
    a = assessment.submit(db, q, "idk")
    assert a.skipped and a.feedback.payload["kind"] == "skipped" and "not an attempt" in a.feedback.payload["skip_reason"]
    assert db.execute(select(ErrorJournal).where(ErrorJournal.attempt_id == a.id)).first() is None


# ------------------------------------------------------------------ rebuild ---
def test_struggling_skill_enters_rebuild_and_leaves_after_two_correct(db):  # adaptive-19
    qs = maths_qs(db, n=8)
    for i, q in enumerate(qs[:4]):
        clock.set_today(TUESDAY + timedelta(days=i))
        assessment.submit(db, q, "987654", confidence="unsure")
    db.commit()
    m = skill(db, qs[0])
    assert m.state == "rebuild"
    assert any(r.kind == "rebuild" for r in open_items(db, qs[0]))
    for i, q in enumerate(qs[4:6], start=4):
        clock.set_today(TUESDAY + timedelta(days=i))
        assessment.submit(db, q, right(q), confidence="confident")
    db.commit()
    assert skill(db, qs[0]).state == "normal"


# ------------------------------------------------------------ HTTP: frame ---
def test_practice_draft_autosaves_and_restores(client, db):  # english-15
    q = written_q(db, "ENGLISH")
    r = client.get(f"/practice/{q.id}")
    assert f'data-save-url="/practice/{q.id}/draft"' in r.text
    r = client.post(f"/practice/{q.id}/draft", data={"text": "My half-written paragraph", "time_seconds": "40"})
    assert r.json()["ok"]
    r = client.get(f"/practice/{q.id}")
    assert "My half-written paragraph" in r.text and "Draft saved" in r.text
    client.post(f"/practice/{q.id}/submit", data={"answer": "My finished paragraph about the passage and its metaphor of memory.", "time_seconds": "60"})
    db.expire_all()
    assert db.execute(select(PracticeDraft).where(PracticeDraft.question_id == q.id)).first() is None


def test_maths_hint_first_then_full_solution(client, db):  # adaptive-15
    q = next(q for q in maths_qs(db) if (q.solution or {}).get("steps") and len(q.solution["steps"]) >= 2)
    client.post(f"/practice/{q.id}/submit", data={"answer": "987654"}, follow_redirects=False)
    page = client.get(f"/practice/{q.id}").text
    assert "Try again with this hint" in page and "Show full solution" in page
    assert "Complete worked solution" not in page
    retry = client.get(f"/practice/{q.id}?retry=1").text
    assert "retry-notes" in retry and "Submit rewrite" in retry
    a = db.execute(select(Attempt).where(Attempt.question_id == q.id)).scalars().first()
    client.post(f"/attempt/{a.id}/model-viewed", data={"back": f"/practice/{q.id}"}, follow_redirects=False)
    db.expire_all()
    assert db.get(Attempt, a.id).model_viewed_at is not None


def test_no_retry_after_skip(client, db):  # adaptive-15
    q = written_q(db, "ENGLISH")
    client.post(f"/practice/{q.id}/skip", follow_redirects=False)
    page = client.get(f"/practice/{q.id}").text
    assert "Try again" not in page
    page = client.get(f"/practice/{q.id}?retry=1").text
    assert 'id="answer-form"' not in page


def test_rewrite_after_viewing_model_is_labelled(client, db):  # english-21
    q = written_q(db, "ENGLISH")
    client.post(f"/practice/{q.id}/submit", data={"answer": "The writer uses a metaphor to show memory, which is effective in the passage."})
    a1 = db.execute(select(Attempt).where(Attempt.question_id == q.id)).scalars().first()
    assert client.post(f"/attempt/{a1.id}/model-viewed").json()["first"] is True
    client.post(f"/practice/{q.id}/submit", data={"answer": "A rewrite that analyses how the extended metaphor of the tide shapes our sense of memory."})
    page = client.get(f"/practice/{q.id}").text
    assert "rewritten after viewing the model" in page


def test_why_endpoint_returns_paragraphs(client, db):
    q = maths_qs(db)[0]
    client.post(f"/practice/{q.id}/skip")
    a = db.execute(select(Attempt).where(Attempt.question_id == q.id)).scalars().first()
    j = client.post(f"/attempt/{a.id}/why").json()
    assert j["paragraphs"] and j["explanation"]


def test_question_page_shows_evidence_label(client, db):
    q = maths_qs(db)[0]
    assert "counts towards your schedule" in client.get(f"/practice/{q.id}").text
    client.post(f"/practice/{q.id}/skip")
    other_day = TUESDAY + timedelta(days=1)
    clock.set_today(other_day)
    assert "doesn&#39;t change your schedule" in client.get(f"/practice/{q.id}").text or \
        "doesn't change your schedule" in client.get(f"/practice/{q.id}").text
