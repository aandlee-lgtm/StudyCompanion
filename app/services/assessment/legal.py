"""Legal Studies specifics for written marking (owner: legal-logic).

- Offline: the estimate is rebuilt on resolved citations and the question's required elements
  (app.services.legal_marking; audit legal-04/05/15): invented or outdated authorities are never
  rewarded, and feedback carries all ten section-9 elements deterministically.
- With AI: every authority in the AI's text is resolved against the WHOLE evidence bank;
  suggestions become bank cards or are listed as 'not in your bank'; non-bank authorities in an
  AI model answer are redacted; corrections must cite a bank item or say 'Possible issue — verify:'
  (legal-13/14).
- Both: the model answer is labelled by its real provenance (legal-06) and 'Current information
  checked' is computed from the items actually shown (legal-03)."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.schemas import Criterion, ErrorItem, MarkingResult
from app.models import LearningPlanItem, LegalEvidence, LegalEvidenceTopic, Question
from app.models.common import ORIGIN_ADAPTED, ORIGIN_HISTORICAL, ORIGIN_SAMPLE
from app.services import citations as cit
from app.services import clock
from app.services import legal_marking as lm
from app.services import settings as st

DISCLAIMER = "Legal Studies feedback is for education only and is not legal advice."

# legal-06: model answers are labelled by where they came from, never by the marking method
PROVENANCE = {
    "seeded": "Written for this question by HSC Companion (GENERATED — not an official NESA sample answer)",
    "ai": "AI-written for this question (GENERATED — check every authority against your evidence bank)",
    "official_sample": "Official NESA sample answer",
    "student_entered": "Entered by you",
    "adapted": "Adapted by HSC Companion from a past-paper question (GENERATED)",
}
_STATUS_ORDER = {"verified": 0, "recheck_due": 1, "unverified": 2, "outdated": 3}


def evidence_for(db: Session, q: Question) -> list[dict]:
    """Evidence given to the AI prompt: the question's topic items, each with its verification status."""
    if not q.topic_id:
        return []
    today, s = clock.today(), st.all_settings(db)
    rows = db.execute(select(LegalEvidence).join(LegalEvidenceTopic).where(LegalEvidenceTopic.topic_id == q.topic_id)).scalars().all()
    out = []
    for e in rows:
        it = cit.make_item(e)
        out.append({"title": e.title, "type": e.item_type, "date": e.date, "jurisdiction": e.jurisdiction, "summary": e.summary,
                    "significance": e.legal_significance, "source_url": e.source_url, "status": cit.item_status(it, today, s),
                    "legal_status": e.status, "verified": e.last_verified_date.isoformat() if e.last_verified_date else "UNVERIFIED"})
    return out


def unverified_citations(text: str, evidence: list[dict]) -> list[str]:
    """Authorities in ``text`` that do not resolve to any of ``evidence`` (kept for callers of the
    v1 helper; resolution now uses the citations service)."""
    from datetime import date as _d

    bank = cit.Bank([{"title": e["title"], "item_type": e.get("type") or "report", "status": e.get("legal_status") or "unknown"} for e in evidence])
    out: list[str] = []
    for r in cit.unique(cit.resolve(text or "", bank, _d.today())):
        if r.citation.kind != "statistic" and r.status == "not_in_bank" and r.citation.name not in out:
            out.append(r.citation.name)
    return out


def _sub_area(db: Session, q: Question) -> str | None:
    item = db.get(LearningPlanItem, q.plan_item_id) if q.plan_item_id else None
    return item.code if item else None


def card(it: cit.BankItem, today, settings: dict | None = None) -> dict:
    stt = cit.item_status(it, today, settings)
    return {"id": it.id, "title": it.title, "type": it.item_type, "date": it.date or "", "jurisdiction": it.jurisdiction or "",
            "summary": it.summary or "", "source_url": it.source_url, "status": stt, "label": lm.item_label(it, today, settings),
            "cls": cit.CHIP_CLASS.get(stt, "")}


def evidence_cards(db: Session, q: Question, bank: cit.Bank, today, settings: dict | None = None, n: int = 3) -> list[dict]:
    """The top ``n`` relevant bank items (legal-15 element 6): the question's own evidence titles
    first, then items of its sub-area; verified before unverified; outdated items never suggested."""
    sol = q.solution or {}
    named = [t for t in list(sol.get("evidence_titles") or []) + list(sol.get("stimulus_evidence_titles") or []) if t]
    sub = _sub_area(db, q)
    picked: list[cit.BankItem] = []
    for t in named:
        it = bank.get(t)
        if it is not None and it not in picked:
            picked.append(it)
    if sub:
        picked += [it for it in bank.items if it.sub_area == sub and it not in picked]
    picked = [it for it in picked if cit.item_status(it, today, settings) != "outdated"]
    picked.sort(key=lambda it: (it.title not in named, _STATUS_ORDER.get(cit.item_status(it, today, settings), 9)))
    return [card(it, today, settings) for it in picked[:n]]


def _chips(resolutions) -> list[dict]:
    out = []
    for r in resolutions:
        d = r.as_dict()
        d["cls"] = cit.CHIP_CLASS.get(r.status, "")
        out.append(d)
    return out


def currency_for(resolutions, cards: list[dict], bank: cit.Bank, today) -> dict:
    """'Current information checked' from the items actually shown: cited in the model answer or
    an explanation, plus the evidence cards (legal-03). Stored as at marking time."""
    rs = [r for r in resolutions if r.item is not None]
    for c in cards:
        it = bank.get(c["title"])
        if it is not None:
            rs.append(cit.Resolution(cit.Citation("report", it.title, ""), cit.item_status(it, today), it))
    return cit.currency(rs, today)


def currency_line(cur: dict | None) -> str:
    """One line for the page, e.g. 'Current information checked: 01 Oct 2026 (oldest of 3 cited items)'."""
    if not cur or not cur.get("cited"):
        return "Current information checked: no evidence-bank items are cited here."
    from datetime import date as _d

    if cur.get("checked"):
        line = f"Current information checked: {_d.fromisoformat(cur['checked']):%d %b %Y} (oldest check of {cur['cited']} cited item{'s' if cur['cited'] != 1 else ''})"
    else:
        line = f"Current information checked: none of the {cur['cited']} cited item{'s' if cur['cited'] != 1 else ''} has been verified yet"
    extra = []
    if cur.get("unverified") and cur.get("checked"):
        extra.append(f"includes {len(cur['unverified'])} unverified item{'s' if len(cur['unverified']) != 1 else ''}: " + ", ".join(cur["unverified"][:3]))
    if cur.get("recheck_due"):
        extra.append("re-check due: " + ", ".join(cur["recheck_due"][:3]))
    if cur.get("outdated"):
        extra.append("recorded as outdated: " + ", ".join(cur["outdated"][:3]))
    return line + ("; " + "; ".join(extra) if extra else "") + f". As at {_d.fromisoformat(cur['as_at']):%d %b %Y}."


def model_origin(q: Question, ai_model: bool) -> str | None:
    if ai_model:
        return "ai"
    if not q.model_answer:
        return None
    origin = (q.solution or {}).get("model_answer_origin")
    if origin in PROVENANCE:
        return origin
    if q.guideline_official and q.historical_or_generated in (ORIGIN_HISTORICAL, ORIGIN_SAMPLE):
        return "official_sample"
    return "adapted" if q.historical_or_generated == ORIGIN_ADAPTED else "seeded"


# ------------------------------------------------------------------ offline estimate ---


def _apply_estimate(q: Question, est: lm.Estimate, result: MarkingResult, cards: list[dict], settings: dict) -> None:
    """Replace the generic offline result with the Legal estimate (in place: the caller keeps
    references to some of these lists)."""
    result.mark_awarded = est.mark
    result.criteria = [Criterion(name=c.name, judgement=c.judgement, comment=c.comment) for c in est.components]
    result.strengths = [f"{c.name}: {c.comment}" for c in est.components if c.score >= 0.75]
    result.weaknesses.clear()
    result.weaknesses.extend(f"{c.name}: {c.comment}" for c in est.components if c.score < 0.75)
    missing = [e["text"] for e in est.elements if not e["met"]]
    result.missing_elements = missing
    result.corrections = list(est.corrections)
    result.errors = [ErrorItem(category=j["category"], description=j["description"]) for j in est.journal]
    gaps = sorted((c for c in est.components if c.score < 1 and c.improve), key=lambda c: -(c.weight * (1 - c.score)))
    result.improvements = [c.improve for c in gaps[:4]] + est.notes
    result.improvement_task = lm.improvement_task(est, q, cards, settings)
    result.evidence_suggestions = [c["title"] for c in cards]
    result.dimensions = {}
    result.model_answer = ""  # legal-06: the offline result never claims the stored model answer
    level = lm.criteria_level((q.solution or {}).get("criteria") or [], est.mark)
    result.performance_level = (f"About {level.get('range') or level.get('mark')} marks: {level.get('descriptor')}" if level
                                else "Not estimated offline")
    met = sum(1 for e in est.elements if e["met"])
    bits = []
    if est.elements:
        bits.append(f"{met} of {len(est.elements)} required elements covered")
    auth = [r for r in est.resolutions if r.citation.kind != "statistic"]
    good = [r for r in auth if r.status in ("verified", "recheck_due", "unverified")]
    bits.append(f"{len(good)} authorit{'y' if len(good) == 1 else 'ies'} from your evidence bank")
    if est.corrections:
        bits.append(f"{len(est.corrections)} authorit{'y' if len(est.corrections) == 1 else 'ies'} to check")
    result.marking_rationale = ("Offline estimate: " + "; ".join(bits) + "." + (" " + " ".join(est.caps) if est.caps else ""))
    result.next_level = (f"To reach the next level: {level.get('descriptor')}" if level else
                         "Add the missing elements listed above, each supported by an authority from your evidence bank.")


def _correction_ok(text: str, bank: cit.Bank) -> bool:
    low = text.lower()
    return text.startswith("Possible issue") or any(it.title.lower() in low or any(a.lower() in low for a in it.aliases if len(a) > 3)
                                                     for it in bank.items)


def post_process(db: Session, q: Question, ctx: dict, result: MarkingResult, payload: dict, method: str) -> None:
    """Add Legal-only fields to the feedback payload (called by written.mark_written)."""
    s = st.all_settings(db)
    today = clock.today()
    bank = cit.Bank.from_db(db)
    response = ctx.get("response") or ""
    cards = evidence_cards(db, q, bank, today, s)
    ai_model = method == "ai" and bool(result.model_answer)

    if method == "offline_estimate":
        est = lm.estimate(q, response, bank, today, s, stimulus=ctx.get("stimulus"))
        _apply_estimate(q, est, result, cards, s)
        payload["mark"] = est.mark
        payload["result"] = result.model_dump()
        payload["model_answer"] = q.model_answer or ""
        model_f = lm.features(q.model_answer, bank, today, s) if q.model_answer else None
        payload["comparison"] = ""
        payload["comparison_rows"] = lm.comparison_rows(model_f, est.features, est)
        payload["scaffold"] = lm.scaffold(q, cards)
        payload["elements"] = est.elements
        payload["caps"] = est.caps
        payload["deduction"] = est.deduction
        payload["citations"] = _chips(r for r in est.resolutions if r.citation.kind != "statistic")
        payload["statistics"] = _chips(r for r in est.resolutions if r.citation.kind == "statistic")
        payload["unverified_references"] = []
    else:
        resp_res = cit.unique(cit.resolve(response, bank, today, s))
        payload["citations"] = _chips(r for r in resp_res if r.citation.kind != "statistic")
        payload["statistics"] = _chips(r for r in resp_res if r.citation.kind == "statistic")
        removed: list[str] = []
        if result.model_answer:  # legal-14: an AI model answer may only cite bank items
            red, removed = cit.redact(result.model_answer, cit.resolve(result.model_answer, bank, today, s))
            payload["model_answer"] = red
            payload["redacted"] = removed
        in_bank, not_in_bank = [], []
        for x in result.evidence_suggestions:
            it = bank.get(x)
            if it is None:
                rs = [r for r in cit.resolve(x, bank, today, s) if r.item is not None]
                it = rs[0].item if rs else None
            if it is not None:
                if all(c["title"] != it.title for c in in_bank):
                    in_bank.append(card(it, today, s))
            else:
                not_in_bank.append(x)
        payload["suggestion_cards"] = in_bank
        payload["ai_suggestions_not_in_bank"] = not_in_bank
        result.corrections = [c if _correction_ok(c, bank) else "Possible issue — verify: " + c for c in result.corrections]
        ai_text = " ".join([result.improved_argument, result.improved_answer])
        unverified = [r.citation.name for r in cit.unique(cit.resolve(ai_text, bank, today, s)) if r.status == "not_in_bank"]
        payload["unverified_references"] = list(dict.fromkeys(unverified + removed))
        good = [r for r in resp_res if r.item is not None and r.status != "outdated"]
        if good and all(r.item.item_type == "media" for r in good):
            payload["journalism_only"] = True
        payload["result"] = result.model_dump()
        payload["citation_audit"] = {"response": [r.as_dict() for r in resp_res], "redacted": removed, "suggestions_not_in_bank": not_in_bank}

    origin = model_origin(q, ai_model)
    payload["model_answer_origin"] = origin
    payload["model_answer_source"] = PROVENANCE.get(origin) if origin else None
    model_res = cit.unique(cit.resolve(payload.get("model_answer") or "", bank, today, s))
    payload["model_citations"] = _chips(r for r in model_res if r.citation.kind != "statistic")
    cur = currency_for(model_res, cards, bank, today)
    payload["currency"] = cur
    payload["currency_line"] = currency_line(cur)
    payload["facts_checked"] = cur.get("checked")
    payload["evidence_cards"] = cards
    payload["evidence"] = ctx["evidence"]
    payload["disclaimer"] = DISCLAIMER


def why_lost(q: Question, p: dict, attempt) -> str | None:
    """Legal-specific explanation built from the stored estimate (offline) or the AI result;
    None falls back to the generic written explainer."""
    r = p.get("result") or {}
    if p.get("method") != "offline_estimate" and not r.get("missing_elements") and not r.get("corrections"):
        return None
    from app.services.assessment.common import VERBS

    verb = (q.directive_verb or "").lower()
    parts = [f"This was a {q.marks}-mark '{q.directive_verb or 'response'}' question"
             + (f" — '{q.directive_verb}' asks you to {VERBS[verb]}" if verb in VERBS else "") + "."]
    mark = attempt.mark_awarded if attempt is not None and attempt.mark_awarded is not None else p.get("mark")
    if mark is not None:
        parts.append(f"Your response earned about {float(mark):g}/{q.marks}"
                     + (" (offline estimate)." if p.get("method") == "offline_estimate" else "."))
    if r.get("performance_level") and not r["performance_level"].startswith("Not estimated"):
        parts.append(r["performance_level"] + ".")
    missing = r.get("missing_elements") or []
    if missing:
        parts.append("Not yet covered: " + "; ".join(missing[:3]) + ".")
    if r.get("corrections"):
        parts.append("Check your authorities: " + r["corrections"][0])
    for c in p.get("caps") or []:
        parts.append(c)
    if r.get("improvement_task"):
        parts.append("Next: " + r["improvement_task"])
    return " ".join(parts)
