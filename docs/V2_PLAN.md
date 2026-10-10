# HSC Companion 2027 — version 2 build plan

v1 (commit `e18d23d`) was audited against `docs/SPECIFICATION.md`. The verified-by-reproduction
findings are in `/tmp/claude-0/-home-user/a63aafe1-601c-5ef5-85d0-f9ee1e900e08/scratchpad/audit_findings.json`
(JSON list of lanes; each finding has id, severity, evidence, proposal). v2 is built by parallel
work packages, each in its own git worktree and branch, merged by the integrator.

## Rules for every package

1. **Work only in your worktree** `/home/user/wt/<package>` (branch `v2-<package>`). Never edit
   `/home/user/studycompanion` directly. Commit early and often (`git commit -am "..."`, with a
   clear message) so interrupted work is never lost — at least after every coherent step.
   Commit messages must end with the two attribution lines:
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
   `Claude-Session: https://claude.ai/code/session_01BTjCCVHmSkPqzXQd8opGK9`.
2. **File ownership.** Edit only files your package owns (listed below) plus NEW files you create
   (prefix new modules/tests with your area, e.g. `app/services/citations.py`,
   `tests/test_v2_legal_*.py`). If you truly need a change in a file you don't own, keep it
   minimal (a few lines), and describe it in your final report so the integrator can check it.
   Shared files with reserved slots: `app/services/settings.py` (add defaults only inside your own
   `DEFAULTS.update({  # <package>` block), `app/static/css/<package>.css`,
   `app/services/seed.py` (only your own loader function), `app/models/*.py` (see 3).
3. **Schema changes.** Prefer storing extra per-question data in existing JSON columns
   (`Question.solution`, `Question.answer`, `AttemptFeedback.payload`, `SessionQuestion.score_breakdown`,
   `DailySession.explanation`). If you need new columns/tables: add them to the model at the END of
   the class with a `# v2-<package>` comment, and add ONE Alembic migration
   `migrations/versions/0002_<package>.py` with `revision = "0002_<package>"` and
   `down_revision = "0001"` (the integrator chains them). New tables go in a new model module
   `app/models/<package>.py` imported from `app/models/__init__.py` (one line).
4. **Tests.** Keep the existing suite passing (`python3 -m pytest -q`, ~40 s); change an existing
   test only when behaviour changes deliberately, and say why in the report. Add focused tests for
   everything you build in `tests/test_v2_<package>*.py`. Run targeted tests while working and the
   full suite before your final commit.
5. **Honesty rules from the spec.** Never invent NESA questions, guidelines, outcome codes,
   prescriptions, cases, legislation, statistics or dates. Generated content is labelled
   GENERATED. AI marks are never official. Offline estimates are labelled as such. No network
   access to NESA/legislation sites exists — when unsure of a fact, mark it for owner
   verification rather than guessing.
6. **Quality bar.** This app is for a serious Year 12 student: calm UI, precise educational
   feedback, no gamification. Desktop Chrome first, works at phone width, light and dark mode.
7. **Efficiency.** Read only the files you need; avoid printing huge outputs; don't start web
   servers unless you need to see a page (use FastAPI TestClient for route tests).
8. **Final report** (your final message): what you implemented (by audit id), what you skipped and
   why, any edits outside your files, new settings, migrations, and test results.

## Packages and ownership

| Package | Owns |
|---|---|
| selection | `app/selection/*`, `app/services/sessions.py`, `app/services/question_bank.py`, `app/routes/today.py`, templates `session.html`, `today_none.html`, `app/static/js/session.js`, `css/selection.css` |
| maths | `app/marking/maths.py`, `app/services/maths_templates.py`, `data/seed/questions_maths.json`, `app/services/assessment/maths.py`, `app/routes/api.py` (math preview), templates `_answer_maths.html`, `feedback_maths.html`, `app/static/js/maths.js`, `css/maths.css`, `seed.py::seed_maths_handwritten` |
| english-logic | `app/services/assessment/english.py`, `app/ai/prompts_english.py`, new `app/ai/schemas_english.py`, `app/marking/rubric.py`, new `app/marking/quotes.py`, templates `_stimulus.html`, `_answer_written.html`, `feedback_english.html`, `app/static/js/writing.js`, `css/english.css`, `seed.py::seed_english`, new `app/routes/english.py` |
| english-content | NEW data files only: `data/seed/english_sets.json`, `data/seed/english_course.json` |
| legal-logic | `app/services/assessment/legal.py`, new `app/services/citations.py`, `app/services/legal_evidence.py`, `app/routes/legal.py`, `app/routes/curriculum.py`, templates `legal.html`, `feedback_legal.html`, `curriculum.html`, `app/ai/prompts_legal.py`, new `app/ai/schemas_legal.py`, `seed.py::seed_legal` + `seed_legal_evidence`, `data/seed/curriculum.json`, `data/seed/legal_evidence.json`, `css/legal.css` |
| legal-content | NEW data files only: `data/seed/legal_v2.json`, `data/seed/legal_evidence_v2.json` |
| ingestion | `app/ingestion/*`, `app/routes/questions.py`, templates `questions.html`, `question_detail.html`, `admin_review.html`, `admin_import.html`, `sources.html`, `_audit_line.html`, `scripts/import_nesa.py`, `app/services/fingerprint.py`, `css/ingestion.css` |
| adaptive | `app/services/assessment/core.py`, `why.py`, `common.py`, `written.py`, `app/services/mastery.py`, `app/routes/review.py`, `errors.py`, `practice.py`, `attempts.py`, `question_helpers.py`, templates `question.html`, `_answer_mcq.html`, `feedback_mcq.html`, `feedback_skipped.html`, `feedback_self_mark.html`, `review.html`, `errors.html`, `app/static/js/core.js`, `js/plan.js`, `css/adaptive.css` |
| analytics | `app/services/analytics.py`, `app/routes/dashboard.py`, `app/routes/progress.py`, templates `dashboard.html`, `progress.html`, `week.html`, `month.html`, `summary.html` |
| platform (integrator) | `app/main.py`, `app/config.py`, `app/db.py`, `app/ai/base.py`, `factory.py`, `openai_compat.py`, `offline.py`, `schemas.py`, `prompts.py`, `app/routes/setup.py`, `settings_routes.py`, `common.py`, templates `base.html`, `setup.html`, `settings.html`, `error.html`, `app/static/app.css`, `app/services/backup.py`, `clock.py`, `plan.py`, `settings.py` (structure), `app/desktop.py`, `packaging/*`, `migrations/env.py`, `README.md`, `docs/*` |

## Content data formats

### English reading sets — `data/seed/english_sets.json`
```json
{"sets": [{
  "key": "unique-slug", "title": "…", "form": "Prose fiction | Memoir | Personal essay | Feature article | Speech | Poetry | Media | Hybrid | Drama | Letter | Review",
  "complexity": 1, "author": "Original text (HSC Companion)", "body": "text; blank line between paragraphs; poems keep line breaks",
  "pair": null,
  "questions": [{
    "marks": 4, "verb": "Analyse", "demand": "identify|explain|analyse|compare|evaluate|synthesise",
    "text": "question wording", "skill_tags": ["imagery", "perspective"],
    "criteria": [{"mark": 4, "descriptor": "…"}, {"mark": 3, "descriptor": "…"}, {"mark": 2, "descriptor": "…"}, {"mark": 1, "descriptor": "…"}],
    "checklist": ["passage-specific element a strong answer contains", "…"],
    "next_steps": {"0": "…", "1": "…", "2": "…", "3": "…"},
    "model": "Band 6 response written for this question; every quotation must appear verbatim in the passage"
  }]
}]}
```
`pair` (paired texts) is `{"title": "…", "form": "…", "body": "…"}`; the questions then refer to
"Text 1" (main) and "Text 2" (pair). Every set has 3 questions with distinct marks (2–6).

### English course-linked and Craft tasks — `data/seed/english_course.json`
```json
{"questions": [{"module": "EN-THE|EN-TC|EN-CSL|EN-CRAFT", "marks": 6, "verb": "Analyse", "demand": "analyse",
  "response_type": "analytical|comparative|imaginative|discursive|persuasive|reflective|rewrite",
  "text": "…", "criteria": [...], "checklist": [...], "next_steps": {...},
  "plan": "Band 6 response PLAN (thesis, paragraph moves, which moments/scenes/poems to use, which form features) — NO direct quotations from the prescribed texts",
  "suggested_words": [250, 350]}]}
```

### Legal questions — `data/seed/legal_v2.json`
```json
{"questions": [{
  "topic": "LS-CRIME | LS-HR | LS-OPT-…", "sub_area": "LS-CRIME-NATURE | LS-CRIME-INVESTIGATION | LS-CRIME-TRIAL | LS-CRIME-SENTENCING | LS-CRIME-YOUNG | LS-CRIME-INTERNATIONAL | LS-HR-NATURE | LS-HR-ENFORCE | LS-HR-ISSUE",
  "type": "mcq | short_answer | stimulus | extended", "marks": 1, "difficulty": 1, "verb": "Explain",
  "text": "…",
  "stimulus": {"title": "…", "kind": "hypothetical scenario | statistics table (hypothetical) | extract", "body": "…", "evidence_titles": []},
  "options": ["A. …", "B. …", "C. …", "D. …"], "answer": "B",
  "option_rationales": {"A": "why tempting and why wrong", "B": "why right", "C": "…", "D": "…"},
  "criteria": [{"mark": 5, "descriptor": "…"}, …], "required_elements": ["…"],
  "model": "Band 6 model answer; cites ONLY evidence-bank items by exact title",
  "evidence_titles": ["exact titles of bank items cited"],
  "legal_fact_currency": "current | check"
}]}
```

### Legal evidence additions — `data/seed/legal_evidence_v2.json`
Same item format as `data/seed/legal_evidence.json`, plus `"sub_area"`, `"aliases": []`,
`"status": "in_force | repealed | amended | superseded | unknown"`. Only real, well-known items you
are confident exist; never invent; every item starts unverified.

## Package briefs (priorities: MUST first, then SHOULD; audit ids in brackets)

- **selection** — MUST: score-respecting joint set selection with per-subject time envelopes and
  the 80–95 window as a real constraint (selection-01/02); exact repeat before
  `next_revision_date` is a hard rule + fallback ladder (selection-03, adaptive-04); stimulus is the
  unit of freshness, one passage per day, 3 distinct-mark questions (selection-04, english-19);
  two-stage item allocation so weights and weakness matter (selection-05); one question per
  template family/form per session (selection-07, adaptive-22); missed-day redesign incl. catch-up
  and setup floor (selection-10/11); active-time timer with heartbeats and auto-pause
  (selection-13); mode profiles incl. light day counts (selection-15); Legal weekly format plan and
  extended-response rotation using question types `mcq|short_answer|stimulus|extended`
  (selection-16, legal-07, legal-10); explanation built from the engine's facts (selection-19);
  longitudinal simulation test harness (selection-21). SHOULD: selection-06/08/09/12/14/17/18/20/22.
- **maths** — MUST: safe locked-down parser (whitelist, AST validation, size/exponent caps, never
  eval arbitrary names) and marking that can never hang or 500 (maths-01/02); units, rounding
  semantics, MCQ letter parsing, intervals (maths-03/04/05/14); a real template for every aliased
  subtopic + 2E, 2G, graph-modelling, continuous RVs, 8F (maths-06/13); multi-part HSC-style
  4–6 mark challenge templates so the Maths slot can fill ~35 min (selection-02); difficulty tiers
  that are real (maths-10); common errors tagged on two axes `category` (spec 5C list) and
  `topic_tag` (spec 23 list: sign error, chain rule, algebra, domain/range, calculator error,
  probability interpretation, …) (adaptive-10); content self-test (maths-09/16). SHOULD: maths-07/08/
  11/12/15/17/18/19/20.
- **english-logic** — MUST: replace keyword offline estimate with guided self-marking against the
  question's checklist/criteria plus deterministic warnings (english-03); quote verification
  module and its use (english-07); model-answer provenance and keep vetted models
  (english-05/06); per-question mark ladders for why-lost (english-12); response types incl.
  Craft routing (english-04); split-pane passage/writing layout incl. full screen (english-14);
  load the new content files in `seed_english` (sets, course tasks). SHOULD: english-13/16/17/18/20/22.
- **english-content** — MUST: at least 30 new ORIGINAL reading sets (90 questions) across the forms
  in spec 6A (prose fiction, memoir, personal essay, feature article, speech, poetry, media, hybrid,
  drama/script, letter; 6+ paired sets with comparison/synthesis), marks 2–6 incl. 6-mark questions,
  demands identify→synthesise, each with criteria ladder, checklist, next_steps and a genuine
  Band 6 model whose quotations are verbatim; plus at least 32 course-linked/Craft tasks
  (8 per module) with criteria and response PLANS (no invented quotations). Verify every quotation
  programmatically before finishing.
- **legal-logic** — MUST: citations service (legal-01/02), currency from cited items (legal-03),
  offline Legal marking rebuilt on resolved citations + required elements, never rewarding invented
  authorities (legal-04/05/15), provenance labels (legal-06), Legal sub-areas as plan items with
  statuses and option slots (max two) in the Learning plan (legal-09/11), evidence bank structure +
  edit form + verification dialog (legal-18/19), Legal prompt dimensions (legal-13/14), load the new
  content files in `seed_legal`/`seed_legal_evidence`, tests (legal-21). SHOULD: legal-17/20.
- **legal-content** — MUST: a substantially larger Legal bank in the format above for Crime and
  Human Rights across all sub-areas: ≥24 scenario MCQs with per-option rationales, ≥16 short answers
  across verb tiers (2–8 marks), ≥8 stimulus-based questions (hypothetical scenarios or hypothetical
  data — clearly labelled hypothetical, never fake real-world facts), ≥4 extended responses
  (15 marks) with full Band 6 model answers; all model answers cite only evidence-bank items (existing
  or added by you, real and well-known only). Add ≥15 real evidence items (legislation, cases,
  treaties, institutions) you are confident exist, unverified. Mark anything time-sensitive
  `legal_fact_currency: "check"`.
- **ingestion** — MUST: coordinate-based segmentation (MCQ numbers/options, marks from margins and
  headings, sub-parts (i)/(ii), continuation, noise) (sources-01/02/04/11); per-segment failure
  isolation (sources-03); subtopic mapping that never releases future content early, UNMAPPED state
  (sources-05/06/07); guideline parser incl. MCQ answer key and criteria rows (sources-09/10);
  English stimulus booklet import (sources-08); review tool with edit fields, validation gates,
  batch actions, adaptation editor creating ADAPTED copies (sources-12/13, english-11, legal-12);
  question detail reveal gate (adaptive-01); library filters + edit/retire (sources-18); audit line
  (sources-19); realistic PDF fixture tests (sources-24). SHOULD: sources-14/15/16/17/21/22/23.
- **adaptive** — MUST: one attempt chain per question with `counts_for_mastery`/`after_reveal`, practice
  as rehearsal (adaptive-02); revision queue lifecycle fix (adaptive-03); confidence × correctness
  table (adaptive-05); evidence weighted by marking reliability, no weak schedules from offline
  estimates (adaptive-06); error journal two axes + patterns panel (adaptive-10/11/12); why-lost
  dispatcher using subject explainers, MCQ distractor rationales (`solution.option_rationales`),
  skipped explanation (adaptive-13); retry flow (adaptive-15, english-21); self-mark deferral
  (adaptive-16); learner-facing schedule labels (adaptive-17); review page rebuild (adaptive-18);
  rebuild ladder for struggling skills (adaptive-19); token-answer guard (adaptive-23); practice
  drafts autosave (english-15). SHOULD: adaptive-07/08/09/14/20/21.
- **analytics** — (this lane was not audited; audit it yourself against spec 20, 21, 22, 45, 46,
  47, 48, 49 first) MUST: correct numbers and specific interpretations like the spec's examples;
  readiness explained, low early, uses counted attempts only; daily summary, Friday weekly review,
  monthly review complete; dashboard: all section-20 elements, a "Question bank health" card per
  subject (fresh questions left ≈ days until repeats; LEARNING items without questions); historical
  coverage per focus area; performance with 3,000 attempts (each page < 1 s).
