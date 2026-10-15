"""seed_english loads v1 questions plus the v2 reading sets and course/Craft task files (english-logic)."""
import json

from sqlalchemy import select

from app.models import Question, Stimulus, Subject
from app.services import english_guided as eg
from app.services.seed import seed_english

LADDER4 = [{"mark": 4, "descriptor": "Perceptive analysis"}, {"mark": 3, "descriptor": "Clear analysis"},
           {"mark": 2, "descriptor": "Some explanation"}, {"mark": 1, "descriptor": "Identifies a feature"}]

SETS = {"sets": [
    {"key": "fixture-gull", "title": "Fixture: The Gull", "form": "Prose fiction", "complexity": 2, "author": "Original text (HSC Companion)",
     "headnote": "An extract from an original story.", "theme_tags": ["memory"], "length_words": 30,
     "body": "The gull stood on one leg on the rail, patient as a clerk.\n\nMy father said nothing all the way across the bay.",
     "pair": None,
     "questions": [
         {"marks": 2, "verb": "Explain", "demand": "explain", "text": "Fixture: explain what the simile suggests about the gull.",
          "skill_tags": ["imagery"], "criteria": LADDER4[2:], "checklist": ["Quotes 'patient as a clerk'", "Explains the effect"],
          "next_steps": {"0": "Find the simile.", "1": "Say what it suggests."},
          "model": "The simile 'patient as a clerk' makes the gull seem dutiful and resigned.", "difficulty": 1},
         {"marks": 4, "verb": "Analyse", "demand": "analyse", "text": "Fixture: analyse how silence is represented.",
          "skill_tags": ["perspective"], "criteria": LADDER4, "checklist": ["a", "b", "c", "d"], "next_steps": {"0": "x"},
          "model": "The father 'said nothing all the way across the harbour', so silence fills the journey.", "difficulty": 2},
     ]},
    {"key": "fixture-pair", "title": "Fixture: Tide Tables", "form": "Memoir", "complexity": 1, "author": "Original text (HSC Companion)",
     "headnote": "", "theme_tags": [], "length_words": 12, "body": "Every morning my grandmother read the tide tables aloud.",
     "pair": {"title": "Fixture: Low Water", "form": "Poetry", "author": "Original text (HSC Companion)", "headnote": "",
              "body": "Low water,\nand the boats lie down\nlike tired dogs"},
     "questions": [
         {"marks": 3, "verb": "Explain", "demand": "explain", "text": "In Text 1, explain the grandmother's ritual.", "skill_tags": [],
          "criteria": LADDER4[1:], "checklist": ["x"], "next_steps": {}, "model": "She 'read the tide tables aloud' every morning.", "difficulty": 1},
         {"marks": 4, "verb": "Analyse", "demand": "analyse", "text": "Analyse the simile in Text 2.", "skill_tags": [],
          "criteria": LADDER4, "checklist": ["x"], "next_steps": {}, "model": "The boats 'lie down / like tired dogs'.", "difficulty": 2},
         {"marks": 6, "verb": "Compare", "demand": "compare", "text": "Compare how Text 1 and Text 2 represent the sea.", "skill_tags": [],
          "criteria": [{"mark": m, "descriptor": f"level {m}"} for m in range(6, 0, -1)], "checklist": ["x"], "next_steps": {},
          "model": "Text 1's 'tide tables' and Text 2's 'Low water' both measure the sea.", "difficulty": 3},
     ]},
]}

COURSE = {"questions": [
    {"module": "EN-CRAFT", "marks": 6, "verb": "Compose", "demand": "synthesise", "response_type": "imaginative",
     "text": "Fixture: compose the opening of a story set in a lift (300 to 400 words).", "skill_tags": ["structure"],
     "criteria": [{"mark": m, "descriptor": f"craft level {m}"} for m in range(6, 0, -1)], "checklist": ["Shows not tells", "Controls tense"],
     "next_steps": {"0": "Decide the withheld fact."}, "plan": "Open in the lift; withhold the reason; turn in the last line.",
     "suggested_words": [300, 400], "difficulty": 2},
    {"module": "EN-THE", "marks": 4, "verb": "Explain", "demand": "explain", "response_type": "analytical",
     "text": "Fixture: explain how setting shapes a relationship in your prescribed text.", "skill_tags": ["setting"],
     "criteria": LADDER4, "checklist": ["Makes a claim"], "next_steps": {}, "plan": "Thesis: ...", "suggested_words": [180, 260], "difficulty": 2},
]}


def _write(tmp_path, sets=SETS, course=COURSE):
    (tmp_path / "english_sets.json").write_text(json.dumps(sets), encoding="utf-8")
    (tmp_path / "english_course.json").write_text(json.dumps(course), encoding="utf-8")
    return tmp_path


def _q(db, text):
    return db.execute(select(Question).where(Question.question_text == text)).scalar_one()


def test_loads_sets_pairs_and_course_tasks(db, tmp_path):
    counts = seed_english(db, seed_dir=_write(tmp_path))
    assert counts["questions"] == 7 and counts["stimuli"] == 3

    q = _q(db, "Fixture: explain what the simile suggests about the gull.")
    assert q.category == "unseen" and q.stimulus.title == "Fixture: The Gull"
    assert q.model_answer.startswith("The simile") and not q.guideline_official
    sol = q.solution
    assert sol["checklist"][0].startswith("Quotes") and sol["demand"] == "explain" and sol["skill_tags"] == ["imagery"]
    assert sol["criteria"][0] == {"mark": 2, "descriptor": "Some explanation"} and sol["next_steps"]["1"] == "Say what it suggests."
    assert sol["model_source"] == "app_authored" and sol["model_status"] == "vetted" and sol["text_complexity"] == 2
    assert q.marking_guideline.splitlines()[0] == "2 marks: Some explanation"
    assert q.stimulus.headnote == "An extract from an original story." and q.stimulus.complexity == 2
    assert q.stimulus.meta["key"] == "fixture-gull"

    m = eg.meta(q)
    assert m["ladder"][0]["mark"] == 2 and m["checklist_authored"] and not m["paired"]


def test_paired_sets_scope_each_question_to_its_text(db, tmp_path):
    seed_english(db, seed_dir=_write(tmp_path))
    t1 = _q(db, "In Text 1, explain the grandmother's ritual.")
    t2 = _q(db, "Analyse the simile in Text 2.")
    both = _q(db, "Compare how Text 1 and Text 2 represent the sea.")
    assert [s.title for s in both.stimulus.reading_set()] == ["Fixture: Tide Tables", "Fixture: Low Water"]
    assert t1.solution["texts"] == [0] and t2.solution["texts"] == [1] and both.solution["texts"] == [0, 1]
    assert eg.meta(both)["paired"] and not eg.meta(t1)["paired"]
    assert both.stimulus.reading_set()[1].form == "Poetry"


def test_misquoted_model_is_never_marked_vetted(db, tmp_path):
    seed_english(db, seed_dir=_write(tmp_path))
    q = _q(db, "Fixture: analyse how silence is represented.")  # model says 'harbour'; the passage says 'bay'
    assert q.solution["model_status"] == "quotes_unverified"


def test_course_and_craft_tasks(db, tmp_path):
    seed_english(db, seed_dir=_write(tmp_path))
    craft = _q(db, "Fixture: compose the opening of a story set in a lift (300 to 400 words).")
    assert craft.category == "course" and craft.model_answer is None and craft.stimulus_id is None
    assert craft.solution["response_type"] == "imaginative" and craft.solution["plan"].startswith("Open in the lift")
    assert craft.solution["model_source"] == "app_authored_plan" and craft.solution["module"] == "EN-CRAFT"
    assert craft.estimated_minutes == 23  # 400 words at ~20 words/min + 3 min planning (english-04)
    assert eg.meta(craft)["craft"] and eg.meta(craft)["suggested_words"] == [300, 400]
    the = _q(db, "Fixture: explain how setting shapes a relationship in your prescribed text.")
    assert the.estimated_minutes == 7.5 and not eg.meta(the)["craft"]


def test_reseeding_is_idempotent_and_refreshes_authored_data(db, tmp_path):
    seed_english(db, seed_dir=_write(tmp_path))
    assert seed_english(db, seed_dir=tmp_path) == {"stimuli": 0, "questions": 0, "updated": 0}
    changed = json.loads(json.dumps(SETS))
    changed["sets"][0]["questions"][0]["checklist"] = ["Quotes 'patient as a clerk' exactly", "Explains the effect"]
    counts = seed_english(db, seed_dir=_write(tmp_path, sets=changed))
    assert counts == {"stimuli": 0, "questions": 0, "updated": 1}
    assert _q(db, "Fixture: explain what the simile suggests about the gull.").solution["checklist"][0].endswith("exactly")


def test_every_seeded_english_question_has_marking_data(db):
    eng = db.execute(select(Subject).where(Subject.code == "ENGLISH")).scalar_one()
    qs = db.execute(select(Question).where(Question.subject_id == eng.id)).scalars().all()
    assert len(qs) >= 20
    for q in qs:
        m = eg.meta(q)
        assert m["ladder"] and m["checklist"] and m["checklist_authored"], q.question_text
        assert m["ladder"][0]["mark"] == q.marks, q.question_text
        assert all(str(k) in m["next_steps"] for k in range(q.marks)), q.question_text
    stims = db.execute(select(Stimulus).where(Stimulus.subject_id == eng.id)).scalars().all()
    for s in stims:  # app-written texts say so; real texts are credited to their authors as public-domain
        assert s.attribution and ("Original text" in s.attribution if s.provenance == "generated_original"
                                  else s.provenance == "public_domain" and "Public-domain text" in s.attribution)


def test_at_most_ten_percent_of_served_passages_are_ai_written(data_dir, monkeypatch):
    """Owner request: real public-domain texts; AI-written passages at most 10% of those served."""
    from app.database_setup import prepare_database
    from app.db import SessionLocal
    from app.services import seed as seed_mod

    monkeypatch.setattr(seed_mod, "RETIRE_AI", True)
    prepare_database(f"sqlite:///{data_dir / 'r.db'}")
    s = SessionLocal()
    eng = s.execute(select(Subject).where(Subject.code == "ENGLISH")).scalar_one()
    served = {}
    for q in s.execute(select(Question).where(Question.subject_id == eng.id, Question.approved.is_(True),
                                              Question.stimulus_id.is_not(None))).scalars():
        served[q.stimulus_id] = q.stimulus.provenance
    ai = sum(1 for p in served.values() if p != "public_domain")
    assert len(served) >= 25 and ai / len(served) <= 0.10
    s.close()
