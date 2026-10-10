"""Quotation verification for English responses (owner: english-logic).

Every quotation in a model answer, an AI-written answer or a student response can be checked
against the passage(s) it claims to quote. Matching is word-based and forgiving about
typography (curly vs straight quotes, dashes, line breaks, capitals, punctuation) but strict
about the words themselves: "improvement" does not match "improving".

Supported conventions inside a quotation:
* ellipsis (``...`` or ``…``) and ``/`` (a poetry line break) split it into segments; every
  segment must appear in the same passage, in order;
* ``[bracketed]`` words are the writer's own changes and are skipped (they split the quote).
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import asdict, dataclass

_QUOTE_CHARS = {"‘": "'", "’": "'", "‛": "'", "′": "'", "“": '"', "”": '"', "‟": '"', "″": '"',
                "«": '"', "»": '"'}
_DASHES = {"–": "-", "—": "-", "‒": "-", "−": "-", "‐": "-", "‑": "-"}
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")
# Text that is a reference to a text rather than a quotation from it.
_NOT_QUOTES = re.compile(r"^(text|extract|source|poem|passage)\s*[0-9a-z]?$", re.I)

STOPWORDS = set("""a about above after again against all also am an and any are as at be because been before being below between both but by
can could did do does doing down during each even ever every few for from further had has have having he her here hers herself him himself
his how i if in into is it its itself just like may me might more most much must my myself no nor not now of off on once only or other our
ours ourselves out over own same she should so some such than that the their theirs them themselves then there these they this those
through to too under until up upon very was we were what when where which while who whom why will with would yet you your yours yourself
yourselves one two three text texts writer writers poet poets speaker author reader readers passage extract shows show uses use used using
makes make made way ways also through effect effects suggests suggest reveals reveal conveys convey""".split())


def normalise(text: str) -> str:
    """Lower-case, NFKC, straight quotes, plain hyphens, single spaces."""
    s = unicodedata.normalize("NFKC", text or "")
    for a, b in {**_QUOTE_CHARS, **_DASHES}.items():
        s = s.replace(a, b)
    s = s.replace("…", "...")
    return re.sub(r"\s+", " ", s).strip().lower()


def tokens(text: str) -> list[str]:
    return _WORD.findall(normalise(text))


@dataclass
class Token:
    word: str
    start: int
    end: int


def _tokens_with_spans(text: str) -> tuple[str, list[Token]]:
    s = unicodedata.normalize("NFKC", text or "")
    for a, b in {**_QUOTE_CHARS, **_DASHES}.items():
        s = s.replace(a, b)
    return s, [Token(m.group(0).lower(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)*", s)]


# ------------------------------------------------------------------ extraction ---

_DOUBLE = re.compile(r'"([^"\n]{1,400}?)"')
# single quotes: the opening ' must not follow a letter/digit (so possessives and contractions are not
# openings); inner apostrophes are allowed between letters; the closing ' must not be followed by a letter.
_SINGLE = re.compile(r"(?<![A-Za-z0-9])'((?:[^'\n]|(?<=[A-Za-z])'(?=[A-Za-z])){1,400}?)'(?![A-Za-z0-9])")


def extract_quotes(text: str) -> list[str]:
    """Quoted fragments in ``text`` (double, curly or single quotation marks), in order."""
    s = unicodedata.normalize("NFKC", text or "")
    for a, b in _QUOTE_CHARS.items():
        s = s.replace(a, b)
    found: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    for m in _DOUBLE.finditer(s):
        found.append((m.start(), m.group(1)))
        taken.append((m.start(), m.end()))
    for m in _SINGLE.finditer(s):
        if any(a <= m.start() < b for a, b in taken):
            continue  # a 'quote within a quote' is checked as part of its outer quotation
        found.append((m.start(), m.group(1)))
    out = []
    for _, q in sorted(found):
        q = q.strip()
        if not tokens(q) or _NOT_QUOTES.match(q.strip(" .,;:")):
            continue
        out.append(q)
    return out


def _segments(quote: str) -> list[list[str]]:
    q = normalise(quote)
    q = re.sub(r"\[[^\]]*\]", "|", q)  # [changed words] are the writer's own
    parts = re.split(r"\.\.\.|\||/", q)
    return [t for t in (tokens(p) for p in parts) if t]


def _find(seq: list[str], hay: list[str], start: int = 0) -> int:
    n = len(seq)
    first = seq[0]
    for i in range(start, len(hay) - n + 1):
        if hay[i] == first and hay[i : i + n] == seq:
            return i
    return -1


# --------------------------------------------------------------- verification ---


@dataclass
class QuoteCheck:
    quote: str
    found: bool
    passage: int | None = None  # index of the passage the quotation was found in
    closest: str | None = None  # nearest wording in the passage when not found
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _closest(seg: list[str], passage_text: str) -> tuple[float, str | None]:
    shown, toks = _tokens_with_spans(passage_text)
    words = [t.word for t in toks]
    n = len(seg)
    if not words or not n:
        return 0.0, None
    target = " ".join(seg)
    best, best_span = 0.0, None
    for width in {max(1, n - 1), n, n + 1}:
        for i in range(0, max(1, len(words) - width + 1)):
            cand = " ".join(words[i : i + width])
            r = difflib.SequenceMatcher(None, target, cand, autojunk=False).ratio()
            if r > best:
                best, best_span = r, (i, min(len(toks), i + width) - 1)
    if best_span is None:
        return 0.0, None
    a, b = best_span
    return best, shown[toks[a].start : toks[b].end]


def verify_quote(quote: str, passages: list[str]) -> QuoteCheck:
    segs = _segments(quote)
    if not segs:
        return QuoteCheck(quote=quote, found=True, note="nothing to check")
    for idx, p in enumerate(passages):
        hay = tokens(p)
        pos, ok = 0, True
        for seg in segs:
            i = _find(seg, hay, pos)
            if i < 0:
                i = _find(seg, hay, 0)  # out-of-order segments still count as quoted, just not in order
                if i < 0:
                    ok = False
                    break
            pos = i + len(seg)
        if ok:
            return QuoteCheck(quote=quote, found=True, passage=idx)
    # not found: find the closest wording for the first segment that fails anywhere
    best_ratio, best_text = 0.0, None
    for seg in segs:
        if any(_find(seg, tokens(p)) >= 0 for p in passages):
            continue
        for p in passages:
            r, t = _closest(seg, p)
            if r > best_ratio:
                best_ratio, best_text = r, t
        break
    closest = best_text if best_ratio >= 0.6 else None
    note = (f"Not in the text as written. The text says “{closest}”." if closest
            else "These words do not appear in the text.")
    return QuoteCheck(quote=quote, found=False, closest=closest, note=note)


def verify_quotes(text: str, passages: list[str] | str) -> list[QuoteCheck]:
    """Check every quotation in ``text`` against ``passages`` (one string or a list, e.g. Text 1 and Text 2)."""
    if isinstance(passages, str):
        passages = [passages]
    passages = [p for p in passages if p]
    if not passages:
        return []
    return [verify_quote(q, passages) for q in extract_quotes(text)]


def summary(checks: list[QuoteCheck]) -> dict:
    found = [c for c in checks if c.found]
    return {"total": len(checks), "verified": len(found), "unverified": len(checks) - len(found),
            "texts": sorted({c.passage for c in found if c.passage is not None})}


# ------------------------------------------------------ evidence and relevance ---


def unquoted_phrases(text: str, passage: str, n: int = 4) -> int:
    """How many distinct ``n``-word runs from the passage appear in ``text`` OUTSIDE quotation
    marks (evidence embedded without quotation marks)."""
    stripped = text
    for q in extract_quotes(text):
        stripped = stripped.replace(q, " ")
    a, b = tokens(stripped), tokens(passage)
    if len(a) < n or len(b) < n:
        return 0
    grams = {tuple(b[i : i + n]) for i in range(len(b) - n + 1)}
    hits, i = 0, 0
    while i <= len(a) - n:
        g = tuple(a[i : i + n])
        if g in grams and not all(w in STOPWORDS for w in g):
            hits += 1
            i += n
        else:
            i += 1
    return hits


def content_words(text: str) -> set[str]:
    return {w for w in tokens(text) if len(w) >= 4 and w not in STOPWORDS and not w.isdigit()}


def _stem(w: str) -> str:
    for suf in ("ingly", "edly", "ing", "ed", "ly", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def relevance(text: str, passages: list[str] | str, question: str = "") -> float:
    """Share of the response's content words that come from the passage(s) or the question
    (0..1, stemmed). Off-topic answers score low; a genuine answer usually scores above 0.25."""
    if isinstance(passages, str):
        passages = [passages]
    words = content_words(text)
    if not words:
        return 0.0
    ref = {_stem(w) for w in content_words(" ".join(passages) + " " + (question or ""))}
    hits = sum(1 for w in words if _stem(w) in ref)
    return round(hits / len(words), 3)
