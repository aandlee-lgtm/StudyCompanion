"""Offline Legal Studies estimate built on resolved citations and required elements
(audit legal-04, legal-05, legal-15, legal-20).

Used when no AI provider is configured (or AI marking failed). It is always labelled as an
estimate. What it measures:

- REQUIRED ELEMENTS of the question (``Question.solution.required_elements``): the main
  component, so a strong answer that names organisations rather than Acts is not marked down;
- AUTHORITIES the response cites, resolved against the WHOLE evidence bank: full credit for a
  verified item, half for an unverified one, nothing for an authority that is not in the bank or
  is recorded as repealed/superseded. Those produce corrections and a deduction, so invented or
  outdated law is never rewarded;
- judgement language (evaluative verbs only), precise legal terms (word boundaries), use of the
  stimulus, law reform, contemporary evidence (a bank item dated within N years of today),
  cause-and-effect / comparison language for the directive verb, and structure for extended
  responses;
- length caps per mark value (e.g. a 15-mark response under 150 words cannot score above 3).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date

from app.services import citations as cit

STOP = set("""a an the and or but of to in on for with by as at from into onto than then that this these those there their they them it its
is are was were be been being has have had do does did not no nor so such can could may might must shall should will would which who whom
whose what when where why how also any each every some more most other others own same very just only about above after again against all
both before below between during further here once out over under until up while because if until through per via one two three four five
own your you we our us he she his her him i me my""".split())

# precise Legal terms (stems allowed with \\w*); counted once each
LEGAL_TERMS = [
    r"legislat\w*", r"statut\w*", r"courts?", r"jurisdictions?", r"precedents?", r"common law", r"sentenc\w*", r"bail", r"remand\w*",
    r"accused", r"prosecut\w*", r"defen[cs]es?", r"law reform", r"justice", r"treat(?:y|ies)", r"conventions?", r"covenants?",
    r"parliament\w*", r"jur(?:y|ies|ors?)", r"rights?", r"mens rea", r"actus reus", r"beyond reasonable doubt", r"burden of proof",
    r"standard of proof", r"presumption of innocence", r"doli incapax", r"rule of law", r"ratif\w+", r"sovereignty", r"enforc\w+",
    r"tribunals?", r"appeals?", r"pleas?", r"charge negotiation", r"offences?", r"indictable", r"summary offences?", r"diversion\w*",
    r"deterrence", r"rehabilitat\w*", r"retribution", r"incapacitation", r"procedural fairness", r"natural justice",
    r"self-determination", r"inalienable", r"domestic law", r"international law", r"customary international law", r"extradit\w*",
    r"victims?", r"aggravating", r"mitigating", r"parole", r"adversar\w+", r"inquisitorial", r"warrants?", r"arrest\w*",
    r"interrogat\w*", r"detention", r"ngos?", r"united nations", r"intergovernmental", r"constitution\w*", r"bill of rights",
    r"strict liability", r"causation", r"culpab\w+", r"recidivism", r"restorative justice", r"legal aid", r"unacceptable risk",
]
JUDGEMENT = [
    r"(?:in)?effective(?:ly|ness)?", r"to an? (?:large|limited|great|significant|considerable|lesser|some) extent", r"partially", r"overall",
    r"largely", r"moderately", r"on balance", r"(?:un)?successful(?:ly)?", r"(?:in)?adequate(?:ly)?", r"fails? to", r"succeeds? in",
    r"limited (?:in|by|effectiveness)", r"(?:highly|only partly|partly) (?:effective|successful)", r"(?:strength|weakness)(?:es)?",
    r"however", r"although", r"nevertheless",
]
CAUSE = [r"because", r"therefore", r"as a result", r"this means", r"which means", r"consequently", r"thus", r"so that", r"leads? to",
         r"results? in", r"due to", r"in order to", r"which (?:allows|ensures|prevents|protects)"]
COMPARE = [r"whereas", r"while", r"unlike", r"in contrast", r"by contrast", r"both", r"similarly", r"differs?", r"however"]
REFORM = r"\b(?:law reforms?|reform(?:s|ed)?|amend(?:ed|ment|ments)|repeal(?:ed)?|introduced|recommend(?:ed|ation|ations)|replaced)\b"
EVALUATIVE = {"evaluate", "assess", "discuss", "to what extent", "justify", "critically analyse", "critically evaluate"}
WORDS_PER_MARK = 35  # short answers; extended responses use 45


def _rx(words: list[str]) -> re.Pattern:
    return re.compile(r"(?<![\w-])(?:" + "|".join(words) + r")(?![\w-])", re.I)


_TERMS_RX = [re.compile(r"(?<![\w-])" + w + r"(?![\w-])", re.I) for w in LEGAL_TERMS]
_JUDGE_RX, _CAUSE_RX, _COMPARE_RX = _rx(JUDGEMENT), _rx(CAUSE), _rx(COMPARE)
_REFORM_RX = re.compile(REFORM, re.I)


def words(text: str) -> int:
    return len((text or "").split())


def stem(w: str) -> str:
    w = re.sub(r"[^a-z0-9]", "", w.lower())
    for suf in ("ations", "ation", "ments", "ment", "ness", "ities", "ity", "ings", "ing", "ies", "ed", "es", "s", "ly"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            w = w[: -len(suf)]
            break
    return w[:7]


def key_terms(text: str) -> list[str]:
    out: list[str] = []
    for w in re.findall(r"[A-Za-z][A-Za-z'’\-]*|\d{2,4}", text or ""):
        for part in re.split(r"[-’']", w):
            lw = part.lower()
            if len(lw) < 3 or lw in STOP:
                continue
            s = stem(lw)
            if s and s not in out:
                out.append(s)
    return out


def legal_terms(text: str) -> list[str]:
    return [rx.pattern for rx in _TERMS_RX if rx.search(text or "")]


def judgement_count(text: str) -> int:
    return len(_JUDGE_RX.findall(text or ""))


def paragraphs(text: str) -> int:
    blocks = [b for b in re.split(r"\n\s*\n", (text or "").strip()) if words(b) >= 15]
    return len(blocks)


def verb_of(q) -> str:
    v = (getattr(q, "directive_verb", None) or "").strip().lower()
    if not v and re.match(r"\s*to what extent", getattr(q, "question_text", "") or "", re.I):
        v = "to what extent"
    return v


# ------------------------------------------------------------------ required elements ---


def element_text(e) -> str:
    if isinstance(e, dict):
        return e.get("name") or e.get("text") or ""
    return str(e)


def match_element(e, resp_terms: set[str], resp_lower: str) -> tuple[float, list[str]]:
    """1.0 met, 0.5 partly, 0 missing; plus the terms that matched."""
    if isinstance(e, dict) and e.get("any"):
        hits = [t for t in e["any"] if re.search(r"(?<![\w-])" + re.escape(t.lower()) + r"(?![\w-])", resp_lower)]
        return (1.0 if hits else 0.0), hits
    terms = key_terms(element_text(e))
    if not terms:
        return 0.0, []
    hits = [t for t in terms if t in resp_terms]
    ratio = len(hits) / len(terms)
    need = min(2, len(terms))
    if ratio >= 0.5 and len(hits) >= need:
        return 1.0, hits
    if ratio >= 0.3 and len(hits) >= need:
        return 0.5, hits
    return 0.0, hits


# ------------------------------------------------------------------ the estimate ---


@dataclass
class Component:
    key: str
    name: str
    weight: float
    score: float
    comment: str = ""
    improve: str = ""
    category: str | None = None  # error-journal category when it is a gap

    @property
    def judgement(self) -> str:
        return "met" if self.score >= 0.75 else ("partly met" if self.score >= 0.25 else "not met")


@dataclass
class Estimate:
    mark: float
    marks: int
    fraction: float
    components: list[Component]
    elements: list[dict]
    resolutions: list
    corrections: list[str]
    journal: list[dict]
    caps: list[str]
    features: dict
    deduction: float = 0.0
    notes: list[str] = field(default_factory=list)


def features(text: str, bank: cit.Bank, today: date, settings: dict | None = None, resolutions=None) -> dict:
    s = settings or {}
    res = resolutions if resolutions is not None else cit.unique(cit.resolve(text or "", bank, today, s))
    auth = [r for r in res if r.citation.kind != "statistic"]
    good = [r for r in auth if r.item is not None and r.status in ("verified", "recheck_due", "unverified")]
    years = int(s.get("legal_contemporary_years", 5) or 5)
    recent: list[str] = []
    for r in good:
        y = r.item.year or r.citation.year
        if y and y >= today.year - years:
            recent.append(r.item.title)
    # a dated recent development in the same sentence as a bank authority also counts
    for sent in re.findall(r"[^.!?\n]+[.!?]?", text or ""):
        ys = [int(y) for y in re.findall(r"\b(20\d\d)\b", sent)]
        if any(y >= today.year - years for y in ys) and any(r.citation.start >= 0 and r.citation.name in sent for r in good):
            recent.append(sent.strip()[:80])
    media_only = bool(recent) and all((r.item.item_type == "media") for r in good if r.item and r.item.title in recent)
    return {
        "words": words(text), "terms": legal_terms(text), "judgement": judgement_count(text), "cause": len(_CAUSE_RX.findall(text or "")),
        "compare": len(_COMPARE_RX.findall(text or "")), "reform": len(_REFORM_RX.findall(text or "")), "paragraphs": paragraphs(text),
        "legislation": sorted({r.item.title for r in good if r.item.item_type in ("legislation", "law_reform")}),
        "cases": sorted({r.item.title for r in good if r.item.item_type == "case"}),
        "other_items": sorted({r.item.title for r in good if r.item.item_type not in ("legislation", "law_reform", "case")}),
        "contemporary": sorted(set(recent)), "media_only_contemporary": media_only,
        "not_in_bank": [r.citation.name for r in auth if r.status == "not_in_bank"],
        "outdated": [r.citation.name for r in auth if r.status == "outdated" or r.possibly_outdated],
    }


def _stimulus_score(response: str, stimulus: str | None) -> tuple[float, list[str]]:
    if not stimulus:
        return 0.0, []
    body = stimulus
    names = {w for w in re.findall(r"(?<=[a-z,;:] )([A-Z][a-z]{2,})", body)} - {"The", "This", "These", "Witnesses", "Police"}
    nums = set(re.findall(r"\b\d+(?:\.\d+)?%?", body)) - {str(i) for i in range(0, 13)}
    hits = sorted({n for n in names if re.search(rf"\b{re.escape(n)}\b", response)} | {n for n in nums if n in response})
    generic = re.search(r"\b(?:the|this) (?:scenario|stimulus|source|table|extract|data|figures?|statistics)\b", response, re.I)
    score = min(1.0, len(hits) / 2 + (0.5 if generic else 0))
    return score, hits


def item_label(item: cit.BankItem, today: date, settings: dict | None = None) -> str:
    st = cit.item_status(item, today, settings)
    if st == "verified":
        return f"verified {item.last_verified:%d %b %Y}"
    if st == "recheck_due":
        return f"re-check due, last checked {item.last_verified:%d %b %Y}"
    if st == "outdated":
        return f"recorded as {item.status}"
    return "in your evidence bank, not yet verified"


def _need_authorities(marks: int) -> int:
    return 1 if marks <= 4 else (2 if marks <= 8 else 4)


def _terms_needed(marks: int) -> int:
    return 2 if marks <= 3 else (3 if marks <= 6 else (4 if marks <= 8 else 6))


def expected_words(marks: int) -> int:
    return marks * (WORDS_PER_MARK if marks <= 8 else 45)


def _round_half(x: float) -> float:
    return round(x * 2) / 2


def estimate(q, response: str, bank: cit.Bank, today: date, settings: dict | None = None, stimulus: str | None = None) -> Estimate:
    s = settings or {}
    marks = int(q.marks or 1)
    sol = q.solution or {}
    verb = verb_of(q)
    text = response or ""
    lower = text.lower()
    res = cit.unique(cit.resolve(text, bank, today, s))
    f = features(text, bank, today, s, res)
    criteria_blob = " ".join([q.marking_guideline or "", " ".join(element_text(e) for e in sol.get("required_elements") or []),
                              q.question_text or ""]).lower()
    comps: list[Component] = []
    corrections: list[str] = []
    journal: list[dict] = []

    # 1. required elements (legal-05)
    elements_out: list[dict] = []
    req = sol.get("required_elements") or []
    if req:
        resp_terms = set(key_terms(text))
        got = 0.0
        for e in req:
            sc, hits = match_element(e, resp_terms, lower)
            got += sc
            elements_out.append({"text": element_text(e), "score": sc, "met": sc >= 1.0, "partly": 0 < sc < 1.0})
        cov = got / len(req)
        missing = [e["text"] for e in elements_out if not e["met"]]
        comps.append(Component("elements", "Required elements for this question", 0.45, cov,
                               f"{sum(1 for e in elements_out if e['met'])} of {len(req)} covered"
                               + (f", {sum(1 for e in elements_out if e['partly'])} partly" if any(e["partly"] for e in elements_out) else ""),
                               ("Add: " + missing[0]) if missing else ""))

    # 2. authorities resolved against the whole bank (legal-04 a/b)
    auth = [r for r in res if r.citation.kind != "statistic"]
    needs_authority = marks >= 5 or bool(re.search(r"\b(legislation|acts?|cases?|authorit\w*|statutes?|treat(?:y|ies)|conventions?|law reform)\b", criteria_blob))
    credit = 0.0
    for r in auth:
        if r.status in ("verified", "recheck_due"):
            credit += 1.0
        elif r.status == "unverified":
            credit += 0.5
    if needs_authority:
        need = _need_authorities(marks)
        score = min(1.0, credit / need)
        comps.append(Component("authority", "Legal authority (from your evidence bank)", 0.2, score,
                               (f"{len([r for r in auth if r.item is not None and r.status != 'outdated'])} bank authorit"
                                f"{'y' if len([r for r in auth if r.item is not None and r.status != 'outdated']) == 1 else 'ies'} cited")
                               + (f"; expected about {need}" if score < 1 else ""),
                               f"Support your points with {need} authorit{'y' if need == 1 else 'ies'} from your evidence bank (legislation, cases, treaties or reports).",
                               "missing authority"))
    problems = 0
    for r in auth:
        if r.status == "outdated" or (r.status == "not_in_bank" and r.possibly_outdated):
            problems += 1
            msg = r.note or f"{r.citation.name} is outdated."
            if r.item is not None and r.item.superseded_by:
                cur = bank.get(r.item.superseded_by)
                if cur is not None:
                    msg += f" Use the current law instead: {cur.title} ({item_label(cur, today, s)})."
            corrections.append(msg)
            journal.append({"category": "outdated legislation", "description": msg})
        elif r.status == "not_in_bank":
            problems += 1
            msg = r.note or f"{r.citation.name} is not in your evidence bank. Check that it exists before using it."
            corrections.append(msg)
            journal.append({"category": "unverified/invented authority", "description": msg})
    for r in res:
        if r.status == "no_source":
            corrections.append(f"'{r.citation.name}': {r.note}")

    # 3. judgement (evaluative verbs and extended responses)
    if verb in EVALUATIVE or marks >= 10:
        need_j = 1 if marks < 10 else 3
        sc = min(1.0, f["judgement"] / need_j)
        comps.append(Component("judgement", "Judgement that answers the directive verb", 0.15, sc,
                               f"{f['judgement']} judgement marker(s)",
                               f"Answer '{q.directive_verb or 'evaluate'}' with an explicit judgement (e.g. 'largely effective because...') and sustain it to your conclusion.",
                               "description instead of evaluation" if f["judgement"] == 0 else "weak judgement"))

    # 4. terminology (word boundaries, legal-04 c)
    tn = _terms_needed(marks)
    comps.append(Component("terminology", "Precise legal terminology", 0.1, min(1.0, len(f["terms"]) / tn), f"{len(f['terms'])} distinct legal term(s)",
                           "Use precise legal terms (for example the names of tests, doctrines and institutions) instead of everyday words.",
                           "imprecise legal terminology"))

    # 5. contemporary evidence (legal-04 d)
    if marks >= 6 or (verb in EVALUATIVE and marks >= 5) or re.search(r"contemporary|recent|current", criteria_blob):
        years = int(s.get("legal_contemporary_years", 5) or 5)
        comps.append(Component("contemporary", "Contemporary evidence (dated, from your bank)", 0.1, 1.0 if f["contemporary"] else 0.0,
                               ", ".join(f["contemporary"][:3]) or f"none from the last {years} years",
                               f"Add one development from the last {years} years (a case, reform or report from your evidence bank) and say what it shows.",
                               "insufficient contemporary evidence"))

    # 6. law reform
    if marks >= 10 or re.search(r"\breform", criteria_blob):
        comps.append(Component("law_reform", "Law reform", 0.1, min(1.0, f["reform"] / (2 if marks >= 10 else 1)), f"{f['reform']} reference(s) to reform",
                               "Discuss law reform: what changed, why, and whether it made the law more effective.", "no law reform"))

    # 7. the stimulus
    if stimulus:
        sc, hits = _stimulus_score(text, stimulus)
        comps.append(Component("stimulus", "Use of the stimulus", 0.15, sc, ("refers to " + ", ".join(hits[:4])) if hits else "no specific reference",
                               "Refer to specific details of the stimulus (people, facts, figures) and explain how each supports your point.",
                               "stimulus not used"))

    # 8. the directive verb's language
    if verb in ("explain", "analyse", "account for"):
        comps.append(Component("verb", f"'{q.directive_verb}': cause and effect", 0.05, min(1.0, f["cause"] / max(1, marks // 3)),
                               f"{f['cause']} cause-and-effect link(s)", "Link each point to its consequence ('because', 'as a result', 'this means').",
                               "failure to address directive verb"))
    elif verb in ("compare", "distinguish", "contrast"):
        comps.append(Component("verb", f"'{q.directive_verb}': similarities and differences", 0.05, min(1.0, f["compare"] / 2), f"{f['compare']} comparison marker(s)",
                               "Make the comparison explicit ('whereas', 'unlike', 'both').", "failure to address directive verb"))

    # 9. structure (extended responses)
    if marks >= 10:
        comps.append(Component("structure", "Structure (introduction, developed paragraphs, conclusion)", 0.05, min(1.0, f["paragraphs"] / 4),
                               f"{f['paragraphs']} developed paragraph(s)", "Organise the response into an introduction with your judgement, 3–4 developed body paragraphs and a conclusion."))

    tw = sum(c.weight for c in comps) or 1.0
    fraction = sum(c.weight * c.score for c in comps) / tw
    raw = fraction * marks
    caps: list[str] = []
    # length caps per mark value (legal-04 e)
    ew = expected_words(marks)
    ratio = f["words"] / ew if ew else 1
    factor = 0.25 if ratio < 0.25 else 0.5 if ratio < 0.5 else 0.75 if ratio < 0.7 else 1.0
    cap = marks * factor
    cap = math.floor(cap) if marks >= 10 else math.floor(cap * 2) / 2
    if f["words"] < 5:
        cap = 0
    elif f["words"] < 15:
        cap = min(cap, 1)
    if raw > cap:
        caps.append(f"Capped at {cap:g} because the response is {f['words']} words for a {marks}-mark question (about {ew} words is typical).")
        raw = cap
    deduction = 0.0
    if problems:
        deduction = min(problems * 0.5, 1.5 if marks < 10 else 3.0)
        raw = max(0.0, raw - deduction)
        caps.append(f"{deduction:g} mark(s) deducted for relying on authorities that are outdated or not in your evidence bank.")
    mark = min(float(marks), max(0.0, _round_half(raw)))

    for c in comps:
        if not c.category or c.score >= 0.5:
            continue
        if c.key == "authority" and problems:
            continue  # the outdated / not-in-bank entries above already describe the authority problem
        journal.append({"category": c.category, "description": c.improve})
    seen, uniq = set(), []
    for j in journal:
        if j["category"] not in seen:
            seen.add(j["category"])
            uniq.append(j)
    notes = []
    if f["media_only_contemporary"]:
        notes.append("Your only contemporary support is journalism: use it as supporting evidence alongside a primary or official source.")
    return Estimate(mark=mark, marks=marks, fraction=fraction, components=comps, elements=elements_out, resolutions=res,
                    corrections=corrections, journal=uniq, caps=caps, features=f, deduction=deduction, notes=notes)


# ------------------------------------------------------------------ explanations ---


def criteria_level(rows: list[dict], mark: float) -> dict | None:
    """The criteria row whose mark range contains ``mark`` (rows as in legal_content.criteria_rows)."""
    best = None
    for r in rows or []:
        rng = str(r.get("range") or r.get("mark") or "")
        nums = [int(n) for n in re.findall(r"\d+", rng)]
        if not nums:
            continue
        lo, hi = (nums[0], nums[-1])
        if lo <= mark <= hi or (lo - 0.5 <= mark < lo):
            return r
        if hi <= mark and (best is None or hi > max(int(n) for n in re.findall(r"\d+", str(best.get("range") or best.get("mark"))))):
            best = r
    return best


def comparison_rows(model_f: dict | None, resp_f: dict, est: Estimate) -> list[dict]:
    """Side-by-side conceptual comparison, model vs yours (legal-15 element 9)."""
    m = model_f or {}
    met = sum(1 for e in est.elements if e["met"])

    def lst(x):
        return ", ".join(x) if x else "none"

    rows = [
        {"aspect": "Judgement", "model": f"{m.get('judgement', '—')} judgement marker(s)" if m else "—", "yours": f"{resp_f['judgement']} judgement marker(s)"},
        {"aspect": "Legislation", "model": lst(m.get("legislation")) if m else "—", "yours": lst(resp_f["legislation"])},
        {"aspect": "Cases", "model": lst(m.get("cases")) if m else "—", "yours": lst(resp_f["cases"])},
        {"aspect": "Treaties, reports, other bank items", "model": lst(m.get("other_items")) if m else "—", "yours": lst(resp_f["other_items"])},
        {"aspect": "Contemporary evidence", "model": lst(m.get("contemporary")) if m else "—", "yours": lst(resp_f["contemporary"])},
        {"aspect": "Law reform", "model": f"{m.get('reform', 0)} reference(s)" if m else "—", "yours": f"{resp_f['reform']} reference(s)"},
        {"aspect": "Structure", "model": f"{m.get('paragraphs', 0)} developed paragraph(s), {m.get('words', 0)} words" if m else "—",
         "yours": f"{resp_f['paragraphs']} developed paragraph(s), {resp_f['words']} words"},
    ]
    if est.elements:
        rows.insert(0, {"aspect": "Required elements", "model": "all", "yours": f"{met} of {len(est.elements)}"})
    if resp_f["not_in_bank"] or resp_f["outdated"]:
        rows.append({"aspect": "Authorities to check", "model": "none", "yours": lst(resp_f["not_in_bank"] + resp_f["outdated"])})
    return rows


TASKS = {
    "elements": "Rewrite your answer so that it covers: {missing}. Give it its own sentence and say why it matters to the question.",
    "authority": "Add {need} authorit{plural} from your evidence bank (for example {example}) and explain in one sentence what each shows.",
    "invented": "Replace every authority marked 'not in your bank' with an item from your evidence bank, or delete it. Never cite an authority you have not checked exists.",
    "outdated": "Rewrite the sentence that relies on {old} using the current law ({new}), and note one way the current law differs.",
    "judgement": "Write a one-sentence judgement that answers '{verb}' directly (e.g. 'largely effective, because...'), put it in your first sentence and return to it in your last.",
    "contemporary": "Add one dated development from the last {years} years from your evidence bank (a case, reform or report) and say what it shows about effectiveness.",
    "law_reform": "Add a paragraph on one law reform: what changed, why, and whether it improved the law.",
    "stimulus": "Use two specific details from the stimulus (a person, fact or figure) and explain how each supports your point.",
    "terminology": "Replace everyday words with precise legal terms; check each one against the glossary in your notes.",
    "verb": "Link each point to its consequence using 'because', 'as a result' or 'this means'.",
    "structure": "Plan the essay: a judgement in the introduction, one paragraph per criterion (each with an authority), and a conclusion that answers the question.",
    "length": "Develop the answer to about {ew} words: one developed paragraph (point, law, evidence, evaluation) per required element.",
}


def improvement_task(est: Estimate, q, cards: list[dict], settings: dict | None = None) -> str:
    """One specific task chosen by the largest gap (legal-15 element 10)."""
    s = settings or {}
    if est.features["outdated"]:
        old = est.features["outdated"][0]
        r = next((r for r in est.resolutions if r.citation.name == old), None)
        new = (r.item.superseded_by if r is not None and r.item is not None and r.item.superseded_by else (r.near.title if r is not None and r.near else "the current Act in your evidence bank"))
        return TASKS["outdated"].format(old=old, new=new)
    if est.features["not_in_bank"]:
        return TASKS["invented"]
    if est.caps and "words" in est.caps[0]:
        return TASKS["length"].format(ew=expected_words(est.marks))
    gaps = sorted((c for c in est.components if c.score < 1), key=lambda c: -(c.weight * (1 - c.score)))
    if not gaps:
        return "Re-read the model response and add one more developed point with an authority from your evidence bank."
    g = gaps[0]
    if g.key == "elements":
        missing = [e["text"] for e in est.elements if not e["met"]][:2]
        return TASKS["elements"].format(missing="; ".join(missing))
    if g.key == "authority":
        need = _need_authorities(est.marks)
        return TASKS["authority"].format(need=need, plural="y" if need == 1 else "ies", example=cards[0]["title"] if cards else "an Act or case from your bank")
    if g.key == "judgement":
        return TASKS["judgement"].format(verb=q.directive_verb or "evaluate")
    if g.key == "contemporary":
        return TASKS["contemporary"].format(years=int(s.get("legal_contemporary_years", 5) or 5))
    return TASKS.get(g.key, g.improve or "Address the largest gap listed above.")


def scaffold(q, cards: list[dict]) -> dict:
    """Improved-argument scaffold: claim, law, evidence, evaluation, link (legal-15 element 7)."""
    verb = (q.directive_verb or "Explain").lower()
    focus = re.sub(r"^\s*(?:with reference to [^,]+,\s*)?(?:" + re.escape(verb) + r")\s+", "", q.question_text or "", flags=re.I).rstrip(". ")
    focus = focus[:1].lower() + focus[1:] if focus else "the issue"
    law = cards[0] if cards else None
    ev = cards[1] if len(cards) > 1 else None
    claim = (f"State your judgement on {focus}: how far, for whom, and why (e.g. 'largely effective, because ...')." if verb in EVALUATIVE
             else f"State your main point about {focus} in one sentence.")
    return {
        "claim": claim,
        "law": (f"Name the law and what it does: {law['title']} — {law['summary'][:160]}" if law else "Name the relevant legislation or case from your evidence bank and say what it does."),
        "evidence": (f"Support it with {ev['title']}{' (' + ev['date'] + ')' if ev.get('date') else ''}." if ev else "Support it with a dated example from your evidence bank."),
        "evaluation": "Weigh it against a criterion — justice, protection of rights, community safety, efficiency, accessibility — and say what limits it.",
        "link": f"Link back to the question's wording: how does this point answer '{(q.question_text or '')[:90]}'?",
    }
