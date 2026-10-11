"""Content checks for the v2 Legal bank: data/seed/legal_v2.json and data/seed/legal_evidence_v2.json.

These tests read the JSON files only (no database), so they guard the content whatever loader is used.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

SEED = Path(__file__).resolve().parent.parent / "data" / "seed"

SUB_AREAS = {
    "LS-CRIME": {"LS-CRIME-NATURE", "LS-CRIME-INVESTIGATION", "LS-CRIME-TRIAL", "LS-CRIME-SENTENCING",
                 "LS-CRIME-YOUNG", "LS-CRIME-INTERNATIONAL"},
    "LS-HR": {"LS-HR-NATURE", "LS-HR-ENFORCE", "LS-HR-ISSUE"},
}
ALL_SUB = set().union(*SUB_AREAS.values())
STIM_KINDS = {"hypothetical scenario", "statistics table (hypothetical)", "extract"}
EV_STATUS = {"in_force", "repealed", "amended", "superseded", "unknown"}
EV_TYPES = {"legislation", "case", "law_reform", "report", "inquiry", "treaty", "media", "issue", "institution"}


def _load(name):
    return json.loads((SEED / name).read_text(encoding="utf-8"))


QUESTIONS = _load("legal_v2.json")["questions"]
V1_EVIDENCE = _load("legal_evidence.json")["items"]
V2_EVIDENCE = _load("legal_evidence_v2.json")["items"]
BANK = {i["title"]: i for i in V1_EVIDENCE + V2_EVIDENCE}
WRITTEN = [q for q in QUESTIONS if q["type"] != "mcq"]
MCQS = [q for q in QUESTIONS if q["type"] == "mcq"]


def _qid(q):
    return f"{q['type']}:{q['sub_area']}:{q['text'][:40]}"


def _cited_text(q) -> str:
    parts = [q["text"], q.get("model") or "", q.get("explanation") or "", q.get("model_note") or ""]
    parts += [o for o in q.get("options") or []]
    parts += list((q.get("option_rationales") or {}).values())
    parts += [c["descriptor"] for c in q.get("criteria") or []]
    parts += q.get("required_elements") or []
    return "\n".join(parts)


# ------------------------------------------------------------------------------------------ targets
def test_targets_from_v2_plan():
    by_type = Counter(q["type"] for q in QUESTIONS)
    assert by_type["mcq"] >= 24
    assert by_type["short_answer"] >= 16
    assert by_type["stimulus"] >= 8
    assert by_type["extended"] >= 4
    assert len(V2_EVIDENCE) >= 15


def test_every_sub_area_is_covered_evenly():
    by_sub = Counter(q["sub_area"] for q in QUESTIONS)
    assert set(by_sub) == ALL_SUB
    assert min(by_sub.values()) >= 6
    mcq_by_sub = Counter(q["sub_area"] for q in MCQS)
    assert set(mcq_by_sub) == ALL_SUB and min(mcq_by_sub.values()) >= 3


def test_short_answers_span_verb_tiers_and_marks():
    shorts = [q for q in QUESTIONS if q["type"] == "short_answer"]
    verbs = {q["verb"] for q in shorts}
    assert verbs & {"Identify", "Outline", "Describe"}
    assert verbs & {"Explain", "Distinguish"}
    assert verbs & {"Analyse", "Discuss"}
    assert verbs & {"Assess", "Evaluate"}
    marks = {q["marks"] for q in shorts}
    assert min(marks) >= 2 and max(marks) <= 8 and len(marks) >= 5


# ------------------------------------------------------------------------------------------ schema
@pytest.mark.parametrize("q", QUESTIONS, ids=_qid)
def test_question_schema(q):
    assert q["topic"] in SUB_AREAS and q["sub_area"] in SUB_AREAS[q["topic"]]
    assert q["type"] in {"mcq", "short_answer", "stimulus", "extended"}
    assert q["difficulty"] in (1, 2, 3)
    assert q["legal_fact_currency"] in ("current", "check")
    if q["legal_fact_currency"] == "check":
        assert "verify" in q["currency_note"].lower()
    assert isinstance(q["evidence_titles"], list)
    assert len(set(q["evidence_titles"])) == len(q["evidence_titles"])


def test_question_texts_are_unique_and_not_v1_duplicates():
    texts = [q["text"].strip().lower() for q in QUESTIONS]
    assert len(texts) == len(set(texts))
    v1 = {q["text"].strip().lower() for q in _load("questions_legal.json")["questions"]}
    assert not set(texts) & v1


@pytest.mark.parametrize("q", MCQS, ids=_qid)
def test_mcq_answer_options_and_rationales_agree(q):
    assert q["marks"] == 1 and q["verb"] is None
    assert [o[:3] for o in q["options"]] == ["A. ", "B. ", "C. ", "D. "]
    assert len({o[3:].lower() for o in q["options"]}) == 4
    assert q["answer"] in "ABCD"
    assert set(q["option_rationales"]) == set("ABCD")
    assert all(len(r) >= 40 for r in q["option_rationales"].values())
    assert not q["option_rationales"][q["answer"]].lower().startswith(("tempting", "incorrect", "wrong"))
    assert q.get("explanation")
    assert not q.get("model") and not q.get("criteria") and not q.get("stimulus")


def test_mcq_answers_are_balanced():
    counts = Counter(q["answer"] for q in MCQS)
    assert set(counts) == set("ABCD")
    assert max(counts.values()) - min(counts.values()) <= 2


@pytest.mark.parametrize("q", WRITTEN, ids=_qid)
def test_written_marks_criteria_and_model(q):
    assert q["verb"] and q["verb"].lower() in q["text"].lower()
    lo, hi = {"short_answer": (2, 8), "stimulus": (3, 10), "extended": (15, 15)}[q["type"]]
    assert lo <= q["marks"] <= hi
    crit = q["criteria"]
    assert crit[0]["mark"] == q["marks"]
    covered = []
    for prev, row in zip([None] + crit[:-1], crit):
        if prev is not None:
            assert row["mark"] < prev["mark"]
        if "range" in row:
            a, b = (int(x) for x in re.split(r"[–-]", row["range"]))
            assert b == row["mark"]
            covered += list(range(a, b + 1))
        else:
            covered.append(row["mark"])
    assert sorted(covered) == list(range(1, q["marks"] + 1))
    assert len(q["required_elements"]) >= 2
    words = len(q["model"].split())
    if q["type"] == "extended":
        assert 750 <= words <= 1700
        assert len(q["evidence_titles"]) >= 5
    else:
        assert max(40, 22 * q["marks"]) <= words <= max(160, 75 * q["marks"])
    if q["marks"] >= 4:
        assert q["evidence_titles"], "a model worth 4+ marks should cite at least one bank item"


@pytest.mark.parametrize("q", [q for q in QUESTIONS if q["type"] == "stimulus"], ids=_qid)
def test_stimulus_is_labelled_hypothetical(q):
    st = q["stimulus"]
    assert "hypothetical" in st["title"].lower()
    assert st["kind"] in STIM_KINDS and st["kind"] != "extract"
    body = st["body"].lower()
    assert "invented" in body or "fictional" in body
    if st["kind"] == "statistics table (hypothetical)":
        assert "invented" in body and "must not be quoted as real" in body
    assert re.search(r"stimulus|scenario|data|table", q["text"], re.I)
    for t in st["evidence_titles"]:
        assert t in BANK


# ------------------------------------------------------------------------------------------ citations
@pytest.mark.parametrize("q", QUESTIONS, ids=_qid)
def test_cited_titles_exist_in_bank_and_appear_verbatim(q):
    text = _cited_text(q)
    for t in q["evidence_titles"]:
        assert t in BANK, f"not in evidence bank: {t}"
        assert t in text, f"listed but never cited by exact title: {t}"


@pytest.mark.parametrize("q", QUESTIONS, ids=_qid)
def test_every_bank_item_mentioned_is_listed(q):
    text = _cited_text(q)
    for title, item in BANK.items():
        names = [title] + [a for a in item.get("aliases", []) if len(a) > 4]
        if any(re.search(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])", text) for n in names):
            # A title that is a substring of a longer cited title (ICCPR inside its Optional Protocol) is fine.
            if title not in q["evidence_titles"]:
                longer = [t for t in q["evidence_titles"] if title in t or any(n in t for n in names)]
                assert longer, f"mentions {title!r} but it is not in evidence_titles"


CASE_RE = re.compile(r"\b[A-Z][\w'’.-]+(?:\s+[A-Z(][\w'’.()-]*)*\s+v\s+(?:The\s+)?[A-Z][\w'’.-]+")


@pytest.mark.parametrize("q", QUESTIONS, ids=_qid)
def test_no_case_names_outside_the_bank(q):
    text = _cited_text(q) + "\n" + ((q.get("stimulus") or {}).get("body") or "")
    names = []
    for title, item in BANK.items():
        names += [title] + item.get("aliases", [])
        if item["item_type"] == "case":  # the party names without the citation, e.g. 'RP v The Queen'
            names.append(re.split(r" [(\[]", title)[0])
    for n in sorted(names, key=len, reverse=True):
        text = text.replace(n, "#")
    assert not CASE_RE.findall(text)


@pytest.mark.parametrize("q", WRITTEN, ids=_qid)
def test_models_have_no_editor_notes_or_unsourced_statistics(q):
    model = q["model"]
    assert not re.search(r"\[(?:Check|Add|Support|Verify|Insert)", model, re.I)
    assert not re.search(r"\b(?:TODO|Note:|NB:)", model)
    assert not re.search(r"\d\s*%|per cent|percent", model)
    assert not re.search(r"\b(?:research shows|studies show|statistics show)\b", model, re.I)


def test_superseded_items_are_flagged_where_cited():
    for q in QUESTIONS:
        superseded = [t for t in q["evidence_titles"] if BANK[t].get("status") in ("superseded", "repealed")]
        if superseded:
            assert q["legal_fact_currency"] == "check"
            assert re.search(r"overrul|repeal|supersed|no longer", _cited_text(q), re.I)


# ------------------------------------------------------------------------------------------ evidence
@pytest.mark.parametrize("item", V2_EVIDENCE, ids=lambda i: i["title"][:50])
def test_evidence_item_schema_and_unverified(item):
    for key in ("title", "item_type", "date", "jurisdiction", "topics", "issue", "summary", "legal_significance",
                "source", "source_url", "source_type", "sub_area", "aliases", "status"):
        assert key in item
    assert item["item_type"] in EV_TYPES
    assert item["status"] in EV_STATUS
    assert item["sub_area"] in ALL_SUB and item["sub_area"].rsplit("-", 1)[0] in item["topics"]
    assert isinstance(item["aliases"], list)
    assert item["source_url"].startswith("https://")
    assert not item.get("last_verified_date") and not item.get("retrieved_date")


def test_evidence_titles_and_aliases_do_not_collide():
    seen = {}
    v1_titles = {i["title"] for i in V1_EVIDENCE}
    for item in V2_EVIDENCE:
        assert item["title"] not in v1_titles
        for name in [item["title"]] + item["aliases"]:
            key = name.lower()
            assert seen.get(key, item["title"]) == item["title"], f"{name!r} used by two items"
            seen[key] = item["title"]
