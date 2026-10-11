"""Mapping imported questions to the student's learning plan (sources-05/06/07/14/15, legal-12).

Rules that keep future content from being served early:

* a question is mapped to learning-plan SUBTOPICS (plan items), never just to a focus area;
* every plan item a question needs is stored (``question_plan_items``); the primary item
  (``Question.plan_item_id``) is the LATEST of them in the learning sequence, so a question that
  mixes topics is released late rather than early;
* when the evidence is weak the question is UNMAPPED (no plan item); UNMAPPED blocks approval
  until a reviewer chooses the subtopic — there is no "first topic" fallback;
* section and option headings ('Section III — Human rights', 'Question 23 — Consumers') and the
  paper ('Paper 1', Section I unseen texts) force the topic, so an option question can only map
  to its option.

The offline mapper matches whole words and phrases with weights (no substring matching) and
never auto-approves. The AI mapper gets the plan items with their statuses, the outcomes, the
guideline and the mapping-grid row, and must cite plan-item codes that exist."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import LearningPlanItem, PrescribedText, Question, QuestionMapping, Subject, SyllabusOutcome, SyllabusTopic, SyllabusVersion
from app.models.common import ADAPTABLE, DIRECT, LOCKED, PARTIAL, REJECT
from app.models.ingestion import QuestionOutcome, QuestionPlanItem

MIN_SCORE = 1.5  # below this the question is UNMAPPED
REQUIRE_RATIO = 0.6  # other subtopics scoring >= 60 % of the best are required too

# Weighted phrases per plan-item code of the seeded (Cambridge-sequence) Mathematics plan.
# 'a+b' means both a and b must occur. Weights: 3 decisive, 2 strong, 1 supporting.
MATHS_ITEM_KEYWORDS: dict[str, str] = {
    "1A": "sequence:1|nth term:1|term of the sequence:1",
    "1B": "arithmetic sequence:2|common difference:2|arithmetic progression:2",
    "1C": "geometric sequence:2|common ratio:2|geometric progression:2",
    "1D": "arithmetic+geometric:1",
    "1E": "sigma notation:2|partial sum*:2",
    "1F": "arithmetic series:2.5|sum of the first+arithmetic:1",
    "1G": "geometric series:2|sum of the first+geometric:1",
    "1H": "limiting sum:3|sum to infinity:3|infinite geometric series:3",
    "1I": "recurring decimal*:3",
    "2A": "increasing:1.5|decreasing:1.5|stationary at:1",
    "2B": "stationary point*:2.5|turning point*:2.5|nature:0.5",
    "2C": "second derivative:2.5|higher derivative*:2",
    "2D": "concav*:2.5|point* of inflection:2.5|inflection:1.5",
    "2E": "sketch*:1.5|curve sketching:2",
    "2F": "global maximum:2.5|global minimum:2.5|absolute maximum:2|maximum value of:1|minimum value of:1",
    "2G": "continuity:2|continuous at:2|differentiable:2",
    "2H": "maximis*:2|minimis*:2|maximum volume:2|maximum area:2|minimum cost:2|optimal:1.5|maximum profit:2",
    "2I": "primitive*:2",
    "3A": "area under:1.5|definite integral:1",
    "3B": "fundamental theorem:2.5",
    "3C": "odd function:1|even function:1|properties of the definite integral:2",
    "3E": "indefinite integral:2|antiderivative*:1.5",
    "3F": "area enclosed:2.5|area bounded:2.5|area between:2.5|enclosed between:2.5|bounded by:1",
    "3G": "trapezoidal:3",
    "3H": "reverse chain rule:3",
    "4A": "exponential function:1|e^x:1",
    "4B": "differentiat*+e^:2|derivative+e^:2|differentiat*+exponential:2",
    "4C": "tangent+e^:1|stationary+e^:1",
    "4D": "integrat*+e^:2|primitive+e^:2|∫+e^:2",
    "4E": "area+e^:1",
    "4F": "2^x:1.5|other bases:2|a^x:1.5",
    "5A": "logarithmic function:1.5|ln x:1|log_e:1",
    "5B": "differentiat*+ln:2|derivative+ln:2|differentiat*+log:1.5",
    "5C": "tangent+ln:1|stationary+ln:1",
    "5D": "integrat*+1/x:2|reciprocal function*:2|∫+1/x:2|primitive+1/x:2",
    "5F": "log_2:1.5|log_10:1.5|base 2:1|base 10:1",
    "6A": "period:2|amplitude:2|trigonometric graph*:2|trigonometric model*:2",
    "6B": "differentiat*+sin:2|differentiat*+cos:2|differentiat*+tan:2|derivative+sin:2|derivative+cos:2",
    "6D": "integrat*+sin:2|integrat*+cos:2|∫+sin:2|∫+cos:2|primitive+sin:2|primitive+cos:2",
    "7A": "velocity:1.5|acceleration:1.5|particle:1|displacement:1.5",
    "7B": "velocity+integrat*:1.5|acceleration+initially:1|at rest+velocity:1",
    "7C": "rate of change:1.5|rate at which:1.5|related rate*:2",
    "7D": "rate+integrat*:1|rate+volume:1",
    "7E": "exponential growth:2.5|exponential decay:2.5|half-life:2.5|growth:1|decay:1|population:1",
    "8A": "salary+each year:1|arithmetic+each year:1|geometric+each year:1",
    "8B": "geometric+logarithm*:1.5",
    "8C": "simple interest:2.5|compound interest:2.5|compounded:2|per annum:1",
    "8D": "superannuation:2.5|instalment*:2|regular deposit*:2|invest*:1",
    "8E": "loan:2.5|repayment*:2.5|amount owing:2.5|reducing balance:2",
    "8F": "annuit*:2.5|pension:2.5|present value:2|future value:2",
    "9A": "probability distribution:2|discrete random variable:2|random variable:1",
    "9B": "expected value:2|e(x):2|mean of x:1.5",
    "9C": "variance:2|standard deviation:2|var(x):2",
    "10A": "cumulative frequency:2.5|grouped data:2|ogive:2.5",
    "10B": "probability density function:3|continuous random variable:2.5|pdf:2|cumulative distribution function:2.5|cdf:2",
    "10C": "mean+continuous:1|variance+continuous:1|median+continuous:1|median+density:1",
    "10D": "standard normal:3|z-score*:2.5|z score*:2.5|standardis*:2",
    "10E": "normal distribution:2|normally distributed:2.5",
    "10F": "empirical rule:2.5|68%:1|95%:1|99.7%:1.5",
    "Y11-FUNC": "domain:1|range:1|quadratic:1|inequalit*:1|absolute value:1|polynomial:1",
    "Y11-TRANS": "translat*:1|dilat*:1|reflect*:1",
    "Y11-TRIG": "sine rule:2|cosine rule:2|exact value:1.5|radian*:1|bearing*:1.5",
    "Y11-CALC": "first principles:2.5|tangent:1|gradient:1|differentiat*:0.5",
    "Y11-EXPLOG": "log law*:2|logarithm*:1|index laws:1.5|ln:1|log:0.5",
    "Y11-PROB": "probability:1|venn:2|conditional:1.5|independent:1|at random:1",
}
EXTENSION = re.compile(r"mathematics extension|mathematical induction|\binduction\b|\bvectors?\b|binomial theorem|inverse trig|"
                       r"\bsin\^?\{?-1|\barcsin\b|projectile|\bME1[12]-", re.I)
LEGAL_OPTIONS = {
    "consumers": "LS-OPT-CONSUMERS", "global environmental protection": "LS-OPT-GEP", "family": "LS-OPT-FAMILY",
    "indigenous peoples": "LS-OPT-INDIGENOUS", "shelter": "LS-OPT-SHELTER", "workplace": "LS-OPT-WORKPLACE", "world order": "LS-OPT-WORLDORDER",
}
LEGAL_CORE = {"crime": "LS-CRIME", "human rights": "LS-HR"}
LEGAL_ITEM_KEYWORDS = {  # sub-areas (when the plan has them, codes as in docs/V2_PLAN.md)
    "LS-CRIME-NATURE": "mens rea:2|actus reus:2|strict liability:2|summary offence*:2|indictable:2|elements of crime:2|types of crime:1.5|defences:1",
    "LS-CRIME-INVESTIGATION": "police:1.5|investigat*:1.5|arrest:2|search warrant*:2|bail:2.5|remand:2|police discretion:2.5",
    "LS-CRIME-TRIAL": "trial:1.5|jury:2|burden of proof:2.5|standard of proof:2.5|plea*:1.5|legal aid:2|adversarial:2|courts:1",
    "LS-CRIME-SENTENCING": "sentenc*:2.5|punishment:2|victim impact:2.5|aggravating:2|mitigating:2|parole:2|post-sentencing:2.5",
    "LS-CRIME-YOUNG": "young offender*:3|doli incapax:3|children's court:3|youth justice:3|aged 1?:1|age of criminal responsibility:3",
    "LS-CRIME-INTERNATIONAL": "international crime:3|international criminal court:3|transnational:2.5|extradition:2.5",
    "LS-HR-NATURE": "human rights:1.5|udhr:2|universal declaration:2|developing recognition:2|self-determination:2|nature of human rights:2.5",
    "LS-HR-ENFORCE": "enforc*:1.5|ICCPR:1.5|human rights committee:2|un charter:2|treaty:1|ngo*:1.5|bill of rights:2",
    "LS-HR-ISSUE": "contemporary issue:2|asylum:2|refugee*:2|discrimination:1",
}
ENGLISH_MODULE_WORDS = {
    "EN-UNSEEN": "text 1:2|text 2:2|text 3:2|text 4:2|unseen:2|stimulus booklet:2",
    "EN-THE": "human experience*:3|texts and human experiences:3|common module:2.5|cold enough for snow:3|jessica au:3",
    "EN-TC": "textual conversation*:3|module a:2.5|hamlet:3|shakespeare:2.5|dickinson:3",
    "EN-CSL": "critical study:3|module b:2.5|pride and prejudice:3|austen:3|textual integrity:2.5",
    "EN-CRAFT": "craft of writing:3|module c:2.5|imaginative:2|discursive:2.5|persuasive:2|reflection statement:2.5|compose:1.5|stimulus:0.5",
}
STOP = set("a an and the of to in on for with by at its it is be as or from into how what which this that these those using use your "
           "review applications application introduction further more other types type part".split())
VERBS = ["Account", "Analyse", "Apply", "Appreciate", "Assess", "Calculate", "Clarify", "Classify", "Compare", "Construct", "Contrast",
         "Critically analyse", "Critically evaluate", "Deduce", "Define", "Demonstrate", "Describe", "Determine", "Differentiate", "Discuss",
         "Distinguish", "Evaluate", "Examine", "Explain", "Extract", "Extrapolate", "Find", "Identify", "Integrate", "Interpret", "Investigate",
         "Justify", "Outline", "Predict", "Propose", "Prove", "Recall", "Recommend", "Recount", "Show", "Sketch", "Solve", "Summarise",
         "Synthesise", "To what extent", "Use", "Write"]
VERB_TIER = {"identify": 1, "define": 1, "recall": 1, "outline": 1, "describe": 1, "recount": 1, "find": 1, "calculate": 1, "write": 1,
             "explain": 2, "analyse": 2, "compare": 2, "contrast": 2, "distinguish": 2, "interpret": 2, "show": 2, "solve": 2, "sketch": 2,
             "differentiate": 1, "integrate": 2, "use": 2, "determine": 2, "examine": 2, "discuss": 3, "assess": 3, "evaluate": 3,
             "to what extent": 3, "justify": 3, "prove": 3, "critically analyse": 3, "critically evaluate": 3, "synthesise": 3, "deduce": 3,
             "propose": 3, "recommend": 3, "investigate": 3}


# ------------------------------------------------------------------ phrase matching ---
def _norm(text: str) -> str:
    t = (text or "").lower()
    for a, b in {"²": "^2", "³": "^3", "ˣ": "^x", "ⁿ": "^n", "’": "'", "–": "-", "—": "-"}.items():
        t = t.replace(a, b)
    t = re.sub(r"\be\s*\^\s*\(", "e^(", t)
    return re.sub(r"\s+", " ", t)


def _pattern(phrase: str) -> re.Pattern:
    p = phrase.strip().lower()
    stem = p.endswith("*")
    p = p.rstrip("*")
    body = re.escape(p)
    left = r"(?<![a-z0-9])" if p[:1].isalnum() else ""
    right = "" if stem else (r"(?![a-z0-9])" if p[-1:].isalnum() else "")
    return re.compile(left + body + right)


@dataclass
class Rule:
    patterns: list[re.Pattern]
    weight: float
    label: str

    def hit(self, text: str) -> bool:
        return all(p.search(text) for p in self.patterns)


def parse_rules(spec: str) -> list[Rule]:
    rules = []
    for part in (spec or "").split("|"):
        if not part.strip():
            continue
        phrase, _, w = part.rpartition(":")
        if not phrase:
            phrase, w = w, "1"
        try:
            weight = float(w)
        except ValueError:
            phrase, weight = part, 1.0
        rules.append(Rule([_pattern(x) for x in phrase.split("+")], weight, phrase))
    return rules


# --------------------------------------------------------------------- candidates ---
@dataclass
class Cand:
    id: int
    code: str
    title: str
    status: str
    position: int
    active: bool
    assumed: bool
    topic_code: str | None
    topic_name: str | None
    rules: list[Rule] = field(default_factory=list)
    topic_rules: list[Rule] = field(default_factory=list)

    def as_ctx(self) -> dict:
        return {"code": self.code, "title": self.title, "status": self.status, "topic": self.topic_code, "focus_area": self.topic_name}


def plan_candidates(db: Session, subject_id: int) -> list[Cand]:
    items = db.execute(select(LearningPlanItem).where(LearningPlanItem.subject_id == subject_id).order_by(LearningPlanItem.position)).scalars().all()
    subject = db.get(Subject, subject_id)
    texts_by_topic: dict[int, list[str]] = {}
    for pt in db.execute(select(PrescribedText).where(PrescribedText.subject_id == subject_id)).scalars():
        if pt.topic_id:
            texts_by_topic.setdefault(pt.topic_id, []).extend([f"{pt.title.lower()}:3", f"{pt.author.split()[-1].lower()}:2.5"])
    out: list[Cand] = []
    codes = {i.code for i in items}
    for it in items:
        topic = it.topic
        rules: list[Rule] = []
        if subject.code == "MATHS" and it.code in MATHS_ITEM_KEYWORDS:
            rules = parse_rules(MATHS_ITEM_KEYWORDS[it.code])
        elif subject.code == "LEGAL" and it.code in LEGAL_ITEM_KEYWORDS:
            rules = parse_rules(LEGAL_ITEM_KEYWORDS[it.code])
        elif subject.code == "LEGAL" and not any(c.startswith(it.code + "-") for c in codes):
            # a core topic without sub-area items in the plan takes every sub-area's keywords
            subs = [v for k, v in LEGAL_ITEM_KEYWORDS.items() if k.startswith(it.code + "-")]
            rules = parse_rules("|".join(subs)) if subs else []
        elif subject.code == "ENGLISH" and (topic and topic.code in ENGLISH_MODULE_WORDS):
            rules = parse_rules(ENGLISH_MODULE_WORDS[topic.code])
        if not rules:  # custom plan items: distinctive title words and bigrams
            words = [w for w in re.findall(r"[a-z][a-z'-]+", (it.title or "").lower()) if w not in STOP and len(w) > 3]
            spec = [f"{w}:1" for w in words] + [f"{a} {b}:1.5" for a, b in zip(words, words[1:])]
            rules = parse_rules("|".join(spec))
        if topic is not None and topic.id in texts_by_topic:
            rules += parse_rules("|".join(texts_by_topic[topic.id]))
        topic_rules = parse_rules("|".join(f"{k.strip()}*:0.75" for k in (topic.keywords or "").split(",") if k.strip())) if topic else []
        out.append(Cand(it.id, it.code, it.title, it.status, it.position, bool(it.active), bool(it.is_assumed_knowledge),
                        topic.code if topic else None, topic.name if topic else None, rules, topic_rules))
    return out


# ------------------------------------------------------------------- section context ---
def forced_topics(subject_code: str, unit, paper_text: str = "") -> tuple[list[str], str]:
    """Topic codes a unit must map to, from its section/option headings and the paper."""
    title = (getattr(unit, "question_title", None) or "").lower()
    sec_title = (getattr(unit, "section_title", None) or "").lower()
    sec = getattr(unit, "section_name", None) or ""
    if subject_code == "LEGAL":
        for name, code in LEGAL_OPTIONS.items():
            if name in title or name in sec_title:
                return [code], f"Option heading '{getattr(unit, 'question_title', None) or getattr(unit, 'section_title', '')}' fixes the topic."
        for name, code in LEGAL_CORE.items():
            if name in sec_title or name in title:
                return [code], f"Section heading '{getattr(unit, 'section_title', '')}' fixes the topic."
        return [], ""
    if subject_code == "ENGLISH":
        p = (paper_text or "").lower()
        if getattr(unit, "stimulus_refs", None) or (("paper 1" in p) and sec == "I"):
            return ["EN-UNSEEN"], "Section I of Paper 1 (unseen texts)."
        if "paper 1" in p and sec == "II":
            return ["EN-THE"], "Section II of Paper 1 (Texts and Human Experiences)."
        if "paper 2" in p:
            m = {"I": "EN-TC", "II": "EN-CSL", "III": "EN-CRAFT"}.get(sec)
            if m:
                return [m], f"Section {sec} of Paper 2."
        return [], ""
    return [], ""


# ------------------------------------------------------------------------ proposal ---
@dataclass
class Proposal:
    required: list[Cand] = field(default_factory=list)
    candidates: list[tuple[Cand, float]] = field(default_factory=list)
    relevance: str = PARTIAL
    relevance_score: float = 0.5
    confidence: float = 0.3
    reason: str = ""
    mapped_by: str = "offline"
    is_extension: bool = False
    outcome_codes: list[str] = field(default_factory=list)
    content_descriptor: str | None = None
    original_topic: str | None = None
    skill_relevance: str | None = None
    legal_fact_currency: str | None = None
    student_rationale: str = ""
    subtopic_cited: bool = False
    directive_verb: str | None = None
    difficulty: int | None = None

    @property
    def primary(self) -> Cand | None:
        return primary_of(self.required)

    @property
    def unmapped(self) -> bool:
        return not self.required


def primary_of(items: list[Cand]) -> Cand | None:
    """The latest item in the learning sequence, preferring non-assumed (Year 12) items."""
    if not items:
        return None
    pool = [c for c in items if not c.assumed] or items
    return max(pool, key=lambda c: c.position)


def score_candidates(text: str, cands: list[Cand], extra: str = "") -> list[tuple[Cand, float, list[str]]]:
    t, x = _norm(text), _norm(extra)
    out = []
    for c in cands:
        s, why = 0.0, []
        for r in c.rules:
            if r.hit(t):
                s += r.weight
                why.append(r.label)
            elif x and r.hit(x):
                s += 0.5 * r.weight
                why.append(r.label + " (guideline)")
        for r in c.topic_rules:
            if r.hit(t):
                s += r.weight
        out.append((c, round(s, 2), why))
    # ties favour the LATER subtopic, so an uncertain question is released late, not early
    out.sort(key=lambda z: (-z[1], -z[0].position))
    return out


def detect_verb(text: str) -> str | None:
    best = None
    for v in VERBS:
        m = re.search(rf"(?:^|[.?:;]\s+|\n|\)\s*){re.escape(v)}\b", text, re.I)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), v)
    if best is None:
        for v in VERBS:
            if re.search(rf"\b{re.escape(v)}\b", text, re.I):
                return v
    return best[1] if best else None


def difficulty_for(subject_code: str, marks: int | None, part_marks: list[int], verb: str | None, hint: int | None) -> int:
    """1 foundation, 2 HSC-standard, 3 challenging: the mapping grid's targeted bands when
    available, otherwise marks per part and the directive verb (sources-02)."""
    if hint:
        return hint
    m = max(part_marks) if part_marks else (marks or 1)
    tier = VERB_TIER.get((verb or "").lower(), 2)
    if subject_code == "MATHS":
        base = 1 if m <= 1 else (2 if m <= 3 else 3)
        if tier == 3 and base < 3:
            base += 1
        return base
    if (marks or 0) >= 8:
        return 3
    return max(1, min(3, round((tier + (1 if m <= 3 else (2 if m <= 6 else 3))) / 2)))


def offline_proposal(subject_code: str, unit, cands: list[Cand], *, guideline_text: str = "", grid=None, paper_text: str = "",
                     year: int | None = None, first_hsc_year: int | None = None) -> Proposal:
    text = (unit.text or "") + ("\n" + unit.stem if getattr(unit, "stem", "") and unit.stem not in unit.text else "")
    extra = guideline_text + (" " + grid.content if grid is not None else "")
    forced, forced_reason = forced_topics(subject_code, unit, paper_text)
    pool = [c for c in cands if c.topic_code in forced or any(c.code.startswith(f) for f in forced)] if forced else cands
    if forced and not pool:
        forced_reason += f" No plan item exists for {', '.join(forced)}."
    p = Proposal(mapped_by="offline")
    p.directive_verb = detect_verb(unit.text or "")
    is_ext = subject_code == "MATHS" and bool(EXTENSION.search(text) or (grid is not None and any(o.startswith("ME") for o in grid.outcomes)))
    if grid is not None:
        p.original_topic = grid.content or None
        p.outcome_codes = list(grid.outcomes)
    scored = score_candidates(text, pool, extra)
    p.candidates = [(c, s) for c, s, _ in scored[:3] if s > 0]
    best = scored[0] if scored else None
    if forced and pool and (best is None or best[1] < MIN_SCORE):
        # the heading decides the topic; inside it, an unclear question takes the topic's latest item
        p.required = [primary_of(pool)]
        p.reason = forced_reason + " No subtopic keywords matched, so the latest item of that topic was proposed."
        p.confidence = 0.5
    elif best is not None and best[1] >= MIN_SCORE:
        req = [c for c, s, _ in scored if s >= max(MIN_SCORE, REQUIRE_RATIO * best[1])][:3]
        p.required = req
        p.confidence = min(0.75, 0.35 + 0.08 * best[1])
        p.reason = (forced_reason + " " if forced_reason else "") + f"Keyword match (offline mapper): {', '.join(best[2][:4])} → {best[0].code} {best[0].title}."
        if len(req) > 1:
            p.reason += f" Also needs {', '.join(c.code for c in req if c is not best[0])}; it is released with the latest of these."
    else:
        p.required = []
        p.confidence = 0.2
        p.reason = (forced_reason + " " if forced_reason else "") + "UNMAPPED: no subtopic matched strongly enough. Choose the subtopic before approval."
    if is_ext:
        p.is_extension, p.relevance, p.relevance_score = True, REJECT, 0.0
        p.reason += " Looks like Extension content (never served)."
    elif subject_code == "LEGAL":
        p.relevance, p.relevance_score = (DIRECT, 0.7) if p.required else (PARTIAL, 0.4)
        p.legal_fact_currency = "check"  # legal-12: offline Legal imports always need a currency check
        p.skill_relevance = "high" if p.required else "medium"
    elif subject_code == "ENGLISH":
        unseen = bool(forced and forced[0] == "EN-UNSEEN")
        p.relevance, p.relevance_score = (DIRECT, 0.7) if unseen else (ADAPTABLE, 0.4)
        if not unseen:
            p.reason += " Course-linked question: it may name a superseded prescribed text; adapt it to the 2027 texts."
    else:
        p.relevance, p.relevance_score = (DIRECT, 0.7) if (p.required and best and best[1] >= 2.5) else (PARTIAL, 0.5)
    if year and first_hsc_year and year < first_hsc_year and subject_code == "MATHS" and p.relevance == DIRECT:
        p.reason += f" Paper predates the syllabus first examined in {first_hsc_year}: confirm the content is still examinable."
    p.student_rationale = _student_rationale(p)
    return p


def _student_rationale(p: Proposal) -> str:
    c = p.primary
    if c is None:
        return ""
    return f"Tests {c.title.lower()} ({c.code}), part of {c.topic_name or 'your course'} in the 2027 course."


# ---------------------------------------------------------------------- AI mapping ---
class SegmentAnalysis(BaseModel):
    plan_item_codes: list[str] = []
    topic_code: str | None = None
    outcome_codes: list[str] = []
    content_descriptor: str | None = None
    original_topic: str | None = None
    relevance: Literal["DIRECT", "PARTIAL", "ADAPTABLE", "REJECT"]
    relevance_score: float = Field(ge=0, le=1, default=0.5)
    confidence: float = Field(ge=0, le=1)
    reason: str
    student_rationale: str = ""
    skill_relevance: Literal["high", "medium", "low"] | None = None
    legal_fact_currency: Literal["current", "check", "outdated"] | None = None
    is_extension_content: bool = False
    directive_verb: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=3)

    @field_validator("skill_relevance", "legal_fact_currency", mode="before")
    @classmethod
    def _lower(cls, v):
        return v.strip().lower() if isinstance(v, str) and v.strip() else None

    @field_validator("plan_item_codes", "outcome_codes", mode="before")
    @classmethod
    def _listify(cls, v):
        if v is None:
            return []
        return [v] if isinstance(v, str) else v


def ai_prompt(ctx: dict) -> str:
    return "\n\n".join([
        "TASK: Map this imported examination question to the student's 2027 learning plan. Choose the SUBTOPIC(S) (plan items) the "
        "question needs, citing their codes EXACTLY as listed; list every subtopic a multi-topic question needs. Never choose a "
        "subtopic you are unsure about. Mathematics Advanced only: Extension content is REJECT with is_extension_content=true. "
        "Relevance: DIRECT (still directly applicable as written), PARTIAL (only some parts apply), ADAPTABLE (valuable skill but "
        "needs rewriting, e.g. a superseded prescribed text or outdated law), REJECT (removed or irrelevant content). For English, "
        "questions on superseded prescribed texts are at most ADAPTABLE. For Legal Studies judge QUESTION SKILL RELEVANCE "
        "(high|medium|low) separately from LEGAL FACT CURRENCY (current|check|outdated); use 'check' when the question names "
        "legislation, cases or statistics you cannot confirm are current, and 'outdated' when it relies on superseded law. "
        "Use only outcome codes from the list. Write student_rationale as one plain sentence for the student (no internal jargon).",
        f"SUBJECT: {ctx['subject_name']}; SOURCE: {ctx.get('source', '')} ({ctx.get('year', '')}); syllabus first examined: {ctx.get('first_hsc_year') or 'unknown'}",
        f"SECTION: {ctx.get('section') or '—'}",
        f"LEARNING PLAN ITEMS (code, title, status, topic): {json.dumps(ctx['plan_items'], ensure_ascii=False)}",
        f"SYLLABUS OUTCOMES: {json.dumps(ctx.get('outcomes') or [], ensure_ascii=False)}",
        f"QUESTION ({ctx.get('marks') or '?'} marks):\n{ctx['question']}",
        f"MARKING GUIDELINE:\n{ctx.get('guideline') or '—'}",
        f"MAPPING GRID ROW: {ctx.get('grid') or '—'}",
        'Reply ONLY with JSON: {"plan_item_codes": ["..."], "topic_code": "...", "outcome_codes": [], "content_descriptor": null, '
        '"original_topic": null, "relevance": "DIRECT|PARTIAL|ADAPTABLE|REJECT", "relevance_score": 0..1, "confidence": 0..1, '
        '"reason": "...", "student_rationale": "...", "skill_relevance": null, "legal_fact_currency": null, '
        '"is_extension_content": false, "directive_verb": "...", "difficulty": 1|2|3}',
    ])


def ai_proposal(provider, subject: Subject, unit, cands: list[Cand], offline: Proposal, *, guideline_text: str = "", grid=None,
                source_title: str = "", year: int | None = None, first_hsc_year: int | None = None, outcomes: list[dict] | None = None,
                paper_text: str = "") -> Proposal:
    from app.ai import prompts

    forced, forced_reason = forced_topics(subject.code, unit, paper_text)
    pool = [c for c in cands if c.topic_code in forced or any(c.code.startswith(f) for f in forced)] if forced else cands
    ctx = {"subject_name": subject.name, "source": source_title, "year": year, "first_hsc_year": first_hsc_year,
           "section": " · ".join(x for x in [f"Section {unit.section_name}" if getattr(unit, "section_name", None) else "",
                                              getattr(unit, "section_title", None) or "", getattr(unit, "question_title", None) or ""] if x),
           "plan_items": [c.as_ctx() for c in pool], "outcomes": outcomes or [], "question": unit.text, "marks": unit.marks,
           "guideline": guideline_text[:3000], "grid": (f"{grid.content}; outcomes {', '.join(grid.outcomes)}; bands {grid.bands}" if grid else None)}
    res: SegmentAnalysis = provider.complete_json(prompts.SYSTEM, ai_prompt(ctx), SegmentAnalysis)
    by_code = {c.code: c for c in pool}
    cited = [by_code[c] for c in res.plan_item_codes if c in by_code]
    p = Proposal(mapped_by="ai", relevance=res.relevance, relevance_score=res.relevance_score, confidence=res.confidence,
                 reason=res.reason, is_extension=res.is_extension_content or offline.is_extension, content_descriptor=res.content_descriptor,
                 original_topic=res.original_topic or offline.original_topic, skill_relevance=res.skill_relevance,
                 legal_fact_currency=res.legal_fact_currency, student_rationale=res.student_rationale, directive_verb=res.directive_verb,
                 difficulty=res.difficulty)
    known = {o["code"] for o in (outcomes or [])}
    p.outcome_codes = [o for o in res.outcome_codes if o in known] or offline.outcome_codes
    p.candidates = offline.candidates
    if cited:
        p.required, p.subtopic_cited = cited, True
    else:
        topic_pool = [c for c in pool if c.topic_code == res.topic_code] if res.topic_code else []
        if topic_pool:
            scored = score_candidates(unit.text or "", topic_pool, guideline_text)
            p.required = [scored[0][0]] if scored and scored[0][1] >= MIN_SCORE else [primary_of(topic_pool)]
            p.reason += f" (The AI named only the focus area {res.topic_code}; subtopic {p.required[0].code} was chosen by keywords — confirm it.)"
        else:
            p.required = offline.required
            p.reason += " (The AI did not cite a valid subtopic; the keyword proposal is shown — confirm it.)"
        p.confidence = min(p.confidence, 0.6)
    if forced and forced_reason:
        p.reason = forced_reason + " " + p.reason
    if p.is_extension:
        p.relevance = REJECT
        if offline.is_extension and not res.is_extension_content:
            p.reason += " (Extension content was detected by keyword — e.g. induction or vectors — so it is rejected whatever the AI said.)"
    if subject.code == "LEGAL":
        p.legal_fact_currency = p.legal_fact_currency or "check"
        if p.legal_fact_currency == "outdated" and p.relevance == DIRECT:
            p.relevance = ADAPTABLE  # legal-12: outdated law is adapted, never served as written
        if year and (date.today().year - year) > 5 and p.legal_fact_currency == "current":
            p.legal_fact_currency = "check"
            p.reason += f" Paper is from {year}: legal facts must be checked."
    if not p.student_rationale:
        p.student_rationale = _student_rationale(p)
    return p


# ------------------------------------------------------------------- persistence ---
def set_required_items(db: Session, q: Question, item_ids: list[int], *, primary_id: int | None = None) -> None:
    """Store every plan item the question needs; the primary is the latest in the sequence.
    ``import_meta['required_plan_item_ids']`` mirrors the rows so the selection engine can check
    them without extra queries."""
    db.execute(delete(QuestionPlanItem).where(QuestionPlanItem.question_id == q.id))
    items = [db.get(LearningPlanItem, i) for i in dict.fromkeys(item_ids) if i]
    items = [i for i in items if i is not None and i.subject_id == q.subject_id]
    if not items:
        q.plan_item_id, q.topic_id = None, None
        meta = dict(q.import_meta or {})
        meta["required_plan_item_ids"] = []
        q.import_meta = meta
        return
    if primary_id is None or primary_id not in [i.id for i in items]:
        pool = [i for i in items if not i.is_assumed_knowledge] or items
        primary_id = max(pool, key=lambda i: i.position).id
    for it in items:
        db.add(QuestionPlanItem(question_id=q.id, plan_item_id=it.id, role="primary" if it.id == primary_id else "requires"))
    prim = db.get(LearningPlanItem, primary_id)
    q.plan_item_id, q.topic_id = prim.id, prim.topic_id
    meta = dict(q.import_meta or {})
    meta["required_plan_item_ids"] = [i.id for i in items]
    q.import_meta = meta


def required_items(db: Session, q: Question) -> list[LearningPlanItem]:
    rows = db.execute(select(QuestionPlanItem).where(QuestionPlanItem.question_id == q.id)).scalars().all()
    items = [r.plan_item for r in rows if r.plan_item is not None]
    if not items and q.plan_item_id:
        it = db.get(LearningPlanItem, q.plan_item_id)
        items = [it] if it else []
    return sorted(items, key=lambda i: i.position)


def locked_requirements(db: Session, q: Question) -> list[LearningPlanItem]:
    """Required plan items that would stop the question being served today."""
    return [i for i in required_items(db, q) if i.status == LOCKED or not i.active]


def official_outcomes(db: Session, subject_id: int) -> list[SyllabusOutcome]:
    """Outcomes usable for mapping: official ones once any exist (placeholders are excluded)."""
    rows = db.execute(select(SyllabusOutcome).where(SyllabusOutcome.subject_id == subject_id)).scalars().all()
    official = [o for o in rows if o.official]
    return official or []


def set_outcomes(db: Session, q: Question, codes: list[str]) -> list[SyllabusOutcome]:
    db.execute(delete(QuestionOutcome).where(QuestionOutcome.question_id == q.id))
    if not codes:
        q.syllabus_outcome_id = None
        return []
    rows = [o for o in official_outcomes(db, q.subject_id) if o.code in codes]
    for o in rows:
        db.add(QuestionOutcome(question_id=q.id, outcome_id=o.id))
    q.syllabus_outcome_id = rows[0].id if rows else None
    return rows


def first_hsc_year(db: Session, subject_id: int) -> int | None:
    v = db.execute(select(SyllabusVersion).where(SyllabusVersion.subject_id == subject_id, SyllabusVersion.current.is_(True))).scalars().first()
    return v.first_hsc_year if v else None


def apply_proposal(db: Session, q: Question, p: Proposal) -> QuestionMapping:
    """Write a proposal onto the question (never approving it) and record the mapping row."""
    set_required_items(db, q, [c.id for c in p.required])
    outs = set_outcomes(db, q, p.outcome_codes)
    q.relevance_status, q.relevance_score, q.mapping_confidence = p.relevance, p.relevance_score, p.confidence
    q.is_extension = p.is_extension
    if p.legal_fact_currency:
        q.legal_fact_currency = p.legal_fact_currency
    meta = dict(q.import_meta or {})
    meta.update({
        "mapping_state": "UNMAPPED" if p.unmapped else "MAPPED",
        "candidates": [{"id": c.id, "code": c.code, "title": c.title, "status": c.status, "score": s} for c, s in p.candidates],
        "student_rationale": p.student_rationale or meta.get("student_rationale"),
        "subtopic_cited": p.subtopic_cited,
        "skill_relevance": p.skill_relevance,
        "original_topic": p.original_topic,
        "outcome_codes": p.outcome_codes,
    })
    q.import_meta = meta
    prim = p.primary
    m = QuestionMapping(question_id=q.id, original_topic=p.original_topic, mapped_topic_id=q.topic_id,
                        focus_area=prim.topic_name if prim else None, outcome_id=outs[0].id if outs else None,
                        content_descriptor=p.content_descriptor, relevance_classification=p.relevance, relevance_score=p.relevance_score,
                        mapping_confidence=p.confidence, mapping_reason=p.reason.strip(), skill_relevance=p.skill_relevance,
                        legal_fact_currency=p.legal_fact_currency, mapped_by=p.mapped_by, review_status="pending")
    db.add(m)
    db.flush()
    return m
