"""Legal citations: find every authority a piece of text relies on and resolve it against the
student's evidence bank (audit legal-01/02/03).

``parse_citations(text)`` finds cases (``R v Smith``, ``DPP (NSW) v Smith``, ``Re Kerry (No 2)``,
``Mabo (No 2)``, with optional ``[2016] HCA 53`` / ``(1992) 175 CLR 1`` tails), legislation
(``Bail Act 2013 (NSW)``, ``the Bail Act``, ``LEPRA``), treaties (``Article 9 of the ICCPR``,
``Convention on the Rights of the Child``), reports and inquiries (``Royal Commission into ...``,
``the ALRC report Pathways to Justice``) and statistics (percentages, rates, BOCSAR/ABS figures).

``Bank`` holds the evidence items. Resolution is per item, never by substring of a joined
string: the normalised name (or an alias) must match exactly, ``(No N)`` must match, and the
year, jurisdiction and report citation must match when both sides record them.

Every citation gets a status:

- ``verified``        in the bank and checked within the re-check interval
- ``recheck_due``     in the bank, verified, but the check is older than the interval
- ``unverified``      in the bank but never checked against its source
- ``outdated``        in the bank and marked repealed / superseded
- ``not_in_bank``     no bank item matches: check it exists before relying on it
- ``no_source``       a statistic with no bank item cited in the same sentence
- ``sourced``         a statistic supported by a bank item in the same sentence
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

# ----------------------------------------------------------------------------- vocabulary ---

JURISDICTIONS = {
    "nsw": "nsw", "new south wales": "nsw", "cth": "cth", "commonwealth": "cth", "vic": "vic", "victoria": "vic",
    "qld": "qld", "queensland": "qld", "act": "act", "sa": "sa", "wa": "wa", "tas": "tas", "nt": "nt", "nz": "nz", "uk": "uk",
}
_JUR_RE = r"(?:NSW|Cth|Vic|Qld|ACT|SA|WA|Tas|NT|NZ|UK)"

# Abbreviations whose expansion the app is confident about. They resolve through the bank like
# the full name (the bank item does not need an alias for them).
ACRONYMS: dict[str, tuple[str, str]] = {
    "UDHR": ("treaty", "Universal Declaration of Human Rights"),
    "ICCPR": ("treaty", "International Covenant on Civil and Political Rights"),
    "ICESCR": ("treaty", "International Covenant on Economic, Social and Cultural Rights"),
    "CRC": ("treaty", "Convention on the Rights of the Child"),
    "CROC": ("treaty", "Convention on the Rights of the Child"),
    "UNCROC": ("treaty", "Convention on the Rights of the Child"),
    "CEDAW": ("treaty", "Convention on the Elimination of All Forms of Discrimination against Women"),
    "CERD": ("treaty", "International Convention on the Elimination of All Forms of Racial Discrimination"),
    "ICERD": ("treaty", "International Convention on the Elimination of All Forms of Racial Discrimination"),
    "CRPD": ("treaty", "Convention on the Rights of Persons with Disabilities"),
    "UNDRIP": ("treaty", "United Nations Declaration on the Rights of Indigenous Peoples"),
    "LEPRA": ("legislation", "Law Enforcement (Powers and Responsibilities) Act"),
    "YOA": ("legislation", "Young Offenders Act"),
    "CSPA": ("legislation", "Crimes (Sentencing Procedure) Act"),
}
# Organisations, courts and report series: never citations on their own.
ORGS = {"BOCSAR", "ABS", "AIHW", "ALRC", "AHRC", "NSWLRC", "LRC", "UN", "UNHRC", "OHCHR", "ICC", "ICJ", "HCA", "NSWCCA", "NSWSC",
        "NSWDC", "NSWLC", "CLR", "ALR", "NSWLR", "DPP", "ODPP", "NGO", "NGOS", "UNICEF", "AFP", "ASIO", "NSW", "HSC", "NESA", "USA",
        "UK", "EU", "AM", "PM", "OK", "TV", "ID", "DNA", "CCTV", "MP", "MPS", "QC", "SC", "KC", "JP", "CEO", "GDP", "COVID"}
STAT_ORGS = r"(?:BOCSAR|ABS|AIHW|Productivity Commission|Australian Bureau of Statistics|Bureau of Crime Statistics and Research)"

STOP_WORDS = {
    "Under", "The", "In", "Following", "However", "Overall", "According", "Although", "Whereas", "While", "When", "If", "As",
    "After", "Before", "This", "That", "These", "Those", "Since", "Because", "By", "For", "From", "With", "Without", "Despite",
    "Also", "Additionally", "Furthermore", "Moreover", "Similarly", "Thus", "Therefore", "Hence", "Consequently", "Further",
    "Section", "Sections", "Part", "Article", "Articles", "Schedule", "Clause", "See", "Unlike", "Like", "And", "But", "Or", "Yet",
    "Here", "There", "It", "Its", "On", "At", "To", "Of", "Into", "Through", "During", "Within", "Both", "Each", "Every",
    "Similarly", "Notably", "Importantly", "Recently", "Previously", "Today", "Currently", "First", "Second", "Third", "Finally",
    "Firstly", "Secondly", "Thirdly", "Lastly", "Ultimately", "A", "An", "Case", "Cases", "Recent", "Landmark", "Example",
}
CONNECTORS = {"of", "and", "the", "for", "on", "in", "to", "with", "against", "relating", "&", "into"}
_ROYAL = {"the queen": "r", "the king": "r", "regina": "r", "rex": "r", "r": "r", "queen": "r", "king": "r"}

_TOKEN = re.compile(r"\((?:[^()]|\([^()]*\))*\)|\[[^\[\]]*\]|[A-Za-z][A-Za-z'’\-]*|\d[\d,.]*|[^\sA-Za-z\d]")


@dataclass
class Citation:
    kind: str  # case | legislation | treaty | report | inquiry | statistic
    name: str  # as written (cleaned), e.g. "Bail Act 2013 (NSW)"
    key: str  # normalised comparison key without year / jurisdiction / number
    start: int = 0
    end: int = 0
    year: int | None = None
    jurisdiction: str | None = None
    number: int | None = None  # (No 2)
    report_cite: str | None = None  # "[2016] HCA 53" or "(1992) 175 CLR 1"
    pinpoint: str | None = None  # "s 61", "Article 9"
    acronym: str | None = None

    @property
    def span(self) -> tuple[int, int]:
        return (self.start, self.end)

    def as_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "year": self.year, "jurisdiction": self.jurisdiction, "number": self.number,
                "report_cite": self.report_cite, "pinpoint": self.pinpoint, "span": [self.start, self.end]}


# ----------------------------------------------------------------------------- helpers ---


def _norm(s: str) -> str:
    s = (s or "").replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-").lower()
    s = re.sub(r"[^a-z0-9()'&\- ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_party(p: str) -> str:
    p = _norm(p)
    p = re.sub(r"^the\s+(?!queen\b|king\b)", "", p)
    return _ROYAL.get(p, p)


def _jur(s: str | None) -> str | None:
    if not s:
        return None
    return JURISDICTIONS.get(s.strip("() ").lower())


def _tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(), m.start(), m.end()) for m in _TOKEN.finditer(text)]


def _is_cap(tok: str) -> bool:
    return bool(tok) and tok[0].isupper()


def _paren_is_name(tok: str) -> bool:
    """'(Powers and Responsibilities)' is part of a name; '(NSW)', '(1992)' and '(No 2)' are not."""
    inner = tok[1:-1].strip()
    if not inner or re.fullmatch(_JUR_RE, inner) or re.fullmatch(r"\d{4}", inner) or re.match(r"No\.?\s*\d", inner):
        return False
    return inner[0].isupper()


def _walk_back(text: str, end: int, allow_jur_paren: bool = False) -> int | None:
    """Start index of a capitalised name that ends at ``end`` (exclusive), or None."""
    toks = _tokens(text[:end])
    start = None
    pending: list[int] = []  # connector starts not yet confirmed by a capitalised word before them
    i = len(toks) - 1
    while i >= 0:
        tok, s, _e = toks[i]
        if tok.startswith("("):
            if _paren_is_name(tok) or (allow_jur_paren and start is None and re.fullmatch(r"\(" + _JUR_RE + r"\)", tok)):
                start, pending = s, []
                i -= 1
                continue
            break
        if tok[0].isalpha():
            if _is_cap(tok):
                if tok in STOP_WORDS and not tok.isupper():
                    break
                start, pending = s, []
            elif tok.lower() in CONNECTORS:
                pending.append(s)
            else:
                break
        else:
            break
        i -= 1
    return start


def _walk_forward(text: str, begin: int, allow_the_first: bool = False) -> tuple[int, int | None]:
    """End index of a capitalised name starting at ``begin``; also returns a '(No N)' number."""
    end, number = begin, None
    toks = [(t, s + begin, e + begin) for t, s, e in _tokens(text[begin:])]
    i, first, prev_end = 0, True, begin
    while i < len(toks):
        tok, s, e = toks[i]
        if not first and (s - prev_end > 1 or "\n" in text[prev_end:s]):  # a gap or a line break ends the name
            break
        prev_end = e
        if tok.startswith("("):
            m = re.fullmatch(r"\(No\.?\s*(\d+)\)", tok)
            if m and not first:
                number, end = int(m.group(1)), e
                i += 1
                continue
            if not first and (re.fullmatch(r"\(" + _JUR_RE + r"\)", tok) or _paren_is_name(tok)):
                end = e
                i += 1
                continue
            break
        if tok[0].isalpha():
            if _is_cap(tok):
                if first and tok == "The" and not allow_the_first:
                    break
                if not first and tok in STOP_WORDS and tok not in ("The",):
                    break
                end = e
            elif tok.lower() in CONNECTORS and not first:
                j = i + 1
                while j < len(toks) and toks[j][0].lower() in CONNECTORS and j - i < 3:  # "on the Rights of the Child"
                    j += 1
                nxt = toks[j][0] if j < len(toks) else ""
                if not (nxt and nxt[0].isalpha() and _is_cap(nxt) and nxt not in STOP_WORDS):
                    break
            else:
                break
        elif tok == "," and not first:
            nxt = toks[i + 1][0] if i + 1 < len(toks) else ""
            if not (nxt and nxt[0].isalpha() and _is_cap(nxt) and nxt not in STOP_WORDS):
                break
        else:
            break
        first = False
        i += 1
    return end, number


def _strip_leading_connectors(text: str, start: int, end: int) -> int:
    seg = text[start:end]
    m = re.match(r"(?:(?:the|of|and|for|on|in|to|with|against|into)\s+)+", seg)
    return start + (m.end() if m else 0)


# ----------------------------------------------------------------------------- parsing ---

_ACT = re.compile(r"\bAct\b(?:\s+(?P<year>1[6-9]\d\d|20\d\d))?(?:\s*\((?P<jur>" + _JUR_RE + r")\))?")
_V = re.compile(r"(?<=\S)\s+v\.?\s+(?=[A-Z\[])")
_TAIL = re.compile(
    r"\s*(?:\((?P<y1>1[6-9]\d\d|20\d\d)\)(?:\s+(?P<lr>\d+\s+[A-Z][A-Za-z]*\s+\d+))?|(?P<mnc>\[(?P<y2>1[6-9]\d\d|20\d\d)\]\s+[A-Z][A-Za-z]*\s+\d+))"
)
_RE = re.compile(r"\bRe\s+(?P<name>[A-Z][\w'’\-]*(?:\s+[A-Z][\w'’\-]*)*)(?:\s+\(No\.?\s*(?P<no>\d+)\))?")
_SHORT = re.compile(r"\b(?P<name>[A-Z][\w'’\-]+)\s+\(No\.?\s*(?P<no>\d+)\)")
_TREATY_KW = re.compile(r"\b(?:Convention|Covenant|Declaration|Protocol|Statute|Charter|Treaty)\b")
_ACRO = re.compile(r"\b(?P<a>[A-Z]{2,7})\b(?:\s+(?P<year>1[6-9]\d\d|20\d\d))?(?:\s*\((?P<jur>" + _JUR_RE + r")\))?")
_PIN_BEFORE = re.compile(r"(?:\b(?:[Ss]ection|[Ss]\.?|ss\.?)\s+(?P<s>\d+[A-Z]*)|\b(?:Article|[Aa]rt\.?)\s+(?P<a>\d+))(?:\([^)]*\))*\s+of\s+(?:the\s+)?$")
_PIN_AFTER = re.compile(r"^\s*,?\s*(?:(?:s|ss|section)\.?\s+(?P<s>\d+[A-Z]*)|(?:[Aa]rt(?:icle)?\.?)\s+(?P<a>\d+))")
_ROYAL_COMMISSION = re.compile(r"\bRoyal Commission\s+(?:into|on)\b")
_INQUIRY = re.compile(r"\b(?:[A-Z][\w'’\-]+\s+)*Inquiry\s+into\b")
_ORG_REPORT = re.compile(
    r"\b(?P<org>[A-Z]{2,8}|Productivity Commission|Law Reform Commission)(?:\s+(?P<y>(?:19|20)\d\d))?(?:'s)?\s+[Rr]eport\b"
    r"(?:\s*,?\s*(?:titled\s+|entitled\s+)?['‘\"“]?(?P<title>[A-Z][\w'’\-]*(?:\s+(?:to|of|and|the|in|for|on|into|[A-Z][\w'’\-]*))*)['’\"”]?)?"
    r"(?:\s*\((?P<y2>(?:19|20)\d\d)\))?"
)
_TITLED_REPORT = re.compile(r"\b(?P<title>[A-Z][\w'’\-]*(?:\s+(?:[A-Z][\w'’\-]*|of|and|the|into|on|for|to|in))*\s+Report)\b(?:\s*\((?P<y>(?:19|20)\d\d)\))?")
_SENTENCE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")
_STAT = re.compile(
    r"\d+(?:\.\d+)?\s?(?:%|per\s?cent\b|percent\b)|\bper\s+100[, ]?000\b|\b\d+(?:\.\d+)?\s+times\b|\b(?:doubled|tripled|trebled|halved)\b"
    r"|\b(?:rate|rates|number|numbers|proportion)\s+of\b[^.]*?\b\d[\d,]*\b(?!\s*\))"
)
_STAT_ORG_NUM = re.compile(STAT_ORGS + r"[^.]*?\b\d")


def _overlaps(spans: list[tuple[int, int]], s: int, e: int) -> bool:
    return any(s < b and e > a for a, b in spans)


def _pinpoint(text: str, start: int, end: int) -> str | None:
    m = _PIN_BEFORE.search(text[max(0, start - 40):start])
    if m:
        return f"s {m.group('s')}" if m.group("s") else f"Article {m.group('a')}"
    m = _PIN_AFTER.match(text[end:end + 30])
    if m:
        return f"s {m.group('s')}" if m.group("s") else f"Article {m.group('a')}"
    return None


def _act_key(name: str) -> str:
    n = re.sub(r"\s*\((?:" + _JUR_RE + r")\)\s*$", "", name)
    n = re.sub(r"\s+(?:1[6-9]\d\d|20\d\d)\s*$", "", n)
    return _norm(n)


def _treaty_key(name: str) -> str:
    n = re.sub(r"\s*\(\d{4}\)\s*$", "", name)
    return _norm(re.sub(r"^the\s+", "", n, flags=re.I))


def _case_key(p1: str, p2: str) -> str:
    return f"{_norm_party(p1)} v {_norm_party(p2)}"


def _parse_legislation(text: str, taken: list[tuple[int, int]]) -> list[Citation]:
    out = []
    for m in _ACT.finditer(text):
        start = _walk_back(text, m.start())
        if start is None:
            continue
        start = _strip_leading_connectors(text, start, m.start())
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’\-]*", text[start:m.start()]) if _is_cap(w)]
        if not words:
            continue
        name = text[start:m.end()].strip()
        out.append(Citation("legislation", name, _act_key(text[start:m.start()] + "Act"), start, m.end(),
                            year=int(m.group("year")) if m.group("year") else None, jurisdiction=_jur(m.group("jur")),
                            pinpoint=_pinpoint(text, start, m.end())))
        taken.append((start, m.end()))
    return out


def _parse_cases(text: str, taken: list[tuple[int, int]]) -> list[Citation]:
    out = []
    for m in _V.finditer(text):
        s1 = _walk_back(text, m.start(), allow_jur_paren=True)
        if s1 is None:
            continue
        for a, b in taken:  # never reach back into an Act already found ("the Bail Act 1978 (NSW) and Smith v Jones")
            if a < m.start() and b > s1:
                s1 = b
        s1 = _strip_leading_connectors(text, s1 + (len(text[s1:m.start()]) - len(text[s1:m.start()].lstrip())), m.start())
        p1 = text[s1:m.start()].strip()
        if not p1 or not re.search(r"[A-Z]", p1[0]):
            continue
        e2, number = _walk_forward(text, m.end(), allow_the_first=True)
        p2 = text[m.end():e2].strip()
        p2 = re.sub(r"\s*\(No\.?\s*\d+\)\s*$", "", p2)
        if not p1 or not p2 or not re.search(r"[A-Za-z]", p2) or (p2 == "The"):
            continue
        end, year, rc = e2, None, None
        while True:
            t = _TAIL.match(text, end)
            if not t:
                break
            if t.group("mnc"):
                rc, year = re.sub(r"\s+", " ", t.group("mnc")), year or int(t.group("y2"))
            else:
                year = int(t.group("y1"))
                if t.group("lr"):
                    rc = f"({year}) " + re.sub(r"\s+", " ", t.group("lr"))
            end = t.end()
        if _overlaps(taken, s1, end):
            continue
        name = text[s1:end].strip()
        out.append(Citation("case", name, _case_key(p1, p2), s1, end, year=year, number=number, report_cite=rc,
                            jurisdiction=None, pinpoint=None))
        taken.append((s1, end))
    for m in _RE.finditer(text):
        if _overlaps(taken, m.start(), m.end()):
            continue
        out.append(Citation("case", m.group().strip(), "re " + _norm(m.group("name")), m.start(), m.end(),
                            number=int(m.group("no")) if m.group("no") else None))
        taken.append((m.start(), m.end()))
    for m in _SHORT.finditer(text):
        if _overlaps(taken, m.start(), m.end()) or m.group("name") in STOP_WORDS:
            continue
        out.append(Citation("case", m.group().strip(), _norm_party(m.group("name")), m.start(), m.end(), number=int(m.group("no")),
                            acronym="short"))
        taken.append((m.start(), m.end()))
    return out


def _parse_treaties(text: str, taken: list[tuple[int, int]]) -> list[Citation]:
    out = []
    for m in _TREATY_KW.finditer(text):
        if _overlaps(taken, m.start(), m.end()):
            continue
        s = _walk_back(text, m.start())
        s = m.start() if s is None else _strip_leading_connectors(text, s, m.start())
        e, _ = _walk_forward(text, m.start())
        name = text[s:e].strip().rstrip(",")
        caps = [w for w in re.findall(r"[A-Za-z][A-Za-z'’\-]*", name) if _is_cap(w)]
        if len(caps) < 2:
            continue
        y = re.match(r"\s*\((\d{4})\)", text[e:])
        end = e + (y.end() if y else 0)
        out.append(Citation("treaty", name, _treaty_key(name), s, end, year=int(y.group(1)) if y else None,
                            pinpoint=_pinpoint(text, s, end)))
        taken.append((s, end))
    return out


def _parse_acronyms(text: str, taken: list[tuple[int, int]], extra: Iterable[str] = ()) -> list[Citation]:
    out, extra = [], {a for a in extra if a.isupper()}
    for m in _ACRO.finditer(text):
        a = m.group("a")
        if a in ORGS or _overlaps(taken, m.start(), m.end()):
            continue
        known = a in ACRONYMS or a in extra
        generic = bool(m.group("year") or m.group("jur"))  # "YOA 1997 (NSW)", "the CSPA (NSW)"
        if not (known or generic):
            continue
        kind, full = ACRONYMS.get(a, ("legislation", a))
        key = _act_key(full) if kind == "legislation" else _treaty_key(full)
        out.append(Citation(kind, m.group().strip(), key, m.start(), m.end(), year=int(m.group("year")) if m.group("year") else None,
                            jurisdiction=_jur(m.group("jur")), acronym=a, pinpoint=_pinpoint(text, m.start(), m.end())))
        taken.append((m.start(), m.end()))
    return out


def _parse_reports(text: str, taken: list[tuple[int, int]]) -> list[Citation]:
    out = []
    for rx, kind in ((_ROYAL_COMMISSION, "inquiry"), (_INQUIRY, "inquiry")):
        for m in rx.finditer(text):
            if _overlaps(taken, m.start(), m.end()):
                continue
            e, _ = _walk_forward(text, m.end() + 1) if m.end() < len(text) and text[m.end()] == " " else (m.end(), None)
            e = max(e, m.end())
            y = re.match(r"\s*\((\d{4})\)", text[e:])
            end = e + (y.end() if y else 0)
            name = text[m.start():e].strip()
            out.append(Citation(kind, name, _norm(name), m.start(), end, year=int(y.group(1)) if y else None))
            taken.append((m.start(), end))
    for m in _ORG_REPORT.finditer(text):
        if _overlaps(taken, m.start(), m.end()):
            continue
        title = m.group("title")
        year = m.group("y") or m.group("y2")
        name = title or f"{m.group('org')}{' ' + m.group('y') if m.group('y') else ''} report"
        out.append(Citation("report", name.strip(), _norm(title or f"{m.group('org')} report"), m.start(), m.end(),
                            year=int(year) if year else None, acronym=m.group("org")))
        taken.append((m.start(), m.end()))
    for m in _TITLED_REPORT.finditer(text):
        s = _strip_leading_connectors(text, m.start(), m.end())
        if _overlaps(taken, s, m.end()):
            continue
        words = re.findall(r"[A-Za-z][A-Za-z'’\-]*", m.group("title"))
        if len(words) < 2 or words[0] in STOP_WORDS:
            continue
        out.append(Citation("report", m.group("title"), _norm(m.group("title")), s, m.end(), year=int(m.group("y")) if m.group("y") else None))
        taken.append((s, m.end()))
    return out


def _parse_statistics(text: str, cites: list[Citation]) -> list[Citation]:
    out = []
    for m in _SENTENCE.finditer(text):
        sent = m.group()
        if not (_STAT.search(sent) or _STAT_ORG_NUM.search(sent)):
            continue
        # ignore numbers that are only parts of citations (years, report pages, section numbers)
        s, e = m.start(), m.end()
        masked = list(sent)
        for c in cites:
            if c.start < e and c.end > s:
                for i in range(max(c.start, s), min(c.end, e)):
                    masked[i - s] = " "
        if not (_STAT.search("".join(masked)) or _STAT_ORG_NUM.search("".join(masked))):
            continue
        out.append(Citation("statistic", sent.strip(), _norm(sent), s, e))
    return out


def parse_citations(text: str, extra_acronyms: Iterable[str] = ()) -> list[Citation]:
    """Every citation in ``text``, in order of appearance."""
    text = text or ""
    taken: list[tuple[int, int]] = []
    cites = _parse_legislation(text, taken)
    cites += _parse_cases(text, taken)
    cites += _parse_treaties(text, taken)
    cites += _parse_acronyms(text, taken, extra_acronyms)
    cites += _parse_reports(text, taken)
    cites.sort(key=lambda c: c.start)
    cites += _parse_statistics(text, cites)
    cites.sort(key=lambda c: (c.start, c.kind == "statistic"))
    return cites


def parse_title(title: str) -> Citation | None:
    """Parse a bank item's own title (or alias) into a citation, if it has a recognisable form."""
    cs = [c for c in parse_citations(title) if c.kind != "statistic"]
    if not cs:
        return None
    c = max(cs, key=lambda c: c.end - c.start)
    if c.end - c.start < len(title.strip()) * 0.6:
        return None
    return c


# ----------------------------------------------------------------------------- the bank ---

TYPE_KIND = {"legislation": "legislation", "case": "case", "treaty": "treaty", "report": "report", "inquiry": "inquiry",
             "law_reform": "report", "media": "report", "issue": "report", "statistic": "report", "institution": "report"}


@dataclass
class BankItem:
    id: int | None
    title: str
    item_type: str
    status: str = "unknown"
    last_verified: date | None = None
    aliases: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    date: str | None = None
    jurisdiction: str | None = None
    source_url: str | None = None
    source: str | None = None
    summary: str = ""
    sub_area: str | None = None
    parsed: list[Citation] = field(default_factory=list)  # title + aliases, parsed
    keys: set[str] = field(default_factory=set)  # normalised title and aliases (plain strings)
    title_cite: Citation | None = None  # the title itself, parsed

    @property
    def year(self) -> int | None:
        for c in self.parsed:
            if c.year:
                return c.year
        m = re.search(r"\b(1[6-9]\d\d|20\d\d)\b", self.date or "")
        return int(m.group(1)) if m else None

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "item_type": self.item_type, "status": self.status,
                "verified": self.last_verified.isoformat() if self.last_verified else None, "date": self.date,
                "jurisdiction": self.jurisdiction, "source_url": self.source_url, "source": self.source,
                "superseded_by": self.superseded_by, "sub_area": self.sub_area, "summary": self.summary}


def _as_date(v: Any) -> date | None:
    if v in (None, "", "UNVERIFIED"):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def make_item(row: Any) -> BankItem:
    """A BankItem from a LegalEvidence row or a dict with the same field names."""
    g = (lambda k, d=None: row.get(k, d)) if isinstance(row, dict) else (lambda k, d=None: getattr(row, k, d))
    verified = g("last_verified_date") if g("last_verified_date") is not None else g("verified")
    it = BankItem(id=g("id"), title=g("title"), item_type=g("item_type") or g("type") or "media", status=g("status") or "unknown",
                  last_verified=_as_date(verified), aliases=list(g("aliases") or []), superseded_by=g("superseded_by"), date=g("date"),
                  jurisdiction=g("jurisdiction"), source_url=g("source_url"), source=g("source"), summary=g("summary") or "",
                  sub_area=g("sub_area"))
    it.title_cite = parse_title(it.title)
    for name in [it.title, *it.aliases]:
        it.keys.add(_norm(name))
        it.keys.add(_treaty_key(name))
        p = parse_title(name)
        if p is not None:
            it.parsed.append(p)
        elif name.isupper() and 2 <= len(name) <= 8:
            it.parsed.append(Citation(TYPE_KIND.get(it.item_type, "report"), name, _norm(name), acronym=name))
    return it


class Bank:
    """The evidence bank used for resolution: always the WHOLE bank (legal-02)."""

    def __init__(self, items: Iterable[Any]):
        self.items = [i if isinstance(i, BankItem) else make_item(i) for i in items]
        self.by_title = {i.title: i for i in self.items}

    @classmethod
    def from_db(cls, db) -> "Bank":
        from sqlalchemy import select

        from app.models import LegalEvidence

        return cls(db.execute(select(LegalEvidence)).scalars().all())

    def alias_acronyms(self) -> set[str]:
        return {a for i in self.items for a in i.aliases if a.isupper() and 2 <= len(a) <= 8}

    def get(self, title: str | None) -> BankItem | None:
        if not title:
            return None
        if title in self.by_title:
            return self.by_title[title]
        n = _norm(title)
        return next((i for i in self.items if n in i.keys), None)


# ----------------------------------------------------------------------------- resolution ---


@dataclass
class Resolution:
    citation: Citation
    status: str
    item: BankItem | None = None
    note: str = ""
    near: BankItem | None = None  # a bank item with the same name but a different year / number
    possibly_outdated: bool = False

    def as_dict(self) -> dict:
        return {"text": self.citation.name, "kind": self.citation.kind, "status": self.status, "note": self.note,
                "item": self.item.as_dict() if self.item else None, "near": self.near.title if self.near else None,
                "possibly_outdated": self.possibly_outdated, "pinpoint": self.citation.pinpoint, "label": chip_label(self)}


def recheck_days(item_type: str, settings: dict | None = None) -> int:
    s = settings or {}
    if item_type == "legislation":
        return int(s.get("legal_recheck_days_legislation", 90))
    if item_type == "media":
        return int(s.get("legal_recheck_days_media", 180))
    return int(s.get("legal_recheck_days_other", 365))


def item_status(item: BankItem, today: date, settings: dict | None = None) -> str:
    if item.status in ("repealed", "superseded"):
        return "outdated"
    if item.last_verified is None:
        return "unverified"
    if (today - item.last_verified).days > recheck_days(item.item_type, settings):
        return "recheck_due"
    return "verified"


def _compatible(c: Citation, p: Citation, item_year: int | None = None, item_jur: str | None = None) -> tuple[bool, str]:
    """Does citation ``c`` refer to the item whose parsed title/alias is ``p``? (False, reason) if
    the names agree but a year / number / jurisdiction / report citation contradicts. A yearless
    alias ("Bail Act") is checked against the item's own year, so it never admits another year."""
    p_year, p_jur = p.year or item_year, p.jurisdiction or item_jur
    if c.year and p_year and c.year != p_year:
        return False, "year"
    if c.jurisdiction and p_jur and c.jurisdiction != p_jur:
        return False, "jurisdiction"
    if c.kind == "case":
        if c.number is not None and c.number != p.number:
            return False, "number"
        if c.report_cite and p.report_cite and c.report_cite.startswith("[") == p.report_cite.startswith("[") and _norm(c.report_cite) != _norm(p.report_cite):
            return False, "citation"
    return True, ""


def _candidates(c: Citation, bank: Bank) -> list[tuple[BankItem, Citation | None]]:
    out = []
    for it in bank.items:
        if c.kind in ("report", "inquiry"):
            if it.item_type in ("legislation", "case", "treaty"):
                continue
            k = c.key
            if k and len(k.split()) >= 2 and any(k == key or (len(key.split()) >= 2 and (k in key or key in k)) for key in it.keys):
                out.append((it, None))
            elif c.acronym and any(a == c.acronym for a in it.aliases) and (not c.year or c.year == it.year):
                out.append((it, None))
            continue
        for p in it.parsed:
            if c.kind == "case" and c.acronym == "short":  # "Mabo (No 2)": first party + number
                if p.kind == "case" and p.key.split(" v ")[0] == c.key and p.number == c.number:
                    out.append((it, p))
                elif p.kind == "case" and p.acronym == "short" and p.key == c.key and p.number == c.number:
                    out.append((it, p))
                continue
            if c.acronym and c.acronym in it.aliases:
                out.append((it, p))
                break
            if p.kind == c.kind and p.key == c.key:
                out.append((it, p))
            elif c.kind == "legislation" and p.kind == "legislation" and p.acronym and p.acronym == c.acronym:
                out.append((it, p))
    # de-duplicate per item, keeping the first parsed form
    seen, uniq = set(), []
    for it, p in out:
        if it.title not in seen:
            seen.add(it.title)
            uniq.append((it, p))
    return uniq


def resolve_citation(c: Citation, bank: Bank, today: date, settings: dict | None = None) -> Resolution:
    cands = _candidates(c, bank)
    ok: list[BankItem] = []
    near: BankItem | None = None
    reason = ""
    for it, p in cands:
        if p is None:
            ok.append(it)
            continue
        tp = it.title_cite
        y, j = (tp.year or it.year, tp.jurisdiction) if tp else (it.year, None)
        good, why = _compatible(c, p, y, j)
        if good:
            ok.append(it)
        else:
            near, reason = near or it, reason or why
    if ok:
        ok.sort(key=lambda i: (i.status in ("repealed", "superseded"), i.last_verified is None))
        it = ok[0]
        st = item_status(it, today, settings)
        note = ""
        if st == "outdated":
            note = f"{it.title} is recorded in your evidence bank as {it.status}" + (f"; it was replaced by {it.superseded_by}." if it.superseded_by else ".")
        elif c.kind == "case" and c.number is None and any(p.number for p in it.parsed):
            note = f"Cite it in full: {it.title}."
        return Resolution(c, st, it, note)
    note = f"{c.name} is not in your evidence bank. Check that it exists before using it."
    outdated = False
    if near is not None:
        if reason == "year" and c.kind == "legislation" and near.year and c.year and c.year < near.year and near.status not in ("repealed", "superseded"):
            outdated = True
            note = (f"Possible issue — verify: you cite the {c.name}, but your evidence bank lists the {near.title}. "
                    f"Check whether the {c.year} Act has been repealed or replaced.")
        elif reason == "number":
            note = f"{c.name} is not in your evidence bank (your bank has {near.title}). Check the case name and number."
        else:
            note = f"{c.name} does not match your evidence bank ({reason} differs from {near.title}). Check it before using it."
    return Resolution(c, "not_in_bank", None, note, near=near, possibly_outdated=outdated)


def resolve(text_or_citations: str | list[Citation], bank: Bank, today: date, settings: dict | None = None) -> list[Resolution]:
    cites = parse_citations(text_or_citations, bank.alias_acronyms()) if isinstance(text_or_citations, str) else text_or_citations
    authorities = [resolve_citation(c, bank, today, settings) for c in cites if c.kind != "statistic"]
    out = list(authorities)
    for c in cites:
        if c.kind != "statistic":
            continue
        inside = [r for r in authorities if r.citation.start >= c.start and r.citation.end <= c.end and r.item is not None]
        if inside:
            out.append(Resolution(c, "sourced", inside[0].item, f"Supported by {inside[0].item.title}."))
        else:
            out.append(Resolution(c, "no_source", None, "This statistic has no source from your evidence bank. "
                                  "Add the report it comes from to the bank, or leave the figure out."))
    out.sort(key=lambda r: r.citation.start)
    return out


def chip_label(r: Resolution) -> str:
    if r.status == "verified":
        return f"verified {r.item.last_verified:%d %b %Y}"
    if r.status == "recheck_due":
        return f"re-check due (last checked {r.item.last_verified:%d %b %Y})"
    if r.status == "unverified":
        return "in your bank, not yet verified"
    if r.status == "outdated":
        return f"outdated: {r.item.status}" if r.item else "outdated"
    if r.status == "not_in_bank":
        return "possibly outdated: check it" if r.possibly_outdated else "not in your bank: check it exists"
    if r.status == "no_source":
        return "statistic without a source"
    if r.status == "sourced":
        return "statistic with a bank source"
    return r.status


CHIP_CLASS = {"verified": "good", "recheck_due": "warn", "unverified": "warn", "outdated": "bad", "not_in_bank": "bad",
              "no_source": "", "sourced": "good"}


def unique(resolutions: Iterable[Resolution]) -> list[Resolution]:
    """One resolution per cited thing (the first mention), statistics kept individually."""
    seen, out = set(), []
    for r in resolutions:
        k = (r.item.title if r.item else None) or (r.citation.kind, _norm(r.citation.name))
        if r.citation.kind == "statistic":
            k = ("stat", r.citation.start, r.citation.name)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def audit(text: str, bank: Bank, today: date, settings: dict | None = None) -> list[dict]:
    """JSON-ready citation audit of ``text`` (one entry per distinct citation)."""
    return [r.as_dict() for r in unique(resolve(text, bank, today, settings))]


def currency(resolutions: Iterable[Resolution], today: date) -> dict:
    """'Current information checked' computed from the items actually cited (legal-03): the OLDEST
    verification date among cited bank items, plus which cited items are unverified or due."""
    items: dict[str, BankItem] = {}
    for r in resolutions:
        if r.item is not None and r.citation.kind != "statistic":
            items.setdefault(r.item.title, r.item)
    statuses = {t: item_status(i, today) for t, i in items.items()}
    verified = [i.last_verified for i in items.values() if i.last_verified]
    return {
        "checked": min(verified).isoformat() if verified else None,
        "cited": len(items),
        "verified_count": len(verified),
        "unverified": sorted(t for t, i in items.items() if i.last_verified is None),
        "recheck_due": sorted(t for t, s in statuses.items() if s == "recheck_due"),
        "outdated": sorted(t for t, s in statuses.items() if s == "outdated"),
        "as_at": today.isoformat(),
    }


def redact(text: str, resolutions: Iterable[Resolution]) -> tuple[str, list[str]]:
    """Replace authorities that are not in the bank with a visible marker (AI output only)."""
    removed: list[str] = []
    out = text
    for r in sorted((r for r in resolutions if r.status == "not_in_bank" and r.citation.kind in ("case", "legislation", "treaty")),
                    key=lambda r: -r.citation.start):
        c = r.citation
        out = out[:c.start] + "[authority removed: not in your evidence bank]" + out[c.end:]
        removed.append(c.name)
    return out, removed[::-1]
