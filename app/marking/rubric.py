"""Offline heuristic estimate for written English and Legal responses.

Used ONLY when no AI provider is configured. It measures observable features (length relative
to marks, quotation, analytical language, judgement, legal authorities) and is always labelled
as a rough estimate — never as a marking judgement."""
from __future__ import annotations

import re

ANALYSIS_VERBS = ["suggest", "reveal", "emphasis", "convey", "position", "highlight", "reflect", "evoke", "underscore", "invite",
                  "illustrate", "create", "shape", "imply", "foreground", "juxtapos", "symbolis", "represent", "accentuat", "evokes", "enact"]
TECHNIQUES = ["metaphor", "simile", "imagery", "personification", "juxtaposition", "irony", "tone", "symbol", "motif", "structure",
              "repetition", "alliteration", "rhetorical", "first person", "narrat", "dialogue", "enjambment", "rhyme", "contrast", "listing",
              "cumulative", "fragment", "syntax", "voice", "perspective", "allusion", "hyperbole", "understatement", "oxymoron", "caesura"]
JUDGEMENT = ["effective", "ineffective", "to a large extent", "to a limited extent", "partially", "overall", "largely", "moderately",
             "on balance", "highly", "limited", "successful", "unsuccessful"]
LEGAL_TERMS = ["legislation", "act", "court", "rights", "jurisdiction", "precedent", "statute", "sentenc", "bail", "accused",
               "prosecution", "defence", "law reform", "justice", "treaty", "convention", "parliament", "common law", "jury", "remand"]
COMPARE = ["both", "whereas", "while", "similarly", "in contrast", "by contrast", "unlike", "likewise", "text 1", "text 2"]


def _count(text: str, words: list[str]) -> int:
    t = text.lower()
    return sum(t.count(w) for w in words)


def features(text: str, subject: str) -> dict:
    words = len(text.split())
    quotes = len(re.findall(r"['\"‘“][^'\"‘’“”]{3,}['\"’”]", text))
    acts = re.findall(r"\b[A-Z][A-Za-z()' ]+ Act \d{4}\b", text)
    cases = re.findall(r"\b[A-Z][A-Za-z]+ v [A-Z][A-Za-z]+", text)
    years = [int(y) for y in re.findall(r"\b(20[0-3]\d)\b", text)]
    return {
        "words": words, "quotes": quotes, "analysis": _count(text, ANALYSIS_VERBS), "techniques": _count(text, TECHNIQUES),
        "judgement": _count(text, JUDGEMENT), "legal_terms": _count(text, LEGAL_TERMS), "acts": acts, "cases": cases,
        "recent_years": [y for y in years if y >= 2015], "compare": _count(text, COMPARE),
    }


def estimate(text: str, subject: str, marks: int, verb: str | None, paired: bool = False) -> dict:
    f = features(text, subject)
    verb = (verb or "").lower()
    per_mark = 40 if subject == "ENGLISH" else 45
    length = min(1.0, f["words"] / max(30, per_mark * marks))
    checks: list[tuple[str, float, bool, str]] = []
    if subject == "ENGLISH":
        need_q = 1 if marks <= 3 else 2
        checks += [
            ("Textual evidence", 0.25, f["quotes"] >= need_q, f"Use at least {need_q} short, precise quotation(s) integrated into your sentences."),
            ("Analysis of effect", 0.3, f["analysis"] >= max(1, marks // 2), "Explain HOW language shapes meaning (e.g. 'suggests', 'positions the reader'), not just WHAT happens."),
            ("Language/form features", 0.15, f["techniques"] >= 1, "Name the specific techniques or features of form you are analysing."),
        ]
        if verb in ("evaluate", "assess"):
            checks.append(("Judgement", 0.15, f["judgement"] >= 1, "State a clear judgement (e.g. 'highly effective because...')."))
        if paired or verb == "compare":
            checks.append(("Comparison", 0.15, f["compare"] >= 2, "Compare explicitly using connectives such as 'whereas' and 'both'."))
    else:
        checks += [
            ("Legal terminology", 0.2, f["legal_terms"] >= 2, "Use precise legal terminology."),
            ("Legal authority", 0.3, bool(f["acts"] or f["cases"]), "Support points with named legislation and/or cases (from your evidence bank)."),
        ]
        if verb in ("evaluate", "assess", "discuss") or marks >= 5:
            checks.append(("Judgement", 0.25, f["judgement"] >= 1, f"Answer the directive verb '{verb or 'evaluate'}' with an explicit judgement about effectiveness."))
        if marks >= 5:
            checks.append(("Contemporary evidence", 0.15, bool(f["recent_years"]), "Add dated contemporary evidence (a recent case, report or reform)."))
    total_w = sum(c[1] for c in checks) + 0.25
    got = 0.25 * length + sum(c[1] for c in checks if c[2])
    fraction = got / total_w
    if subject == "ENGLISH" and f["analysis"] == 0:
        fraction = min(fraction, 0.5)  # descriptive responses are capped
    mark = round(fraction * marks * 2) / 2
    if f["words"] < 15:
        mark = 0 if f["words"] < 5 else min(mark, 1)
    strengths = [c[0] for c in checks if c[2]]
    gaps = [(c[0], c[3]) for c in checks if not c[2]]
    if length < 0.6:
        gaps.insert(0, ("Development", f"For {marks} marks, develop more points: your response is short for the mark value."))
    return {"mark": min(mark, marks), "fraction": fraction, "features": f, "strengths": strengths, "gaps": gaps}
