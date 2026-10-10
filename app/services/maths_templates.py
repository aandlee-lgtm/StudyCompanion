"""Syllabus-aligned parametrised Mathematics Advanced question templates (owner: maths).

Every instance is labelled GENERATED. Answers and worked solutions are computed exactly, so
marking is deterministic. Templates are keyed by learning-plan code (e.g. "1B") so that a LEARNING
subtopic never runs out of fresh practice, and every template honours the requested difficulty:
1 foundation, 2 HSC-standard, 3 challenging (usually an HSC-style multi-part question of 4–6 marks).

Parameters are chosen with a seeded RNG; that is *content generation*, not the question selection
logic (which lives in app.selection). The template bodies live in the ``maths_tpl_*`` modules; this
module is the registry plus the content self-test (spec 50: verify generated content)."""
from __future__ import annotations

import json
import random
import re
from typing import Callable

from app.services import maths_tpl_legacy
from app.services.maths_tpl_base import Generated, model_response  # noqa: F401  (re-exported)

_MODULE_NAMES = ("maths_tpl_ch1", "maths_tpl_ch2", "maths_tpl_ch3", "maths_tpl_ch4_5", "maths_tpl_ch6", "maths_tpl_ch7",
                 "maths_tpl_ch8", "maths_tpl_ch9_10", "maths_tpl_y11")


def _code(name: str) -> str:
    code = name[2:]
    return "Y11-" + code[4:] if code.startswith("Y11_") else code


def _collect(mod) -> dict[str, Callable]:
    return {_code(nm): fn for nm, fn in vars(mod).items() if nm.startswith("t_") and callable(fn)}


def _load() -> tuple[dict[str, Callable], set[str]]:
    import importlib

    out = _collect(maths_tpl_legacy)
    v2: set[str] = set()
    for name in _MODULE_NAMES:
        try:
            mod = importlib.import_module(f"app.services.{name}")
        except ModuleNotFoundError:
            continue
        found = _collect(mod)
        out.update(found)
        v2 |= set(found)
    return out, v2


TEMPLATES, V2_CODES = _load()


def _tidy_common_errors(g: Generated) -> list[dict]:
    """Drop any documented error whose answer would be marked correct (dead diagnostics), and duplicates."""
    from app.marking.maths import mark_answer

    parts = {p["label"]: p for p in (g.answer.get("parts") or [])} if g.answer.get("type") == "parts" else {}
    out, seen = [], set()
    for ce in g.common_errors:
        key = (ce.get("part"), str(ce.get("answer")))
        if key in seen:
            continue
        spec, mk = (parts[ce["part"]]["answer"], parts[ce["part"]].get("marks", 1)) if ce.get("part") in parts else (g.answer, g.marks)
        res = mark_answer(str(ce["answer"]), spec, mk)
        if res.correct or res.mark >= mk:
            continue
        seen.add(key)
        out.append(ce)
    return out


def generate(code: str, seed: int, difficulty: int) -> Generated | None:
    fn = TEMPLATES.get(code)
    if fn is None:
        return None
    d = min(3, max(1, int(difficulty)))
    rng = random.Random(f"{code}:{seed}:{d}")
    g = fn(rng, d)
    g.common_errors = _tidy_common_errors(g)
    return g


def minutes_for(marks: int) -> float:
    # HSC Mathematics Advanced: 100 marks in 180 minutes => ~1.8 min/mark, plus reading.
    return round(1.8 * marks + 0.5, 1)


# ------------------------------------------------------------- self-test ---
_GLITCHES = [
    (re.compile(r"=\s*\?"), "unfilled '?' placeholder"),
    (re.compile(r"\+\s*-\s*\d"), "'+ -' in text"),
    (re.compile(r"(?<![\d.])\+\s*0(?![\d.])"), "'+ 0' term"),
    (re.compile(r"(?<![\d.{a-zA-Z^_])1\s*[a-z](?![a-zA-Z])(?!\})"), "coefficient 1 written"),
    (re.compile(r"\bNone\b"), "'None' in text"),
    (re.compile(r"- -"), "'- -' in text"),
]


def check(g: Generated, d: int) -> list[str]:
    """Problems with one generated question (empty list = fine)."""
    from app.marking.maths import CATEGORIES, TOPIC_TAGS, mark_answer

    probs: list[str] = []
    if g.difficulty != d:
        probs.append(f"difficulty {g.difficulty} produced for requested {d}")
    try:
        json.dumps(g.answer)
        json.dumps(g.solution())
    except (TypeError, ValueError) as exc:
        probs.append(f"not JSON-serialisable: {exc}")
    a = g.answer
    if a.get("type") == "parts":
        tot = sum(p.get("marks", 1) for p in a["parts"])
        if tot != g.marks:
            probs.append(f"part marks {tot} != question marks {g.marks}")
        for p in a["parts"]:
            if f"({p['label']})" not in g.text:
                probs.append(f"part ({p['label']}) not in the text")
    res = mark_answer(model_response(a), a, g.marks, g.common_errors, options=g.options)
    if not res.correct:
        probs.append(f"model answer {model_response(a)!r} not accepted: {res.diagnosis}")
    parts = {p["label"]: p for p in (a.get("parts") or [])}
    for ce in g.common_errors:
        if ce.get("category") not in CATEGORIES:
            probs.append(f"common error category {ce.get('category')!r} not in the spec 5C list")
        if ce.get("topic_tag") is not None and ce.get("topic_tag") not in TOPIC_TAGS:
            probs.append(f"common error tag {ce.get('topic_tag')!r} not in the spec 23 list")
        spec, mk = (parts[ce["part"]]["answer"], parts[ce["part"]].get("marks", 1)) if ce.get("part") in parts else (a, g.marks)
        r = mark_answer(str(ce["answer"]), spec, mk, [dict(ce, part=None)])
        if r.correct:
            probs.append(f"common error {ce['answer']!r} is marked correct")
        elif r.category != ce.get("category") and not r.common_error:
            probs.append(f"common error {ce['answer']!r} not recognised (got {r.category})")
        if ce.get("step") and not (1 <= ce["step"] <= len(g.steps)):
            probs.append(f"common error step {ce['step']} outside the worked solution")
    if not g.steps or not g.concept or not g.technique:
        probs.append("missing worked solution, concept or technique")
    if not g.quicker:
        probs.append("no quicker method / check")
    if not g.skill:
        probs.append("no skill description")
    if not g.common_errors and a.get("type") not in ("interval", "mcq"):
        probs.append("no common errors")
    for pat, what in _GLITCHES:
        if pat.search(g.text.replace("\\,", "")):
            probs.append(f"text glitch: {what}")
    if g.text.count("\\(") != g.text.count("\\)"):
        probs.append("unbalanced \\( \\)")
    for cpt in g.checkpoints:
        try:
            from app.marking.maths import stored_ast

            stored_ast(cpt["value"], cpt.get("vars") or ["x"])
        except Exception as exc:  # noqa: BLE001
            probs.append(f"checkpoint {cpt.get('value')!r} unreadable: {exc}")
    tier = {1: (1, 2), 2: (2, 4), 3: (4, 6)}[d]
    if not tier[0] <= g.marks <= tier[1]:
        probs.append(f"{g.marks} marks outside the difficulty-{d} range {tier}")
    return probs


def self_test(codes=None, seeds: int = 12) -> dict[str, list[str]]:
    """Generate many instances of every template and collect problems (empty dict = all good)."""
    out: dict[str, list[str]] = {}
    for code in sorted(codes or TEMPLATES):
        for d in (1, 2, 3):
            for s in range(seeds):
                try:
                    g = generate(code, s, d)
                    probs = check(g, d)
                except Exception as exc:  # noqa: BLE001
                    probs = [f"crashed: {type(exc).__name__}: {exc}"]
                if probs:
                    out.setdefault(f"{code} L{d}", [])
                    for p_ in probs:
                        if p_ not in out[f"{code} L{d}"]:
                            out[f"{code} L{d}"].append(p_)
    return out
