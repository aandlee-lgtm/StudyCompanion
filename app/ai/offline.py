"""Offline provider: no network, no generative AI. Written responses get a clearly labelled
heuristic estimate; mapping uses keyword matching; generation tasks are unavailable."""
from __future__ import annotations

import re

from app.ai.base import AIProvider, AIUnavailable
from app.ai.schemas import ClassifyResult, MappingResult, MarkingResult
from app.marking import rubric

OFFLINE_LABEL = ("Offline estimate — no AI provider is configured. This is a rough, feature-based estimate "
                 "(length, evidence, analysis, judgement), NOT a marking judgement and not an official NESA mark.")


class OfflineProvider(AIProvider):
    name = "offline"
    generative = False

    def __init__(self, reason: str | None = None):
        self.reason = reason or "HSC_AI_PROVIDER is 'offline'"

    def _complete(self, system: str, user: str) -> str:
        raise AIUnavailable("No AI provider configured")

    def classify_question(self, ctx: dict) -> ClassifyResult:
        q = ctx["question"]
        m = re.search(r"\((\d+)\s*marks?\)|(\d+)\s*marks?", q, re.I)
        marks = int(next(g for g in m.groups() if g)) if m else None
        verb = next((v for v in ("Evaluate", "Assess", "Analyse", "Explain", "Discuss", "Compare", "Describe", "Outline", "Identify", "Find", "Show", "Prove", "Calculate", "Sketch")
                     if re.search(rf"\b{v}\b", q, re.I)), None)
        qtype = "mcq" if re.search(r"^\s*\(?A[).]", q, re.M) and re.search(r"^\s*\(?D[).]", q, re.M) else (
            "extended" if marks and marks >= 10 else ("working" if ctx.get("subject") == "MATHS" else "short_answer"))
        diff = 1 if (marks or 2) <= 2 else (2 if (marks or 2) <= 4 else 3)
        return ClassifyResult(question_type=qtype, directive_verb=verb, marks=marks, difficulty=diff,
                              estimated_minutes=round(1.8 * (marks or 2), 1))

    def map_to_syllabus(self, ctx: dict) -> MappingResult:
        text = ctx["question"].lower()
        best, best_hits = None, 0
        for t in ctx["topics"]:
            hits = sum(1 for k in (t.get("keywords") or "").split(",") if k.strip() and k.strip().lower() in text)
            if hits > best_hits:
                best, best_hits = t, hits
        ext = ctx.get("subject") == "MATHS" and bool(re.search(r"mathematics extension|induction|vectors?\b|binomial theorem|inverse trig|\bsin\^\{-1\}", text))
        if best is None:
            best = ctx["topics"][0]
        conf = min(0.75, 0.3 + 0.15 * best_hits)  # offline mapping never auto-approves
        relevance = "REJECT" if ext else ("PARTIAL" if best_hits else "ADAPTABLE")
        return MappingResult(topic_code=best["code"], focus_area=best["name"], relevance=relevance,
                             relevance_score=0.0 if ext else (0.6 if best_hits else 0.3), confidence=conf, is_extension_content=ext,
                             reason=("Keyword match (offline mapper): " + (f"{best_hits} topic keyword(s) for '{best['name']}'." if best_hits else "no strong match.")
                                     + (" Looks like Extension content." if ext else "") + " Needs human review."))

    def mark_response(self, ctx: dict) -> MarkingResult:
        est = rubric.estimate(ctx["response"], ctx["subject"], int(ctx["marks"]), ctx.get("directive_verb"), ctx.get("paired", False))
        f = est["features"]
        improvements = [g[1] for g in est["gaps"]]
        dims = {}
        if ctx["subject"] == "ENGLISH":
            dims = {"textual evidence": f"{f['quotes']} quotation(s) detected", "analysis": f"{f['analysis']} analytical verb(s) detected",
                    "form/language": f"{f['techniques']} technique/feature term(s) detected", "length": f"{f['words']} words"}
        else:
            dims = {"legal terminology": f"{f['legal_terms']} legal term(s) detected", "legislation": ", ".join(f["acts"]) or "none named",
                    "cases": ", ".join(f["cases"]) or "none named", "contemporary evidence": ", ".join(map(str, f["recent_years"])) or "no dated evidence"}
        return MarkingResult(
            mark_awarded=est["mark"], mark_possible=float(ctx["marks"]), confidence=0.25, performance_level="Not estimated offline",
            criteria=[{"name": n, "judgement": "present" if n in est["strengths"] else "missing", "comment": ""} for n in
                      est["strengths"] + [g[0] for g in est["gaps"]]],
            strengths=[f"{s}: present" for s in est["strengths"]], weaknesses=[g[0] for g in est["gaps"]],
            improvements=improvements, dimensions=dims, model_answer=ctx.get("model_answer") or "",
            outcomes=[ctx["outcome"]] if ctx.get("outcome") else [],
            next_level="Add the missing elements listed under 'What prevented a higher mark'.",
            marking_rationale=OFFLINE_LABEL,
        )
