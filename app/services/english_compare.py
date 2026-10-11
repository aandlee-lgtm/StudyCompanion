"""Point-by-point comparison of the student's OWN response with what the question needed
(owner: english-logic; owner request 2026-10-11 "English comparison feedback").

Each comparison item has the same shape whether it comes from the AI or is built offline:

    point         what the question needed (a checklist item, a criterion, or a check)
    status        "missing" | "weak" | "met"
    student_text  the student's own sentence, copied verbatim from the response ("" if none)
    issue         what is missing or weak in it
    why           why it matters for the mark
    try           a constructive example to try: a rewrite of their sentence or a short example
    try_kind      "rewrite" (built on their sentence) | "example" | "next_step"
    next_step     the authored next step for this question (offline), if different from ``try``
    model_example the closest sentence of the model answer (or plan line), to compare with
    source        "ai" | "self_mark" | "check"

AI items are validated: an item whose quoted student text is not verbatim in the response is
dropped (``validate_ai_items``). Offline items are built from guided self-marking: for every
unticked checklist item the student's closest sentence (a simple lexical match), the item, why it
matters, and the question's own next step / a sentence frame to try (``offline_items``)."""
from __future__ import annotations

import math
import re
import unicodedata

from app.marking import quotes

# Typography the student and the AI may write differently; the words themselves must match.
_TYPO = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."}

WHY = {
    "insufficient textual evidence": "Markers can only reward what they can see in the text: without precise, accurate evidence a claim stays an "
                                     "assertion, and the answer stays in the lower half of the ladder.",
    "technique identification without analysis": "Naming a technique earns little on its own. The higher levels reward explaining HOW the "
                                                  "words shape meaning or feeling, and why that matters to the question.",
    "descriptive response": "Retelling or describing shows you understood the text, but the marks above the middle go to explaining how and "
                            "why the writer creates meaning.",
    "poor comparison": "A comparison is marked on the relationship between the texts. Treating one text, or each text separately, is capped "
                       "below the top levels.",
    "limited evaluation": "This verb asks for a judgement. Without a clear, justified judgement the answer cannot reach the top level, however "
                          "good the analysis is.",
    "weak thesis": "At this mark value a sustained line of argument is what separates the top levels from sound ones: every point should "
                   "serve one clear answer to the question.",
    "imprecise expression": "Precise verbs and metalanguage show control; vague wording ('shows', 'uses') makes sound ideas read as general.",
    "telling not showing": "Craft marks reward implying feeling through action, detail and setting; naming the feeling tells the reader what "
                           "to think and reads as unskilled.",
    "uncontrolled tense or point of view": "Control of tense and point of view is one of the first things a marker notices; a slip breaks the "
                                           "reader's trust in the voice.",
    "reflection not linked to purpose": "A reflection earns marks for explaining deliberate choices and their effect on purpose, not for "
                                        "describing what you wrote.",
    "structure lacks purpose": "Structure is a craft choice: a withheld detail, a turn or a resonant ending shapes the reader's response; a "
                               "plain sequence of events does not.",
    "generic or clichéd detail": "Specific, unexpected detail is what makes writing feel controlled; familiar phrases make it feel generic.",
}


# ----------------------------------------------------------------- text tools ---


def _norm(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "")
    for a, b in _TYPO.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


_SENT_END = re.compile(r"(?<=[.!?…])[\"'”’)\]]*\s+|\n\s*")


def sentences(text: str) -> list[str]:
    """The response split into sentences, each a verbatim substring of ``text``."""
    out, pos = [], 0
    for m in _SENT_END.finditer(text or ""):
        end = m.start() + len(m.group(0).rstrip())  # keep closing quotation marks with the sentence
        chunk = text[pos:end].strip()
        if chunk:
            out.append(chunk)
        pos = m.end()
    tail = (text or "")[pos:].strip()
    if tail:
        out.append(tail)
    return [s for s in out if len(quotes.tokens(s)) >= 2]


def _stems(text: str) -> list[str]:
    return [quotes._stem(w) for w in quotes.content_words(text)]


def closest(target: str, candidates: list[str], min_score: float = 0.34) -> tuple[str | None, float]:
    """The candidate sentence sharing the most distinctive content words with ``target``.
    Words that occur in many candidates count for less (a simple idf)."""
    want = set(_stems(target))
    if not want or not candidates:
        return None, 0.0
    sets = [set(_stems(c)) for c in candidates]
    df = {w: sum(1 for s in sets if w in s) for w in want}
    best, best_score = None, 0.0
    for c, s in zip(candidates, sets):
        score = sum(1.0 / df[w] for w in want & s)
        if score > best_score:
            best, best_score = c, score
    norm = best_score / math.sqrt(len(want))
    return (best, round(norm, 3)) if norm >= min_score else (None, round(norm, 3))


def is_verbatim(quote: str, response: str) -> bool:
    """True when ``quote`` is copied from ``response`` word for word (typography, spacing and case
    may differ; '...' may join parts that appear in order). Needs at least three words."""
    q = _norm(quote).strip(" \"'")
    if len(quotes.tokens(q)) < 3:
        return False
    hay = _norm(response).lower()
    pos = 0
    for part in [p.strip(" ,;:") for p in q.lower().split("...")]:
        if not part:
            continue
        i = hay.find(part, pos)
        if i < 0:
            part2 = part.rstrip(".!?")  # a sentence quoted with or without its full stop
            i = hay.find(part2, pos) if part2 else -1
            if i < 0:
                return False
            part = part2
        pos = i + len(part)
    return True


def _open_end(sentence: str) -> str:
    """The sentence without its final full stop, so a clause can be added (keeps a closing quotation mark)."""
    s = sentence.rstrip()
    m = re.match(r"^(.*?)([.!?]+)([\"'”’]*)$", s, re.S)
    if m:
        return m.group(1) + m.group(3)
    return s


def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s and not s[:2].isupper() else s


def text_wording(quote: str, passages: list[str]) -> str | None:
    """The longest run of the student's quoted words that really is in a passage (at least two words
    and half the quotation), in the passage's own wording: the misquotation trimmed to what the
    text says."""
    want = quotes.tokens(quote)
    if len(want) < 2:
        return None
    for k in range(len(want), max(1, math.ceil(len(want) / 2)) - 1, -1):
        if k < 2:
            break
        for i in range(0, len(want) - k + 1):
            seq = want[i : i + k]
            if all(w in quotes.STOPWORDS for w in seq):
                continue
            for p in passages:
                shown, toks = quotes._tokens_with_spans(p)
                j = quotes._find(seq, [t.word for t in toks])
                if j >= 0:
                    return shown[toks[j].start : toks[j + k - 1].end]
    return None


_IRREGULAR = {"has": "have", "does": "do", "goes": "go"}
_NOT_VERBS = {"this", "its", "his", "hers", "yours", "thus", "both", "was", "as", "texts", "words", "details", "images", "ideas",
              "quotations", "examples", "techniques", "features", "paragraphs", "sentences", "verbs", "less", "always", "perhaps"}


def as_task(item: str) -> str | None:
    """'Explains what this shows…' -> 'explain what this shows…' (None when the item is not a verb phrase)."""
    m = re.match(r"([A-Za-z]+)(\b.*)$", (item or "").strip().rstrip("."), re.S)
    if not m:
        return None
    w, rest = m.group(1).lower(), m.group(2)
    if w in _NOT_VERBS or w.endswith(("ous", "us", "is", "ions", "ments", "ics", "ers", "ings", "ness")):
        return None
    if w in _IRREGULAR:
        base = _IRREGULAR[w]
    elif w.endswith("ies") and len(w) > 4:
        base = w[:-3] + "y"
    elif re.search(r"(ss|sh|ch|x|z)es$", w):
        base = w[:-2]
    elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        base = w[:-1]
    else:
        return None
    return base + rest


def _model_quote(sentence: str | None, passages: list[str]) -> str | None:
    """A verified quotation from a model sentence (never an invented one)."""
    if not sentence or not passages:
        return None
    for c in quotes.verify_quotes(sentence, passages):
        if c.found and 1 <= len(quotes.tokens(c.quote)) <= 12:
            return c.quote
    return None


# ------------------------------------------------------------------- frames ---


def frame(category: str, sentence: str | None, *, paired: bool = False, quote: str | None = None) -> tuple[str, str] | None:
    """A rewrite of the student's sentence with the missing move added as a frame to complete,
    or a short example to adapt. Square brackets mark what the student fills in."""
    if not sentence:
        return None
    s = _open_end(sentence)
    q = f"“{quote}”" if quote else "“[a short, exact quotation]”"
    frames = {
        "technique identification without analysis": f"{s}, which suggests [the idea or feeling] because [how these exact words create it].",
        "descriptive response": f"{s}; this matters because the writer [suggests / reveals …], and the [feature] makes the reader [feel / see …].",
        "insufficient textual evidence": f"{s}, as in {q}, which [what these words show].",
        "limited evaluation": f"{s}, and this is [highly / only partly] effective because [reason linked to the question].",
        "poor comparison": (f"{s}, whereas Text 2 [does what, through which feature], so both texts [shared idea] but [the key difference]."
                            if paired else f"{s}, whereas [the other text] [does what], so [similarity] but [difference]."),
        "weak thesis": f"Overall, the writer suggests that [your answer to the question in one clause]: {_lower_first(sentence.strip())}",
        "imprecise expression": f"{s} — now replace each general verb (shows, uses, says) with a precise one (implies, undercuts, intensifies, reframes).",
        "telling not showing": "Cut the named feeling and let one action or object carry it, e.g. [what the character does with their hands, "
                               "or what they notice] — keep the rest of your sentence.",
        "reflection not linked to purpose": f"{s}, which I chose so that the reader [effect], serving my purpose of [purpose].",
    }
    text = frames.get(category)
    if not text:
        return None
    return text, ("example" if category == "telling not showing" else "rewrite")


# ------------------------------------------------------------------ offline ---


def _best_step(item: str, next_steps: dict[str, str], mark: int, used: set[str]) -> str | None:
    """The authored next step that best matches this checklist item (at or above the student's level)."""
    steps = [(int(k), v) for k, v in next_steps.items() if str(k).isdigit() and v]
    if not steps:
        return None
    pool = [v for k, v in sorted(steps) if k >= mark and v not in used] or [v for _, v in sorted(steps) if v not in used]
    if not pool:
        return None
    hit, _ = closest(item, pool, min_score=0.2)
    return hit or (next_steps.get(str(mark)) if next_steps.get(str(mark)) not in used else None)


def offline_items(*, response: str, checklist: list[str], ticked: list[int], marks: int, final: int, raw: int, ladder: list[dict],
                  next_steps: dict[str, str], checks: dict, model_text: str | None, model_kind: str | None, passages: list[str],
                  paired: bool, response_type: str, category_of) -> list[dict]:
    """Comparison items from guided self-marking (no AI): deterministic checks first (they cap the
    mark), then every unticked checklist item, then what the student already does."""
    sents = sentences(response)
    model_sents = sentences(model_text or "") if model_text else []
    per = marks / max(1, len(checklist))
    worth = f" On this question each checklist item is worth about {round(per, 1):g} mark{'s' if per > 1.05 else ''}."
    out: list[dict] = []
    used_steps: set[str] = set()
    used_models: set[str] = set()

    # ---- checks the student cannot tick away
    for c in [c for c in checks.get("quotes", []) if not c.get("found")][:2]:
        sent = next((s for s in sents if c["quote"] in quotes.display_text(s)), None)
        right = text_wording(c["quote"], passages) or c.get("closest")
        fix = quotes.display_text(sent).replace(c["quote"], right, 1) if (sent and right) else None
        out.append({"point": "Quote the text exactly", "status": "weak", "student_text": sent or "",
                    "issue": f"“{c['quote']}” is not in the text as written." + (f" The text says “{right}”." if right else
                                                                                   " These words do not appear in the text."),
                    "why": "A marker checks quotations against the text; an inaccurate one cannot support your point and costs you credibility.",
                    "try": fix or "Copy the words exactly from the passage (use … to shorten, [ ] for your own changes).",
                    "try_kind": "rewrite" if fix else "next_step", "next_step": "", "model_example": "", "source": "check"})
    for w in checks.get("warnings", []):
        if w["code"] in ("no_evidence", "one_text", "wrong_text", "off_text", "short", "empty"):
            cat = {"no_evidence": "insufficient textual evidence", "one_text": "poor comparison"}.get(w["code"])
            sent = sents[0] if sents else ""
            mq_sent, _ = closest(w["message"] + " " + " ".join(checklist), model_sents) if model_sents else (None, 0)
            fr = frame(cat, sent, paired=paired, quote=_model_quote(mq_sent, passages)) if cat else None
            out.append({"point": {"no_evidence": "Use evidence from the text", "one_text": "Use evidence from BOTH texts",
                                  "wrong_text": "Use evidence from the text the question names", "off_text": "Answer about THIS text",
                                  "short": "Develop the answer to suit the mark value", "empty": "Write a response"}[w["code"]],
                        "status": "missing", "student_text": sent, "issue": w["message"],
                        "why": WHY.get(cat or "", "") + (f" This check caps the mark at {w['cap']}/{marks}." if w.get("cap") is not None else ""),
                        "try": fr[0] if fr else "", "try_kind": fr[1] if fr else "", "next_step": "", "model_example": mq_sent or "",
                        "source": "check"})
            if mq_sent:
                used_models.add(mq_sent)

    # ---- unticked checklist items
    tick = set(ticked)
    for i, item in enumerate(checklist):
        if i in tick:
            continue
        sent, score = closest(item, sents)
        cat = category_of(item, response_type, response)
        mex, _ = closest(item, model_sents, min_score=0.2) if model_sents else (None, 0)
        fr = frame(cat, sent, paired=paired, quote=_model_quote(mex, passages) if model_kind == "model" else None)
        step = _best_step(item, next_steps, final, used_steps)
        if step:
            used_steps.add(step)
        task = as_task(item)
        if sent:
            issue = ("You did not tick this item. This is your closest sentence, but it does not yet "
                     + (f"{task}." if task else f"do this: {_lower_first(item.rstrip('.'))}."))
        else:
            issue = "Nothing in your answer does this yet."
        if mex in used_models:
            mex = None
        if mex:
            used_models.add(mex)
        out.append({"point": item, "status": "missing", "student_text": sent or "", "issue": issue, "why": WHY.get(cat, "").strip() + worth,
                    "try": fr[0] if fr else (step or ""), "try_kind": fr[1] if fr else ("next_step" if step else ""),
                    "next_step": step if (fr and step) else "", "model_example": mex or "", "source": "self_mark", "category": cat})

    # ---- what the student already does (their own sentence as proof)
    for i in sorted(tick):
        if 0 <= i < len(checklist):
            sent, _ = closest(checklist[i], sents)
            out.append({"point": checklist[i], "status": "met", "student_text": sent or "", "issue": "", "why": "", "try": "",
                        "try_kind": "", "next_step": "", "model_example": "", "source": "self_mark"})
    return out


def pending_hints(response: str, checklist: list[str]) -> list[str]:
    """For each checklist item, the student's closest sentence (shown while they tick)."""
    sents = sentences(response)
    return [closest(item, sents)[0] or "" for item in checklist]


# ----------------------------------------------------------------------- AI ---


def validate_ai_items(items: list, response: str, passages: list[str]) -> tuple[list[dict], int]:
    """Keep the AI's comparison items whose quoted student text is verbatim in the response.
    An item with no quote is kept only when it says the point is missing altogether. Quotations
    from the passage inside 'try this' are checked too (flagged, not trusted)."""
    kept, dropped = [], 0
    for raw in items or []:
        it = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
        quote = (it.get("student_quote") or "").strip()
        status = (it.get("status") or "weak").strip().lower()
        status = status if status in ("missing", "weak", "met") else "weak"
        if quote and not is_verbatim(quote, response):
            dropped += 1
            continue
        if not quote and status != "missing":
            dropped += 1
            continue
        if not (it.get("point") or "").strip():
            dropped += 1
            continue
        tr = (it.get("try_this") or "").strip()
        bad = [c.quote for c in quotes.verify_quotes(tr, passages) if not c.found and not is_verbatim(c.quote, response)] if passages and tr else []
        kept.append({"point": it["point"].strip(), "status": status, "student_text": quote, "issue": (it.get("issue") or "").strip(),
                     "why": (it.get("why_it_matters") or "").strip(), "try": tr, "try_kind": "rewrite" if quote and tr else ("example" if tr else ""),
                     "try_unverified": bad, "next_step": "", "model_example": "", "source": "ai"})
    order = {"missing": 0, "weak": 0, "met": 1}
    kept.sort(key=lambda x: order[x["status"]])
    return kept[:8], dropped


def summary_text(items: list[dict], mark: float, marks: int) -> str:
    """A one-paragraph version for places that show plain text (and v1 payload readers)."""
    gaps = [i for i in items if i["status"] != "met"]
    met = [i for i in items if i["status"] == "met"]
    if not items:
        return ""
    parts = [f"{mark:g}/{marks}."]
    if met:
        parts.append(f"You already: {met[0]['point'][0].lower() + met[0]['point'][1:]}" + (f" (and {len(met) - 1} more)" if len(met) > 1 else "") + ".")
    if gaps:
        parts.append("To improve: " + "; ".join(g["point"].rstrip(".") for g in gaps[:3]) + ".")
    return " ".join(parts)
