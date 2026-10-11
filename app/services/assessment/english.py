"""English Advanced specifics for written marking (owner: english-logic).

* ``post_process`` (called by ``written.mark_written``) adds the English feedback: authored ladder,
  checklist and next steps, deterministic checks (quotations verified against the passage, evidence
  from the right text(s), relevance, length), model-answer provenance, the 18 numbered feedback
  elements, and journal items with their own descriptions.
* Offline there is NO keyword estimate any more (english-03): the attempt waits for GUIDED
  SELF-MARKING. The student ticks the question's checklist (``apply_guided_self_mark``); the mark is
  derived from the ticks and capped by the deterministic checks.
* ``why_lost`` explains the gap with the question's own mark ladder (english-12)."""
from __future__ import annotations

import inspect
import logging
import math
import re

from sqlalchemy.orm import Session

from app.ai.schemas import MarkingResult
from app.ai.schemas_english import DIMENSIONS, EnglishPatch, canonical_category, missing_fields, needs_comparison
from app.marking import quotes
from app.models import Question
from app.services import english_compare as ec
from app.services import english_guided as eg
from app.services.assessment.common import MARKS_EXPECTATION, VERBS

log = logging.getLogger(__name__)

GUIDED_LABEL = ("Self-marked with the question's checklist (guided self-marking). No AI provider is configured, so the app does not "
                "estimate a mark itself; the deterministic checks below (quotations, evidence, relevance, length) are applied as caps. "
                "Not an official NESA mark.")
PENDING_LABEL = ("Not marked yet. No AI provider is configured, so mark your answer yourself: tick each checklist item your answer "
                 "really contains (compare with the passage and, if you like, the model). Your mark is worked out from the ticks.")
APP_MODEL = "Written for this question by HSC Companion (app-authored; every quotation checked against the passage)"
APP_PLAN = "Band 6 response plan written for this task by HSC Companion (app-authored; it names moments and form features but quotes nothing — use evidence from your own copy)"
AI_MODEL = "AI-written for this question (not yet reviewed; quotations checked against the passage)"
NOT_OFFLINE = "Not assessed offline (needs a teacher, a study partner or an AI provider)"


# ------------------------------------------------------------------- helpers ---


def _model_info(q: Question, m: dict) -> dict:
    """Which model (or plan) to show, and its provenance (english-05)."""
    sol = q.solution or {}
    if q.model_answer and m.get("model_status") != "quotes_unverified":
        src = sol.get("model_source") or "app_authored"
        return {"text": q.model_answer, "source": AI_MODEL if src == "ai_generated" else APP_MODEL, "kind": "model", "origin": src,
                "reviewed": src != "ai_generated" or sol.get("model_status") == "approved"}
    if m.get("plan"):
        return {"text": m["plan"], "source": APP_PLAN, "kind": "plan", "origin": "app_authored_plan", "reviewed": True}
    return {"text": None, "source": None, "kind": None, "origin": None, "reviewed": False}


def _whole(x: float) -> int:
    return int(math.floor(float(x) + 0.5))


def _english_items(result: MarkingResult, rt: str) -> list[dict]:
    """Journal items from AI errors, normalised to the English categories, each with its own description (english-18)."""
    out, seen = [], set()
    for e in result.errors:
        cat = canonical_category(e.category) or "other"
        desc = e.description if canonical_category(e.category) else f"({e.category}) {e.description}"
        if cat not in seen:
            seen.add(cat)
            out.append({"category": cat, "description": desc, "topic_tag": rt if rt in eg.CRAFT_TYPES else None})
    return out


def _patch_missing(db: Session, q: Question, ctx: dict, result: MarkingResult, missing: list[str]) -> list[str]:
    """Re-ask the AI once for only the elements its first reply left out (english-06)."""
    from app.ai import prompts, prompts_english
    from app.ai.base import AIError
    from app.ai.factory import get_provider
    from app.services import settings as st

    try:
        provider = get_provider(st.all_settings(db))
        patch = provider.complete_json(prompts.SYSTEM, prompts_english.patch_prompt(ctx, result.model_dump(), missing), EnglishPatch, retries=0)
    except (AIError, Exception) as exc:  # noqa: BLE001 - a failed re-ask is shown as 'Not assessed', never fatal
        log.warning("English feedback re-ask failed: %s", exc)
        return missing
    for f in ("performance_level", "next_level", "improved_answer"):
        if not getattr(result, f, "").strip() and getattr(patch, f, "").strip():
            setattr(result, f, getattr(patch, f))
    for f in ("strengths", "weaknesses", "improvements"):
        if not getattr(result, f) and getattr(patch, f):
            setattr(result, f, list(getattr(patch, f)))
    if patch.dimensions:
        result.dimensions = {**{k: v for k, v in patch.dimensions.items() if str(v).strip()}, **{k: v for k, v in (result.dimensions or {}).items() if str(v).strip()}}
    if patch.comparison_points and not getattr(result, "comparison_points", None) and hasattr(result, "comparison_points"):
        result.comparison_points = patch.comparison_points
    if "comparison_items" in missing and patch.comparison_items and hasattr(result, "comparison_items"):
        result.comparison_items = list(patch.comparison_items)
    return missing_fields(result, bool(q.model_answer), bool(ctx.get("previous_attempt")))


def _comparison_rows(result: MarkingResult) -> list[dict]:
    cp = getattr(result, "comparison_points", None)
    if not cp:
        return []
    names = [("what_model_does", "What the model does that yours does not"), ("descriptive_moments", "Where your answer becomes descriptive"),
             ("evidence_integration", "Where evidence could be better integrated"), ("development", "Where ideas need development"),
             ("expression", "How expression could be more precise"), ("sophistication", "How the argument could be more sophisticated")]
    return [{"title": t, "text": getattr(cp, k)} for k, t in names if getattr(cp, k, "").strip()]


def _ladder_rows(ladder: list[dict], mark: float | None) -> list[dict]:
    lv = eg.level_for(ladder, mark) if mark is not None else None
    return [{"mark": e["mark"], "low": e.get("low"), "descriptor": e["descriptor"], "reached": lv is e} for e in ladder]


def _offline_dims(m: dict, ck: dict, ticked_texts: list[str] | None = None, unticked: list[str] | None = None) -> dict[str, str]:
    """Honest offline dimensions: only what can be checked deterministically or was self-ticked."""
    qs = ck["quote_summary"]
    lo, hi = m["suggested_words"]
    dims: dict[str, str] = {}
    if m["has_text"] and not m["craft"]:
        ev = f"{qs['verified']} quotation{'s' if qs['verified'] != 1 else ''} verified against the text"
        if qs["unverified"]:
            ev += f"; {qs['unverified']} not found exactly as written (see the highlights)"
        if m["paired"]:
            ev += "; evidence from " + (" and ".join(f"Text {i + 1}" for i in qs["texts"]) if qs["texts"] else "neither text")
        dims["textual evidence"] = ev + "."
    elif not m["craft"]:
        dims["textual evidence"] = "Course-linked task: check your evidence against your own copy of the text (the app cannot verify it)."
    dims["structure"] = f"{ck['paragraphs']} paragraph{'s' if ck['paragraphs'] != 1 else ''}, {ck['words']} words (a typical answer is about {lo}–{hi} words)."
    for key, rx in (("analysis", r"explain|analys|effect|suggest|shape|reveal"), ("form", r"form|structure|technique|feature|narrat|point of view|tense"),
                    ("argument", r"thesis|argument|judg|evaluat|compar|line of"), ("language", r"language|word|image|imagery|detail|sensory")):
        hits_t = [t for t in (ticked_texts or []) if re.search(rx, t, re.I)]
        hits_u = [t for t in (unticked or []) if re.search(rx, t, re.I)]
        if hits_t or hits_u:
            dims[key] = "Self-assessed: " + "; ".join([f"✓ {t}" for t in hits_t] + [f"✗ {t}" for t in hits_u])
    for key in ("expression", "precision", "sophistication"):
        dims.setdefault(key, NOT_OFFLINE)
    for key in DIMENSIONS:
        dims.setdefault(key, NOT_OFFLINE)
    return dims


# --------------------------------------------------------------- post-process ---


def prompt_extra(q: Question) -> dict:
    """English marking context for the AI prompt (``ctx['english']``; see ``prompts_english``)."""
    m = eg.meta(q)
    model = _model_info(q, m)
    return {"response_type": m["response_type"], "craft": m["craft"], "demand": m["demand"], "ladder": m["ladder"], "checklist": m["checklist"],
            "next_steps": m["next_steps"], "plan": m["plan"] if model["kind"] == "plan" else None, "suggested_words": m["suggested_words"],
            "n_texts": m["n_texts"], "texts": m["texts"], "has_text": m["has_text"],
            "reference_model": model["text"] if model["kind"] == "model" else None, "anchors": (q.solution or {}).get("anchors") or []}



def post_process(db: Session, q: Question, ctx: dict, result: MarkingResult, payload: dict, method: str) -> None:
    """Add the English feedback to the payload (called by written.mark_written)."""
    m = eg.meta(q)
    response = ctx.get("response") or ""
    ck = eg.checks(q, response, m)
    model = _model_info(q, m)
    eng = {
        "response_type": m["response_type"], "craft": m["craft"], "demand": m["demand"], "skill_tags": m["skill_tags"], "form": m["form"],
        "ladder": m["ladder"], "checklist": m["checklist"], "checklist_authored": m["checklist_authored"], "next_steps": m["next_steps"],
        "suggested_words": m["suggested_words"], "paired": m["paired"], "texts": m["texts"], "has_text": m["has_text"],
        "checks": ck, "model_kind": model["kind"], "outcome": ctx.get("outcome") or "",
    }
    payload["english"] = eng
    payload["model_answer"] = model["text"]
    payload["model_answer_source"] = model["source"]
    payload["guidance"] = None  # the checklist replaces v1's generic guidance list

    if method == "offline_estimate":
        # english-03: no keyword estimate. The attempt waits for guided self-marking.
        result.mark_awarded = 0.0
        result.performance_level = ""
        result.criteria = []
        result.strengths = []
        result.weaknesses[:] = []  # in place: the v1 caller derives categories from this list object
        result.improvements = []
        result.errors = []
        result.dimensions = {}
        result.comparison = ""
        result.next_level = ""
        result.model_answer = ""
        result.marking_rationale = ""
        payload.update({"pending_mark": True, "guided": True, "mark": 0, "label": PENDING_LABEL, "comparison": "", "comparison_items": [],
                        "result": result.model_dump(), "journal_items": [], "estimated_items": []})
        eng["cap"] = ck["cap"]
        eng["hints"] = ec.pending_hints(response, m["checklist"])  # the student's closest sentence next to each item
        return

    # ---- AI marking
    result.mark_awarded = float(min(_whole(result.mark_awarded), q.marks))  # whole marks (english-20)
    for e in result.errors:  # EnglishMarking already normalises; a plain MarkingResult (other providers) is normalised here
        canon = canonical_category(e.category)
        if canon is None and e.category != "other":
            e.description = f"({e.category}) {e.description}"
        e.category = canon or "other"
    texts = eg.reading_texts(q)
    missing = missing_fields(result, bool(q.model_answer), bool(ctx.get("previous_attempt")))
    comp, dropped = ec.validate_ai_items(getattr(result, "comparison_items", []), response, texts)
    if needs_comparison(comp, result.mark_awarded, q.marks):
        missing.append("comparison_items")
    if missing:
        missing = _patch_missing(db, q, ctx, result, missing)
        comp, dropped2 = ec.validate_ai_items(getattr(result, "comparison_items", []), response, texts)
        dropped = max(dropped, dropped2)
        if needs_comparison(comp, result.mark_awarded, q.marks):
            missing.append("comparison_items")
    eng["not_assessed"] = missing
    # owner request 2026-10-11: lead with the point-by-point comparison of THEIR response; only items whose
    # quoted student text is verbatim in the response are kept
    if getattr(result, "comparison_items", None):  # the stored AI reply keeps only the items that passed the check
        result.comparison_items = [c for c in result.comparison_items
                                   if ec.is_verbatim(c.student_quote, response) or (not c.student_quote.strip() and c.status.strip().lower() == "missing")]
    payload["comparison_items"] = comp
    payload["comparison_source"] = "ai"
    payload["comparison_dropped"] = dropped
    if comp:
        payload["comparison"] = ec.summary_text(comp, result.mark_awarded, q.marks) if not payload.get("comparison") else payload["comparison"]

    # model provenance (english-05): a vetted model is never replaced by a new AI one
    ai_model = (result.model_answer or "").strip()
    if model["kind"] == "model":
        result.model_answer = ""
    elif ai_model:
        bad = [c.as_dict() for c in quotes.verify_quotes(ai_model, texts) if not c.found] if texts else []
        if bad:
            eng["ai_model_rejected"] = bad  # english-07c: an AI model with invented quotations is not shown
            payload["model_answer"], payload["model_answer_source"] = (model["text"], model["source"])
        else:
            _cache_ai_model(q, ai_model)
            payload["model_answer"], payload["model_answer_source"] = ai_model, AI_MODEL
    if result.improved_answer and texts:
        eng["improved_quotes"] = [c.as_dict() for c in quotes.verify_quotes(result.improved_answer, texts)]
        eng["improved_unverified"] = [c for c in eng["improved_quotes"] if not c["found"]]
    eng["comparison_rows"] = _comparison_rows(result)
    sl = getattr(result, "improvement_since_last", None)
    if sl is not None:
        eng["since_last"] = sl.model_dump()
    items = _english_items(result, m["response_type"])
    lv = eg.level_for(m["ladder"], result.mark_awarded)
    dims = {k: v for k, v in (result.dimensions or {}).items() if str(v).strip()}
    eng["elements"] = eg.element_rows(
        mark_text=f"{result.mark_awarded:g} / {q.marks} (AI-estimated)", marks=q.marks,
        level=result.performance_level or (f"{lv['mark']}-mark level: {lv['descriptor']}" if lv else ""),
        criteria=_ladder_rows(m["ladder"], result.mark_awarded), outcomes="; ".join(result.outcomes) or eng["outcome"],
        well=result.strengths, prevented=result.weaknesses if result.mark_awarded < q.marks else [], dims=dims,
        next_level=result.next_level or m["next_steps"].get(str(int(result.mark_awarded)), ""), actions=result.improvements)
    payload["result"] = result.model_dump()
    payload["mark"] = result.mark_awarded
    payload["journal_items"] = items


def _cache_ai_model(q: Question, text: str) -> None:
    """Keep the first AI model so it stays stable across attempts; it is labelled unreviewed (english-05)."""
    if q.model_answer:
        return
    q.model_answer = text
    q.solution = {**(q.solution or {}), "model_source": "ai_generated", "model_status": "unreviewed"}


# ------------------------------------------------------- guided self-marking ---


def guided_summary(q: Question, payload: dict, ticked: list[int]) -> dict:
    """The derived self-mark and everything shown with it, for a set of ticked checklist items."""
    eng = payload.get("english") or {}
    m = eg.meta(q)
    checklist = eng.get("checklist") or m["checklist"]
    ck = eng.get("checks") or eg.checks(q, "", m)
    ticks = sorted({int(i) for i in ticked if 0 <= int(i) < len(checklist)})
    raw, final = eg.derive_mark(q.marks, len(checklist), len(ticks), ck.get("cap"))
    ladder = eng.get("ladder") or m["ladder"]
    lv = eg.level_for(ladder, final)
    next_steps = eng.get("next_steps") or m["next_steps"]
    rt = eng.get("response_type") or m["response_type"]
    done = [checklist[i] for i in ticks]
    missing = [c for i, c in enumerate(checklist) if i not in ticks]
    cap_reasons = [w["message"] for w in ck.get("warnings", []) if w.get("cap") is not None and w["cap"] < raw]
    items, seen = [], set()
    for text in missing:
        cat = eg.item_category(text, rt, payload.get("response") or "")
        if cat not in seen:
            seen.add(cat)
            items.append({"category": cat, "description": f"Not yet in your answer: {text}", "topic_tag": rt if rt in eg.CRAFT_TYPES else None})
    for w in ck.get("warnings", []):
        cat = {"no_evidence": "insufficient textual evidence", "misquote": "insufficient textual evidence", "one_text": "poor comparison"}.get(w["code"])
        if cat and cat not in seen and final < q.marks:
            seen.add(cat)
            items.append({"category": cat, "description": w["message"], "topic_tag": None})
    nxt = next((e for e in sorted(ladder, key=lambda e: e["mark"]) if e.get("low", e["mark"]) > final), None)
    next_level = ""
    if nxt:
        next_level = f"{nxt.get('low', nxt['mark'])} marks: {nxt['descriptor']}"
    step = next_steps.get(str(final)) if final < q.marks else None
    actions = ([step] if step else []) + [f"Add: {t}" for t in missing[:2]] + [w["message"] for w in ck.get("warnings", []) if w["code"] in ("misquote", "unmarked_evidence")][:1]
    mark_text = f"{final} / {q.marks} (self-marked: {len(ticks)} of {len(checklist)} checklist items)"
    if final < raw:
        mark_text += f"; capped from {raw} by the checks below"
    rows = eg.element_rows(
        mark_text=mark_text, marks=q.marks, level=(f"{lv['mark']}-mark level: {lv['descriptor']}" if lv else ("Below the first level" if final == 0 else "")),
        criteria=_ladder_rows(ladder, final), outcomes=eng.get("outcome") or "", well=done,
        prevented=missing + cap_reasons, dims=_offline_dims({**m, **{k: eng[k] for k in ("suggested_words", "paired", "has_text", "craft") if k in eng}}, ck, done, missing),
        next_level=next_level, actions=actions)
    comparison = ec.offline_items(
        response=payload.get("response") or "", checklist=checklist, ticked=ticks, marks=q.marks, final=final, raw=raw, ladder=ladder,
        next_steps=next_steps, checks=ck, model_text=payload.get("model_answer"), model_kind=eng.get("model_kind"),
        passages=eg.reading_texts(q), paired=bool(eng.get("paired", m["paired"])), response_type=rt, category_of=eg.item_category)
    return {"ticked": ticks, "raw": raw, "final": final, "cap": ck.get("cap"), "cap_reasons": cap_reasons, "done": done, "missing": missing,
            "level": lv, "next_step": step, "items": items, "elements": rows, "comparison": comparison}


def _accepts(fn, name: str) -> bool:
    try:
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def apply_guided_self_mark(db: Session, attempt, ticked: list[int]) -> dict:
    """Record a guided self-mark: the mark comes from the ticked checklist items, capped by the
    deterministic checks, and is handed to ``core.apply_self_mark`` (schedule, mastery, journal)."""
    from app.models import ErrorJournal
    from app.services.assessment import core

    q = attempt.question
    fb = attempt.feedback
    payload = dict(fb.payload or {})
    if payload.get("subject") != "ENGLISH" or not payload.get("english"):
        raise ValueError("Guided self-marking is only available for English written answers.")
    payload["response"] = attempt.response_text
    g = guided_summary(q, payload, ticked)
    criteria = [{"item": c, "ticked": i in g["ticked"]} for i, c in enumerate(payload["english"]["checklist"])]
    kwargs = {}
    if _accepts(core.apply_self_mark, "categories"):
        kwargs["categories"] = g["items"]
    if _accepts(core.apply_self_mark, "criteria"):
        kwargs["criteria"] = criteria
    core.apply_self_mark(db, attempt, float(g["final"]), **kwargs)
    if "categories" not in kwargs and attempt.attempt_number == 1:  # older core: journal the gaps here
        from app.services.assessment.common import subject_code

        for e in db.query(ErrorJournal).filter(ErrorJournal.attempt_id == attempt.id).all():
            db.delete(e)
        for it in g["items"]:
            db.add(ErrorJournal(attempt_id=attempt.id, question_id=q.id, subject_code=subject_code(db, q), category=it["category"],
                                plan_item_id=q.plan_item_id, description=it["description"]))
        fb.error_categories = [i["category"] for i in g["items"]]
    if attempt.marking_method == "offline_estimate":
        attempt.marking_method = "self"
    payload = dict(fb.payload or {})
    payload.pop("response", None)
    eng = dict(payload.get("english") or {})
    eng["self"] = {k: v for k, v in g.items() if k not in ("elements", "comparison")}
    eng["elements"] = g["elements"]
    payload["english"] = eng
    payload["comparison_items"] = g["comparison"]  # owner request: lead with the point-by-point comparison
    payload["comparison_source"] = "self_mark"
    payload["comparison"] = ec.summary_text(g["comparison"], g["final"], q.marks)
    payload.update({"guided": True, "pending_mark": False, "self_marked": True, "mark": float(g["final"]), "label": GUIDED_LABEL,
                    "self_criteria": criteria})
    r = dict(payload.get("result") or {})
    r.update({"mark_awarded": float(g["final"]), "strengths": g["done"], "weaknesses": g["missing"] + g["cap_reasons"],
              "performance_level": g["elements"][2]["value"], "next_level": g["elements"][16]["value"], "improvements": g["elements"][17]["value"],
              "errors": [{"category": i["category"], "description": i["description"]} for i in g["items"]]})
    payload["result"] = r
    fb.payload = payload
    fb.why_lost = None  # an explanation cached before marking ("mark your answer first") is out of date now
    db.flush()
    return g


# ------------------------------------------------------------------ why lost ---


def why_lost(q: Question, p: dict, attempt) -> str | None:
    """The gap explained with THIS question's mark ladder (english-12): what you did, why this mark
    value needs more, and the authored next step for this passage. Paragraphs separated by blank lines."""
    eng = p.get("english")
    if not eng:
        return None
    if p.get("pending_mark"):
        return ("Mark your answer first: tick the checklist items your answer really contains. The explanation then uses the level "
                "you reached and the next step written for this passage.")
    mark = int(round(attempt.mark_awarded))
    ladder = eng.get("ladder") or []
    lv = eg.level_for(ladder, mark)
    verb = (q.directive_verb or "").lower()
    self_ = eng.get("self") or {}
    parts = []
    if lv:
        did = f"Your answer is at the {lv['mark'] if not lv.get('low') else str(lv['low']) + '–' + str(lv['mark'])}-mark level for this question: {lv['descriptor'][0].lower() + lv['descriptor'][1:]}."
    else:
        did = "Your answer did not yet reach the first level of the ladder for this question."
    if self_.get("done"):
        did += " You showed: " + "; ".join(self_["done"][:2]) + "."
    parts.append(did)
    if eng.get("craft"):
        why = (f"This is a {q.marks}-mark {eng.get('response_type', 'composition')} task. Marks here reward deliberate control — every choice of "
               "detail, structure, voice and tense should serve the purpose — not the number of techniques used.")
    else:
        why = (f"This was a {q.marks}-mark '{q.directive_verb or 'response'}' question"
               + (f" ('{q.directive_verb}' asks you to {VERBS[verb]})" if verb in VERBS else "")
               + f". At {q.marks} marks a marker expects {MARKS_EXPECTATION.get(min(q.marks, 6), MARKS_EXPECTATION[6])}.")
        nxt = next((e for e in sorted(ladder, key=lambda e: e["mark"]) if e.get("low", e["mark"]) > mark), None)
        if nxt:
            why += f" The next level ({nxt.get('low', nxt['mark'])} marks) needs: {nxt['descriptor'][0].lower() + nxt['descriptor'][1:]}."
    caps = self_.get("cap_reasons") or []
    if caps:
        why += " Your mark was also capped: " + caps[0]
    parts.append(why)
    step = (eng.get("next_steps") or {}).get(str(mark))
    if step:
        parts.append(f"Your next step for this {'task' if eng.get('craft') else 'passage'}: {step}")
    misq = [c for c in (eng.get("checks") or {}).get("quotes", []) if not c.get("found")]
    if misq:
        c = misq[0]
        parts.append(f"Accuracy matters too: “{c['quote']}” is not in the text as written. {c.get('note') or ''}".strip())
    return "\n\n".join(parts)
