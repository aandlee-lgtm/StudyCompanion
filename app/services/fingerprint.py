"""Duplicate detection: a normalised-text fingerprint plus shingle (n-gram) similarity.

Exact duplicates share a fingerprint. Near-duplicates (e.g. the same trial question with
different numbering, or two template instances with the same numbers) are caught by
Jaccard similarity on word 3-grams."""
from __future__ import annotations

import hashlib
import re
import unicodedata

_WS = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^a-z0-9+\-*/^=().]+")
_QNUM = re.compile(r"^\s*(question\s*)?\d+\s*[.)]?\s*(\([a-z]\))?\s*", re.I)


def normalise_text(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "").lower()
    s = _QNUM.sub("", s)
    s = s.replace("\\(", " ").replace("\\)", " ").replace("\\", " ")
    s = _NON_WORD.sub(" ", s)
    return _WS.sub(" ", s).strip()


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalise_text(text).encode()).hexdigest()


def shingles(text: str, n: int = 3) -> set[str]:
    words = normalise_text(text).split()
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def similarity(a: str, b: str) -> float:
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


NEAR_DUPLICATE = 0.85
