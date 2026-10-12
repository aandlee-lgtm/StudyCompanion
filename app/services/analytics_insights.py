"""Rule-based interpretation of a student's results (owner: analytics).

Every rule states what it found, with the numbers and how many answers it is based on, and
only fires when there is enough evidence (minimum answers per group and a minimum gap), so a
statement such as "You are consistently strong at …" is only made when it is true of the data.
The wording follows the specification's examples (section 21): a specific strength, the
specific context in which marks are lost, and what to do next."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from app.services.analytics_data import DIFFICULTY_NAMES, SUBJECT_NAMES, Dataset, Fact, mean, pct

MIN_ANSWERS = 10  # below this nothing is interpreted
MIN_GROUP = 4  # minimum answers in each group that is compared
MIN_GAP = 0.20  # minimum difference between groups (20 percentage points)

APPLICATION_RE = re.compile(r"applicat|modelling|rates|motion|growth|decay|interest|loan|instalment|annuit|maximi|minimi|problems|pension",
                            re.I)

ENGLISH_ERRORS = {
    "technique identification without analysis": "your English responses identify techniques accurately, but analysis of how they shape "
                                                 "meaning remains less developed",
    "insufficient textual evidence": "your English responses make claims without enough precise, integrated textual evidence",
    "descriptive response": "your English responses tend to describe or retell the text rather than analyse how meaning is made",
    "weak thesis": "your English responses lack a clear thesis that answers the question and guides each paragraph",
    "poor comparison": "your comparative responses discuss the texts separately rather than comparing them point by point",
    "limited evaluation": "evaluation questions are answered without a clear, sustained judgement",
    "imprecise expression": "imprecise expression is costing marks: claims are vague where a precise verb or term is needed",
}
ENGLISH_NEXT = {
    "technique identification without analysis": "After naming a technique, add a sentence on what it suggests and how it shapes the "
                                                 "text's idea — that second step is where the higher marks are.",
    "insufficient textual evidence": "Support every claim with a short, embedded quotation and explain it.",
    "descriptive response": "Start each paragraph with an analytical claim about how meaning is made, not with what happens.",
    "weak thesis": "Write a one-sentence thesis that answers the question before you start, and link each paragraph back to it.",
    "poor comparison": "Use comparative connectives (whereas, similarly, in contrast) inside each paragraph.",
    "limited evaluation": "State your judgement in the first sentence and keep weighing evidence for it throughout.",
    "imprecise expression": "Replace general verbs (shows, uses) with precise ones (undermines, foreshadows, positions).",
}
LEGAL_ERRORS = {
    "missing authority": ("your Legal answers make relevant points but rarely support them with legislation, cases or other authority",
                          "Name a statute, case or report for each main point."),
    "outdated legislation": ("some answers rely on legislation that has been replaced or amended", "Check the evidence bank for the current law."),
    "weak judgement": ("your evaluations do not reach a clear judgement about effectiveness",
                       "State the extent (largely, partially, minimally effective) and justify it against criteria."),
    "description instead of evaluation": ("your answers describe the law instead of evaluating how effective it is",
                                          "Use criteria such as justice, protection of rights and resource efficiency to judge."),
    "insufficient contemporary evidence": ("your answers need more recent examples (media reports, law reform, cases)",
                                           "Add one contemporary example to each extended answer."),
    "poor use of cases": ("cases are named but not used to make a point", "Say what each case shows about the law, not just its name."),
    "failure to address directive verb": ("answers do not always do what the directive verb asks",
                                          "Underline the verb (Explain, Assess, Evaluate) and match its demand."),
}
FORM_ADVICE = {
    "poetry": "attend to how imagery, sound and line breaks shape meaning",
    "speech": "analyse how the speaker positions the audience",
    "prose fiction": "analyse narrative voice, perspective and structure",
    "memoir": "analyse the reflective voice and how memory is shaped",
    "personal essay": "analyse the reflective voice and the line of argument",
    "feature article": "analyse how language positions readers",
    "media": "analyse how visual and verbal features work together",
    "drama": "analyse dialogue and staging",
    "letter": "analyse voice, audience and purpose",
}
HIGHER_VERBS = {"analyse", "evaluate", "assess", "compare", "synthesise", "discuss", "justify", "to what extent"}
LOWER_VERBS = {"identify", "describe", "outline", "explain", "define", "state", "recall"}


@dataclass
class Insight:
    subject: str | None
    kind: str
    text: str
    basis: str  # what the statement is based on
    priority: float = 1.0
    tone: str = "info"  # good|warn|info

    @property
    def line(self) -> str:
        """The statement with its subject, for plain lists (summaries, reviews)."""
        label = SUBJECT_NAMES.get(self.subject) if self.subject else {"confidence": "Confidence", "retention": "Revision"}.get(self.kind)
        return f"{label}: {self.text[0].lower()}{self.text[1:]}" if label else self.text

    def as_dict(self) -> dict:
        return {"subject": self.subject, "kind": self.kind, "text": self.text, "line": self.line, "basis": self.basis, "tone": self.tone}


def _avg(facts: list[Fact]) -> float | None:
    return mean(f.frac for f in facts)


def _group(facts: list[Fact], key) -> dict:
    out: dict = defaultdict(list)
    for f in facts:
        k = key(f)
        if k is not None:
            out[k].append(f)
    return out


def _consistent(facts: list[Fact]) -> bool:
    """'Consistently' strong: at least 5 answers and at least 80% of them scored 60%+."""
    return len(facts) >= 5 and sum(1 for f in facts if f.frac >= 0.6) / len(facts) >= 0.8


def _n(n: int, word: str = "answer") -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


# ------------------------------------------------------------------ rules ---
def _item_gap(ds: Dataset, code: str, facts: list[Fact]) -> list[Insight]:
    by_code = {i.code: iid for iid, i in ds.items.items()}

    def topic(f: Fact):
        # Legal sub-areas (LS-CRIME-TRIAL, ...) are compared at topic level (LS-CRIME), as students think of them
        item = ds.items.get(f.plan_item_id)
        if item is not None and code == "LEGAL" and item.code.count("-") >= 2:
            return by_code.get("-".join(item.code.split("-")[:2]), f.plan_item_id)
        return f.plan_item_id

    groups = {k: v for k, v in _group(facts, topic).items() if len(v) >= MIN_GROUP}
    if len(groups) < 2:
        return []
    ranked = sorted(groups.items(), key=lambda kv: _avg(kv[1]))
    (weak_id, weak), (strong_id, strong) = ranked[0], ranked[-1]
    a, b = _avg(strong), _avg(weak)
    if a < 0.7 or a - b < MIN_GAP:
        return []
    word = "consistently strong" if _consistent(strong) else "stronger"
    text = (f"You are {word} on {ds.item_name(strong_id)} ({pct(a)}% across {_n(len(strong), 'question')}) "
            f"but lose marks on {ds.item_name(weak_id)} ({pct(b)}% across {len(weak)}).")
    return [Insight(code, "topic-gap", text, f"{len(strong) + len(weak)} answers", 3 + (a - b), "warn")]


def _maths_context(ds: Dataset, facts: list[Fact]) -> list[Insight]:
    """Mechanics versus the same mathematics embedded in worded / modelling problems."""
    def is_app(f: Fact) -> bool:
        item = ds.items.get(f.plan_item_id)
        name = (item.title if item else "") + " " + ds.area_name(f.area_id)
        return bool(APPLICATION_RE.search(name))
    app = [f for f in facts if is_app(f)]
    mech = [f for f in facts if not is_app(f)]
    if len(app) < MIN_GROUP or len(mech) < MIN_GROUP:
        return []
    a, b = _avg(mech), _avg(app)
    if a < 0.7 or a - b < 0.15:
        return []
    area = Counter(ds.area_name(f.area_id) for f in mech).most_common(1)[0][0]
    top_app = Counter(f.plan_item_id for f in app).most_common(1)[0][0]
    word = "consistently strong" if _consistent(mech) else "stronger"
    text = (f"You are {word} at {area.lower()} mechanics ({pct(a)}% across {len(mech)} questions) but lose marks when the "
            f"same ideas are embedded in worded or modelling problems such as {ds.item_name(top_app)} ({pct(b)}% across {len(app)}). "
            "Before calculating, write down what each quantity in the problem represents.")
    return [Insight("MATHS", "context", text, f"{len(app) + len(mech)} answers", 3.5 + (a - b), "warn")]


def _difficulty(code: str, facts: list[Fact]) -> list[Insight]:
    if code == "MATHS":
        g = _group(facts, lambda f: f.difficulty)
        lo, hi = g.get(1, []), g.get(3, [])
        if len(lo) >= 3 and len(hi) >= 3 and _avg(lo) - _avg(hi) >= 0.25:
            return [Insight(code, "difficulty",
                            f"You handle foundation questions well ({pct(_avg(lo))}%, {len(lo)} questions) but lose marks on "
                            f"challenging multi-step questions ({pct(_avg(hi))}%, {len(hi)}). Set out each stage on its own line so method "
                            "marks are earned even when the final answer slips.", f"{len(lo) + len(hi)} answers", 2.5, "warn")]
        return []
    if code == "ENGLISH":
        written = [f for f in facts if not f.mcq]
        short = [f for f in written if f.marks <= 3]
        long = [f for f in written if f.marks >= 5]
        if len(short) >= 3 and len(long) >= 3 and _avg(short) - _avg(long) >= MIN_GAP:
            return [Insight(code, "marks", f"Your short responses (2–3 marks) average {pct(_avg(short))}% but your 5–6 mark "
                            f"responses average {pct(_avg(long))}% ({len(long)} responses). Longer questions need a sustained argument "
                            "and more analysed evidence, not more points.", f"{len(short) + len(long)} responses", 2.4, "warn")]
        return []
    if code == "LEGAL":
        mcq = [f for f in facts if f.mcq]
        written = [f for f in facts if not f.mcq]
        if len(mcq) >= MIN_GROUP and len(written) >= MIN_GROUP and _avg(mcq) - _avg(written) >= MIN_GAP:
            return [Insight(code, "format", f"You answer multiple-choice questions well ({pct(_avg(mcq))}% across {len(mcq)}) "
                            f"but your written responses average {pct(_avg(written))}% ({len(written)}). The knowledge is there; the marks "
                            "are lost in applying it and supporting it with authority.", f"{len(mcq) + len(written)} answers", 2.4, "warn")]
    return []


def _english_forms(facts: list[Fact]) -> list[Insight]:
    groups = {k: v for k, v in _group([f for f in facts if f.category != "course"],
                                      lambda f: (f.form or "").strip().lower() or None).items() if len(v) >= 3}
    if len(groups) < 2:
        return []
    ranked = sorted(groups.items(), key=lambda kv: _avg(kv[1]))
    (wf, weak), (sf, strong) = ranked[0], ranked[-1]
    if _avg(strong) - _avg(weak) < MIN_GAP:
        return []
    advice = next((v for k, v in FORM_ADVICE.items() if k in wf), "analyse how the form itself shapes meaning")
    return [Insight("ENGLISH", "form", f"Your {wf} responses average {pct(_avg(weak))}% ({len(weak)} questions) compared with "
                    f"{pct(_avg(strong))}% for {sf} ({len(strong)}). With {wf}, {advice}.", f"{len(weak) + len(strong)} responses", 2.2, "warn")]


def _english_verbs(facts: list[Fact]) -> list[Insight]:
    def tier(f: Fact):
        v = (f.verb or "").strip().lower()
        if v in HIGHER_VERBS:
            return "higher"
        if v in LOWER_VERBS:
            return "lower"
        return None
    g = _group([f for f in facts if not f.mcq], tier)
    lo, hi = g.get("lower", []), g.get("higher", [])
    if len(lo) >= 3 and len(hi) >= 3 and _avg(lo) - _avg(hi) >= MIN_GAP:
        verbs = sorted({(f.verb or "").capitalize() for f in hi})
        return [Insight("ENGLISH", "verb", f"You do well when asked to identify or explain ({pct(_avg(lo))}%), but "
                        f"{'/'.join(verbs)} questions average {pct(_avg(hi))}% ({len(hi)} responses). These verbs ask how and how well "
                        "a text works, not just what it does.", f"{len(lo) + len(hi)} responses", 2.1, "warn")]
    return []


def _errors(code: str, facts: list[Fact], ds: Dataset) -> list[Insight]:
    pool = [f for f in facts if not f.skipped and (code == "MATHS" or not f.mcq)]
    if len(pool) < MIN_GROUP:
        return []
    counts = Counter(c for f in pool for c in f.errors)
    out: list[Insight] = []
    if code == "ENGLISH":
        for cat, n in counts.most_common():
            if cat in ENGLISH_ERRORS and n >= 3 and n / len(pool) >= 0.25:
                lead = ENGLISH_ERRORS[cat]
                out.append(Insight(code, "errors", f"{lead[0].upper()}{lead[1:]} (flagged in {n} of {len(pool)} responses). {ENGLISH_NEXT[cat]}",
                                   f"{len(pool)} responses", 3.2 + n / len(pool), "warn"))
                break
    elif code == "LEGAL":
        for cat, n in counts.most_common():
            if cat in LEGAL_ERRORS and n >= 3 and n / len(pool) >= 0.25:
                lead, nxt = LEGAL_ERRORS[cat]
                out.append(Insight(code, "errors", f"{lead[0].upper()}{lead[1:]} (flagged in {n} of {len(pool)} written answers). {nxt}",
                                   f"{len(pool)} answers", 3.1 + n / len(pool), "warn"))
                break
    else:
        tags = Counter(t for f in pool for t in f.error_tags)
        top = (tags or counts).most_common(1)
        if top and top[0][1] >= 3:
            cat, n = top[0]
            where = Counter(f.plan_item_id for f in pool if cat in f.errors or cat in f.error_tags).most_common(1)[0][0]
            slip = cat in ("sign", "sign error", "arithmetic", "careless error", "calculator error", "notation")
            advice = ("These are slips rather than misunderstandings — check each line as you write it." if slip else
                      "Revisit the underlying idea in the worked solutions before doing more questions.")
            out.append(Insight(code, "errors", f"Your most frequent error is '{cat}' ({n} times, most often in "
                               f"{ds.item_name(where)}). {advice}", f"{len(pool)} answers", 2.6, "warn"))
    return out


def _time(code: str, facts: list[Fact]) -> list[Insight]:
    timed = [f for f in facts if f.seconds and not f.skipped and f.est_minutes]
    if len(timed) < 6:
        return []
    ratios = sorted(f.seconds / 60 / f.est_minutes for f in timed)
    med = ratios[len(ratios) // 2]
    avg = _avg(timed)
    if med > 1.3:
        return [Insight(code, "time", f"You typically take about {round((med - 1) * 100)}% longer than the exam-style "
                        f"time for a question ({len(timed)} timed answers). Exam conditions will tighten this as the HSC approaches; "
                        "practise one question a day against the clock.", f"{len(timed)} answers", 1.8, "warn")]
    if med < 0.6 and avg is not None and avg < 0.6:
        return [Insight(code, "time", f"You finish questions well inside the exam-style time (about "
                        f"{round(med * 100)}% of it) but average {pct(avg)}%. Use the remaining time to check and develop your answers.",
                        f"{len(timed)} answers", 1.9, "warn")]
    return []


def _confidence(facts: list[Fact]) -> list[Insight]:
    out = []
    guesses = [f for f in facts if f.confidence == "guess" and not f.skipped]
    lucky = [f for f in guesses if f.frac >= 0.85]
    if len(lucky) >= 3:
        out.append(Insight(None, "confidence", f"{len(lucky)} of {len(guesses)} answers you marked 'Guess' were correct. "
                           "They are scheduled for earlier revision rather than counted as mastered.", f"{len(guesses)} answers", 1.2))
    sure = [f for f in facts if f.confidence in ("confident", "very_confident") and not f.skipped]
    wrong = [f for f in sure if f.frac < 0.5]
    if len(wrong) >= 3 and len(wrong) / max(1, len(sure)) >= 0.25:
        out.append(Insight(None, "confidence", f"On {len(wrong)} of {len(sure)} answers you felt confident about, you lost "
                           "most of the marks. Confident errors usually point to a misconception rather than a slip — review those in the "
                           "error journal first.", f"{len(sure)} answers", 2.0, "warn"))
    return out


def _trend(facts: list[Fact]) -> list[Insight]:
    days = sorted({f.day for f in facts})
    if len(days) < 4 or len(facts) < 20:
        return []
    mid = days[len(days) // 2]
    first = [f for f in facts if f.day < mid]
    second = [f for f in facts if f.day >= mid]
    if len(first) < 10 or len(second) < 10:
        return []
    a, b = _avg(first), _avg(second)
    da, db_ = mean(f.difficulty for f in first), mean(f.difficulty for f in second)
    harder = db_ - da >= 0.25
    if b - a >= 0.1:
        return [Insight(None, "trend", f"Overall your results improved across this period, from {pct(a)}% to {pct(b)}%"
                        + (" even though the questions became harder." if harder else "."), f"{len(facts)} answers", 1.5, "good")]
    if a - b >= 0.1:
        why = " The questions became harder over the period, which explains part of the dip." if harder else \
            " Check the weakest areas below — the dip is not explained by harder questions."
        return [Insight(None, "trend", f"Your results dipped across this period, from {pct(a)}% to {pct(b)}%.{why}", f"{len(facts)} answers",
                        2.2, "warn")]
    return []


def _retention(ds: Dataset, facts: list[Fact]) -> list[Insight]:
    reps = [f for f in facts if f.repeat]
    if len(reps) < 5:
        return []
    first: dict[int, Fact] = {}
    for f in ds.facts:
        first.setdefault(f.question_id, f)
    before = [first[f.question_id] for f in reps if first[f.question_id] is not f]
    a, b = _avg(before), _avg(reps)
    if a is None or b is None:
        return []
    if b - a >= 0.1:
        return [Insight(None, "retention", f"Revision is working: on {len(reps)} questions you met again you scored {pct(b)}%, up from "
                        f"{pct(a)}% the first time.", f"{len(reps)} repeats", 1.4, "good")]
    if a - b >= 0.1:
        return [Insight(None, "retention", f"Retention needs attention: on {len(reps)} questions you met again you scored {pct(b)}%, "
                        f"down from {pct(a)}% the first time. Revisit the worked solutions a few days after each session.",
                        f"{len(reps)} repeats", 2.3, "warn")]
    return []


def _skips(ds: Dataset, code: str, facts: list[Fact]) -> list[Insight]:
    sk = [f for f in facts if f.skipped]
    if len(sk) >= 3 and len(sk) / len(facts) >= 0.15:
        where = Counter(f.plan_item_id for f in sk).most_common(1)[0][0]
        return [Insight(code, "skips", f"You skipped {len(sk)} of {len(facts)} questions (most often in "
                        f"{ds.item_name(where)}). An attempt, even a partial one, earns marks and shows what to fix; skipped questions "
                        "come back sooner.", f"{len(facts)} questions", 2.0, "warn")]
    return []


def _length(ds: Dataset, code: str, facts: list[Fact]) -> list[Insight]:
    written = [f for f in facts if not f.auto and not f.skipped and not f.mcq and f.marks >= 4]
    models = model_words(ds, {f.question_id for f in written})
    pairs = [(f.words, models[f.question_id]) for f in written if models.get(f.question_id)]
    if len(pairs) < MIN_GROUP:
        return []
    w, m = mean(p[0] for p in pairs), mean(p[1] for p in pairs)
    if w < 0.5 * m:
        return [Insight(code, "length", f"Your 4+ mark responses average {round(w)} words; the Band 6 models for "
                        f"the same questions average {round(m)}. Length is not marks, but at this length there is little room for the "
                        "development the higher bands need.", f"{len(pairs)} responses", 1.7, "warn")]
    return []


def _reliability(facts: list[Fact]) -> list[Insight]:
    written = [f for f in facts if f.subject in ("ENGLISH", "LEGAL") and not f.auto and not f.skipped]
    est = [f for f in written if f.estimated]
    if len(written) >= MIN_GROUP and len(est) / len(written) >= 0.5:
        return [Insight(None, "reliability", f"{len(est)} of {len(written)} English and Legal written marks in this period are offline "
                        "estimates (no AI provider was configured). Treat those marks as a rough guide; the patterns in what was "
                        "missing are more reliable than the numbers.", f"{len(written)} responses", 0.5)]
    return []


def model_words(ds: Dataset, qids: set[int]) -> dict[int, int]:
    """Word counts of the stored Band 6 model answers (cached per page)."""
    from sqlalchemy import select

    from app.models import Question

    cache = ds.model_word_cache
    missing = [q for q in qids if q not in cache]
    if missing:
        for qid, text in ds.db.execute(select(Question.id, Question.model_answer).where(Question.id.in_(missing))).all():
            cache[qid] = len((text or "").split())
    return {q: cache.get(q, 0) for q in qids}


# ------------------------------------------------------------------ entry ---
def insights(ds: Dataset, facts: list[Fact], limit: int | None = None) -> list[Insight]:
    """Interpretations for ``facts`` (a window of counted answers), most important first."""
    if len(facts) < MIN_ANSWERS:
        return []
    out: list[Insight] = []
    by_subject = _group(facts, lambda f: f.subject)
    for code in SUBJECT_NAMES:
        fs = by_subject.get(code, [])
        if len(fs) < MIN_GROUP:
            continue
        if code == "MATHS":
            out += _maths_context(ds, fs)
        out += _item_gap(ds, code, fs)
        out += _difficulty(code, fs)
        if code == "ENGLISH":
            out += _english_forms(fs) + _english_verbs(fs)
        out += _errors(code, fs, ds)
        out += _time(code, fs)
        out += _skips(ds, code, fs)
        if code in ("ENGLISH", "LEGAL"):
            out += _length(ds, code, fs)
    out += _confidence(facts) + _trend(facts) + _retention(ds, facts) + _reliability(facts)
    out.sort(key=lambda i: -i.priority)
    return out[:limit] if limit else out


def not_enough_message(n: int) -> str:
    return (f"Not enough answers yet for a reliable interpretation ({n} so far; patterns are reported from {MIN_ANSWERS} answers, and "
            "each statement needs several answers in each group it compares). Complete a few sessions and check back.")


def difficulty_label(d: int) -> str:
    return DIFFICULTY_NAMES.get(d, str(d))
