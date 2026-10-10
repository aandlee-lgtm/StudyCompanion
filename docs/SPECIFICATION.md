# HSC Companion 2027 — owner's specification (source of truth)

This is the owner's specification, as given. Section 5A (the confirmed Mathematics learning
sequence) was supplied first and supersedes the "do not assume the Cambridge order" instruction
in section 5A below. The full chapter list is in `docs/5A-maths-learning-sequence.md` and
`docs/maths-advanced-y12-sequence.json`.

Packaging requirement added later by the owner: **a Mac installer (DMG) only** — the owner uses
an Apple silicon Mac and does not need Windows.

---

## 5A (supplied first). CONFIRMED MATHEMATICS LEARNING SEQUENCE

The student's Year 12 Mathematics Advanced course follows: CambridgeMATHS NSW Stage 6
Mathematics Advanced Year 12, Second Edition. Use this as the DEFAULT learning pathway (Chapters
1–10, subtopics 1A–10F; see `docs/5A-maths-learning-sequence.md`).

- Track learning status at SUBTOPIC level, not merely chapter level.
- Every subtopic must support LOCKED, LEARNING, LEARNED, REVISION.
- Default starting position: Chapter 1, 1A = LEARNING, all later subtopics LOCKED. The student
  must be able to change this immediately.
- Daily Mathematics questions approximately: 50–60% current LEARNING subtopic(s); 20–30%
  recently LEARNED; 10–20% older revision / Year 11 assumed knowledge. Starting rules only;
  adapt to performance.
- Never serve questions from LOCKED subtopics in an ordinary daily session.
- When a new subtopic becomes LEARNING: retain revision from earlier subtopics; progressively
  reduce the weighting of older mastered material; increase weighting for weaknesses.
- Challenge sections 3D and 6F are ENRICHMENT by default: no normal daily weighting unless the
  content is explicitly required by NESA, or the student activates challenge/enrichment practice.
- The Cambridge sequence determines WHEN material is introduced. The official NESA syllabus
  determines WHAT is examinable. Where they differ, NESA takes precedence.

---

You are a senior Python software engineer, educational technology architect, data engineer and
NSW HSC assessment specialist. DESIGN AND BUILD a complete working application called
**HSC Companion 2027**.

This is not merely a quiz application. It is a serious, year-long learning companion for a NSW
Year 12 student preparing for the 2027 HSC. The student commences Year 12 in Term 4 of 2026 and
sits the HSC in 2027. Subjects: 1. Mathematics Advanced 2. English Advanced 3. Legal Studies.

It must operate locally using Python and be accessed primarily through Google Chrome as a local
web application. Not a collection of notebooks — it must behave like a proper application.

## 1. Central purpose
Every Monday to Friday the application prepares a personalised HSC practice session of
approximately 90 minutes: MATHEMATICS ADVANCED 5 questions; ENGLISH ADVANCED 3 questions (strong
emphasis on unseen-text comprehension); LEGAL STUDIES 3 questions. Total 11 per weekday.
Difficulty, marks and expected response length must be selected intelligently so the session is
about 90 minutes. Do not blindly select eleven large examination questions.

The application must know: what the student has learned; is currently learning; has not yet
learned; which questions were attempted; which were answered poorly; which syllabus outcomes need
more practice; which questions are due for revision; how difficult each question is; how long it
should take; what topics should not yet be tested. It should progressively evolve from a learning
companion into an HSC revision and examination-preparation system as 2027 progresses.

## 2. Most important educational principle
Do NOT assume an old HSC question remains relevant simply because it came from the same course.
Every historical question must be mapped against the syllabus applying to the 2027 HSC (2027 is
the first HSC under the new Mathematics Advanced syllabus and the new English Advanced syllabus;
Legal Studies remains under the syllabus applicable to this student's 2027 HSC).

Formal question-mapping system with fields such as: source_subject, source_year, source_exam,
source_question_number, marks, original_topic, 2027_topic, 2027_focus_area, syllabus_outcome,
syllabus_content_descriptor, relevance_classification, relevance_score, mapping_confidence,
mapping_reason, difficulty, estimated_minutes, source_quality, approval_status.

Relevance classifications: DIRECT (knowledge and skills remain directly applicable); PARTIAL
(part applicable, another component no longer aligned); ADAPTABLE (skill valuable, question
requires modification); REJECT (removed, obsolete or irrelevant content). Only DIRECT questions
automatically enter the normal historical pool. PARTIAL and ADAPTABLE go to an administrator
review queue. REJECT must never be presented to the student.

## 3. Source hierarchy
TIER 1 — AUTHORITATIVE official NESA: current syllabus, outcomes, content descriptors, HSC exam
specifications, sample exam materials, historical HSC papers, official marking guidelines,
performance band descriptions. Always priority.
TIER 2 — HISTORICAL OFFICIAL: older NESA papers predating the current syllabus, only after
mapping determines relevance.
TIER 3 — SCHOOL/TRIAL: importable later, labelled "TRIAL / NON-NESA", never presented as
official HSC questions.
TIER 4 — AI-GENERATED: when new-syllabus material is poorly represented, more practice is
needed, a historical question is being adapted, or revision needs a different version. Always
labelled "GENERATED" or "ADAPTED FROM HISTORICAL QUESTION". Never imply it appeared in an HSC.

## 4. Copyright and source integrity
Private study app, not redistribution. Preserve source, exam year, question number, source
document reference, page number where possible. Do not copy commercial textbooks; do not
distribute commercial trial papers. Where a question depends on a diagram/graph/complex
formatting, retain a reference to the source PDF and preferably render or crop the page/region
rather than recreate inaccurately. English unseen texts: preserve attribution and provenance. Do
not fabricate passages and claim they came from NESA.

## 5. Mathematics Advanced — 2027
Mathematics Advanced ONLY (no Extension 1/2). Never introduce Extension questions into the normal
pool. The new syllabus applying to the 2027 HSC is authoritative. Year 12 focus areas include:
further graph transformations and modelling; differential calculus; integral calculus;
applications of calculus; sequences and series; random variables; financial mathematics. Year 11
content is assumed knowledge and remains available for controlled revision.

### 5A. Learning sequence (original wording; superseded by the confirmed sequence above)
Editable Mathematics Learning Plan; user can define or import the chapter sequence; NESA Year 12
focus areas; chapters/subtopics can be added; drag-and-drop or numerical reordering; facility to
enter the Cambridge sequence (photo/PDF/table-of-contents import in a future version). Every topic
has a status LOCKED / LEARNING / LEARNED / REVISION. LOCKED topics should not normally generate
daily questions; LEARNING substantial weighting; LEARNED spaced revision; REVISION increased
weighting. Student can change statuses manually.

### 5B. Maths daily questions
Five per weekday. Initially about 2 accessible/foundation, 2 HSC-standard, 1 challenging. The
ratio changes progressively through the year. Later increase unfamiliar problems, multi-step
problems, integration of multiple syllabus areas, exam-style time pressure. Selection must not
simply become "harder every month"; it responds to actual performance.

### 5C. Maths marking
Prefer deterministic assessment (e.g. SymPy) over relying only on an LLM. Support exact values,
equivalent algebraic forms, numerical answers with tolerances, expressions, units, multiple
legitimate methods. For written working, AI may assess reasoning. Feedback identifies whether the
error was primarily: conceptual, algebraic, arithmetic, interpretation, formula selection,
incomplete reasoning, insufficient working, notation, careless error.
For every maths question provide: 1 student's answer; 2 mark; 3 correct answer; 4 complete worked
solution; 5 exact point where reasoning diverged; 6 explanation of the concept; 7 quicker or more
elegant method where appropriate; 8 examination technique; 9 syllabus outcome; 10 revision
recommendation. Do not merely say "Incorrect. The answer is 12." Teach WHY.

## 6. English Advanced — 2027
Prescribed texts: TEXTS AND HUMAN EXPERIENCES — Jessica Au, *Cold Enough for Snow*; TEXTUAL
CONVERSATIONS — Shakespeare, *Hamlet* and Emily Dickinson, prescribed poetry; CRITICAL STUDY OF
LITERATURE — Jane Austen, *Pride and Prejudice*; THE CRAFT OF WRITING — normal course preparation
and writing practice. Support the prescribed Dickinson poems as defined by the official NESA
prescription. Do not guess the prescription; verify it before seeding.

### 6A. English daily practice
Normally THREE questions per weekday: about 80% unseen-text comprehension/analysis, 20%
course-linked analytical practice (a guideline, not a rigid daily ratio). Wide variety of forms:
prose fiction, nonfiction, memoir, speeches, essays, poetry, visual texts, media, hybrid forms,
paired texts. Vary cognitive demand: identify, explain, analyse, compare, evaluate, synthesise.
Not every question "identify a technique and explain its effect". A typical session: ONE unseen
stimulus followed by three differently weighted questions; occasionally two related texts with
comparison. Realistic marks: 2, 3, 4, 5, 6. Teach how the amount of analysis changes with marks.

### 6B. Course-linked practice
Progressively reinforce Cold Enough for Snow; Hamlet + Dickinson as a textual conversation; Pride
and Prejudice as critical study; Craft of Writing. Historical questions for superseded texts must
NOT be presented as if they apply: identify transferable structures, map to the new syllabus,
create ADAPTED questions where appropriate, label them, preserve the historical inspiration.

## 7. English feedback — very high priority
After submission provide: 1 mark awarded; 2 maximum; 3 estimated performance level; 4 relevant
NESA criteria; 5 syllabus outcomes; 6 what was done well; 7 what prevented a higher mark;
8 quality of textual evidence; 9 quality of analysis; 10 understanding of form; 11 understanding
of language; 12 quality of argument; 13 structure; 14 expression; 15 precision; 16 sophistication
of interpretation; 17 what a marker expects at the next level; 18 concrete actions.
Then a BAND 6 STANDARD MODEL RESPONSE written specifically for the question (not a reproduced
copyrighted sample). Then COMPARISON WITH YOUR RESPONSE: what the model does that the student's
does not; where the student becomes descriptive; where evidence could be better integrated; where
ideas need development; how expression could be more precise; how the argument could be more
sophisticated. Where useful, YOUR ANSWER — IMPROVED: the student's answer rewritten keeping as
many original ideas as possible but lifted toward Band 6. If an official marking guideline exists,
use it. If not, state "AI-estimated mark based on NESA syllabus/performance criteria." Never imply
an AI score is an official NESA judgement.

## 8. Legal Studies — 2027
Starting areas: CRIME and HUMAN RIGHTS (core). The two option topics are not yet known: editable
Legal Studies Learning Plan; options selectable later without code changes; until activated, no
questions from an option; activate/deactivate from Settings.

### 8A. Daily legal questions
THREE per weekday. Mix: objective, short-answer, stimulus-based, explain, analyse, evaluate,
occasional extended responses. Not three large essays in 90 minutes. Gradually increase extended
responses as the HSC approaches. Friday may occasionally contain a longer Legal response provided
the rest of the day's workload is adjusted.

### 8B. Current law and contemporary evidence
A LEGAL STUDIES EVIDENCE BANK organised by topic, syllabus area, issue, case, legislation, law
reform, report, inquiry, treaty/international instrument, media example. Each item stores: title,
date, jurisdiction, topic, summary, legal significance, syllabus link, source, source URL, source
type, reliability, retrieved date, last verified date. Prioritise authoritative sources
(Australian and NSW legislation, courts, AHRC, law reform commissions, parliaments, official
government sources, reputable legal commentary); journalism only as supporting evidence. Every
contemporary example used in feedback or a model response must include a source/reference. Never
invent case names, judgments, legislation, dates or statistics. If not verifiable, say so.

### 8C. Old legal questions
Separate QUESTION SKILL RELEVANCE from LEGAL FACT CURRENCY. A historical question may still be an
excellent evaluation question while its legislation has changed: it should be ADAPTED and labelled.

## 9. Legal Studies feedback
Assess: knowledge of relevant law; legal terminology; response to the directive verb; judgement;
argument; use of legislation; use of cases; contemporary evidence; law reform; effectiveness
analysis; responsiveness to stimulus; structure; clarity; integration of evidence. Provide:
1 score; 2 marking rationale; 3 strengths; 4 missing elements; 5 factual/legal corrections;
6 evidence the student could have used; 7 improved argument; 8 Band 6-standard model answer;
9 side-by-side conceptual comparison; 10 specific improvement task. Model answers demonstrate
relevant contemporary legal evidence. Show the date legal information was last checked.

## 10. Daily question-selection engine
Not random.choice(). Each candidate gets a selection score. Factors: CURRENT TOPIC RELEVANCE,
REVISION DUE, STUDENT WEAKNESS, SYLLABUS COVERAGE GAP, DIFFICULTY FIT, SOURCE QUALITY, NOVELTY,
TIME BUDGET, QUESTION TYPE VARIETY, RECENT EXPOSURE PENALTY. Starting weights: 30% current
learning relevance, 20% weakness/historical performance, 15% spaced repetition priority, 10%
syllabus coverage gap, 10% appropriate difficulty, 10% novelty, 5% source priority — changeable
from configuration.

## 11. Never show future material too early
LOCKED topics normally excluded. Questions may draw from currently learning, previously learned,
assumed Year 11 knowledge, scheduled revision. Do not present a topic scheduled months ahead. The
purpose is to accompany classroom learning, not race ahead.

## 12. Spaced repetition
Questions normally different each day; avoid exact repetition; complete exposure history:
first_seen, last_seen, attempts, score_history, mastery, next_revision_date. STRONG ~56–70 days
before the exact question is eligible again; ADEQUATE ~28–42; WEAK ~14–21; VERY WEAK/INCORRECT
~7. Before repeating an identical question, present a different question testing the same skill.
After about two months, intentionally recycle important previously successful concepts (two-month
revision cycle). Adapt intervals to performance rather than fixed dates only.

## 13. Duplicate detection
Question fingerprint, normalized text hash, ideally semantic similarity. Do not ask effectively
identical questions on consecutive days.

## 14. Daily time budget
Target ~90 minutes; each question has an estimated completion time (use historical exam
mark/time relationships). Calculate expected_total_minutes; aim 80–95. If exceeded, replace long
questions with shorter appropriate ones. Do not remove a subject; preserve 5/3/3 except in
deliberately activated special modes.

## 15. School holidays
Runs Mon–Fri all year, including NSW school holidays. Modes: NORMAL, HOLIDAY/REVISION, EXAM,
LIGHT DAY. Holiday mode may reduce new content, increase revision, focus on weak topics,
optionally shorten duration. Student can override.

## 16. Missed days
If Tuesday is missed, do not force 22 questions on Wednesday. Record the missed session. Provide:
Resume missed session; Skip session; Move important revision items forward. No workload
accumulation.

## 17. Daily session behaviour
Generated when first opened; NOT changed by browser refresh; persisted in SQLite. Show: today's
date, session number, expected duration, Maths 0/5, English 0/3, Legal 0/3, overall progress,
timer, estimated remaining time. Allow autosave, save and continue, return later, pause timer.

## 18. Answer reveal
No model answers before an honest attempt unless the student explicitly chooses SHOW ANSWER /
SKIP — then record as skipped, not correct. After submission provide feedback. Allow hiding
detailed feedback temporarily and continuing.

## 19. Confidence
Optionally ask "How confident were you?": Guess / Unsure / Reasonably confident / Very confident.
Use in revision scheduling. A lucky correct "Guess" is not mastered. A careless error with high
conceptual performance is treated differently from complete misunderstanding.

## 20. Dashboard
TODAY (questions due, expected time, Start/Continue); STREAK (weekdays completed); THIS WEEK
(questions completed, time studied, average performance); SUBJECT STATUS (3 subjects); REVISION
DUE; WEAK AREAS; RECENT IMPROVEMENT; NEXT TOPICS. Not childish gamification; appropriate for a
serious Year 12 student.

## 21. Progress analytics
Views: 7, 30, 60, 90 days, all time. Show accuracy; average marks; marks by subject, topic,
syllabus outcome; performance by difficulty; revision performance; time per question; repeated
errors; strongest/weakest areas; syllabus coverage; topics not yet assessed; response length
where appropriate. Provide interpretation, e.g. "You are consistently strong at differentiation
mechanics but lose marks when calculus is embedded in modelling questions." / "Your English
responses identify techniques accurately but analysis of how textual form shapes meaning remains
less developed."

## 22. HSC readiness
An HSC READINESS indicator (not "PREDICTED HSC MARK"); no false precision. Combine: syllabus
coverage, recent performance, unseen performance, performance at HSC difficulty, revision
retention, timed performance, consistency. Explain how it is calculated.

## 23. Error journal
Automatic ERROR JOURNAL. Maths: sign errors, chain rule, algebra, domain/range, calculator error,
probability interpretation. English: insufficient textual evidence, technique identification
without analysis, weak thesis, descriptive response, poor comparison, limited evaluation,
imprecise expression. Legal: missing authority, outdated legislation, weak judgement, description
instead of evaluation, insufficient contemporary evidence, poor use of cases, failure to address
directive verb. Reviewable at any time.

## 24. "WHY DID I LOSE THE MARK?"
A prominent button for every assessed question producing an educational explanation rather than
repeating the marking feedback (e.g. "You correctly identified metaphor, but this was a 4-mark
question ... connect the metaphor to the writer's larger representation of memory ..."). A
signature feature.

## 25. Retry
TRY AGAIN after feedback; rewrite before viewing the full model answer if desired; store Attempt
1, Attempt 2; show improvement between them. Especially valuable for English and Legal.

## 26. Question library
Administration page QUESTION LIBRARY, filter by subject, year, source, topic, syllabus outcome,
marks, difficulty, relevance, approved/rejected, attempted/not attempted, performance, next
revision date. Question detail: original question, source, marking guidelines, syllabus mapping,
relevance classification, mapping rationale, attempt history, feedback history.

## 27. Curriculum / learning plan screen
Per subject. Maths: textbook/syllabus sequence with statuses. English: Texts and Human
Experiences (Cold Enough for Snow); Textual Conversations (Hamlet + Emily Dickinson); Critical
Study of Literature (Pride and Prejudice); Craft of Writing — currently studied module changeable
manually. Legal: Crime; Human Rights; Option 1 — not selected; Option 2 — not selected (editable).

## 28. AI architecture
Not hard-coded to one AI company. An AIProvider abstraction with classify_question(),
map_to_syllabus(), mark_response(), generate_feedback(), generate_model_answer(),
generate_question_variant(), summarise_legal_source(). Implement at least one provider (OpenAI-
compatible acceptable); Anthropic or another can be added later. API keys from environment
variables; never hard-coded; provide .env.example; do not commit secrets.

## 29. AI prompt quality
Not "Mark this." Structured marking prompts with: subject, syllabus, outcome, question, marks,
directive verb, official marking guideline if available, performance band information, source
context, student response. Require structured JSON (mark_awarded, mark_possible, confidence,
criteria, strengths, weaknesses, errors, improvements, model_answer, comparison,
revision_recommendation). Validate before storing. Malformed AI output must never corrupt the DB.

## 30. Factual safety for Legal Studies
Where a response refers to current legislation, recent cases, law reform, current policy:
require sources where possible. If no reliable source has been retrieved, do not let the AI
confidently invent authorities. Display "Current information checked: [DATE]". Education, not
legal advice.

## 31. Historical paper ingestion
Pipeline (PyMuPDF / pdfplumber / pypdf; OCR optional fallback): 1 register source; 2 download or
import PDF; 3 retain original PDF; 4 extract text; 5 identify subject/year; 6 question
boundaries; 7 marks; 8 detect diagrams/stimuli; 9 associate marking guideline; 10 map to
syllabus; 11 calculate relevance; 12 uncertain mappings to review queue; 13 approve; 14 add to
pool. Automated parsing will not always work: provide a human review interface.

## 32. Source registry
Source table: id, title, organisation, year, subject, source_type, url, local_file,
retrieved_date, official, notes. Questions reference Source IDs.

## 33. Suggested database model
SQLite v1, SQLAlchemy + migrations. Tables such as subjects, syllabus_versions,
syllabus_outcomes, syllabus_topics, learning_plan_items, prescribed_texts, sources,
source_documents, stimuli, questions, question_parts, question_mappings, marking_guidelines,
daily_sessions, session_questions, attempts, attempt_feedback, mastery, revision_queue,
error_journal, legal_evidence, legal_evidence_topics, settings. Important state not only in
browser localStorage; SQLite is the source of truth.

## 34. Question table — important fields
id, subject_id, source_id, source_year, question_number, source_page, question_text,
question_image, stimulus_id, marks, question_type, directive_verb, difficulty, estimated_minutes,
topic_id, syllabus_outcome_id, relevance_status, relevance_score, mapping_confidence,
historical_or_generated, generated_from_question_id, answer, marking_guideline, fingerprint,
approved, created_at, updated_at.

## 35. User experience
Clean, calm, quick. Not a corporate analytics platform; not a children's game. Generous spacing,
readable typography. Pages: / Dashboard; /today; /review; /progress; /errors; /curriculum;
/questions; /legal-evidence; /settings. Desktop Chrome first; responsive so phone/tablet possible
later.

## 36. Mathematical input
Readable maths: MathJax or KaTeX. Typed answers; LaTeX-style input where practical; do not
require complex LaTeX for simple answers.

## 37. English / Legal writing interface
Distraction-free writing area; display question, marks, suggested time, optional timer, word
count. Suggested word count is not an inflexible target. Full-screen writing mode. Autosave
frequently.

## 38. Settings
timezone (default Australia/Sydney); target daily minutes (default 90); weekdays (default
Mon–Fri); holiday behaviour; AI provider; AI model; API key status; question-source preferences;
subject learning plans; Legal Studies options; difficulty behaviour; revision intensity; feedback
depth.

## 39. Data portability
EXPORT BACKUP / IMPORT BACKUP (database + relevant settings, safe format); progress export to
CSV. A year's data must not disappear because the project folder was replaced.

## 40. Privacy
Bind to 127.0.0.1 by default; LAN/tablet access only as an explicit option. Only send what AI
evaluation needs to the configured AI service.

## 41. Technical stack
Python 3.12+; FastAPI or Flask; SQLAlchemy; SQLite; Alembic; Jinja2; vanilla JS / HTMX where
helpful; normal CSS or lightweight framework; PyMuPDF/pdfplumber; SymPy; MathJax/KaTeX. Avoid
unnecessary complexity; no React + Node unless compelling. Maintainable by a non-full-time
engineer.

## 42. Project structure
Approximately: app/ (main.py, config.py, models/, routes/, services/, repositories/, ai/,
ingestion/, selection/, marking/, templates/, static/), migrations/, data/, imports/, tests/,
scripts/ (import_nesa.py, seed_syllabus.py, backup.py), .env.example, requirements.txt or
pyproject.toml, README.md, run.sh. Responsibilities separated; not one 6,000-line app.py.

## 43. Startup experience
python -m venv .venv; source .venv/bin/activate; pip install -r requirements.txt; cp .env.example
.env; python -m app; open http://127.0.0.1:8000. Ideally run.sh. README explains setup clearly.

## 44. First-run wizard
Ask: HSC year 2027; timezone Australia/Sydney; daily target 90 minutes. Subjects: the three.
Pre-populate English texts (Cold Enough for Snow; Hamlet + Emily Dickinson; Pride and Prejudice).
Pre-populate Legal starting areas (Crime; Human Rights); leave Legal options unselected. Maths
plan initially based on the current NESA course, with the ability to enter the Cambridge sequence
(now confirmed — see 5A above).

## 45. 2027 first-exam problem
Historical data alone will not give complete coverage for the new Maths and English syllabuses.
Every syllabus area shows HISTORICAL QUESTION COVERAGE (e.g. Integral calculus GOOD; New
modelling descriptor LIMITED; Random variables MODERATE). Where weak: 1 official 2027 sample
material first; 2 directly transferable historical questions; 3 clearly labelled syllabus-aligned
generated questions. Never silently fill the database with invented "past HSC questions".

## 46. Daily session explanation
Optionally show WHY THESE QUESTIONS? e.g. "Two of today's Mathematics questions reinforce the
calculus work currently marked Learning. One revises logarithms from Year 11. The probability
question is here because your accuracy in that area is currently 58%."

## 47. End-of-day summary
After all 11: Time; Maths x/y; English x/y; Legal x/y; then TODAY'S STRENGTH, MAIN LEARNING, TOP
PRIORITY, REVISION SCHEDULED. Do not overwhelm; deeper analysis on the Progress screen.

## 48. Weekly review
At the end of Friday's session: THIS WEEK — sessions completed, questions attempted, study time,
strongest improvement, persistent weakness, next week's priority, revision coming due.

## 49. Monthly review
Syllabus coverage, topic mastery, improvement, weak areas, response quality, time management,
revision retention, suggested priorities. Interpret, do not just report raw marks.

## 50. Testing
At minimum test: daily question counts; no locked topic appears; no Extension Maths question
appears; duplicate questions suppressed; correct spaced repetition; missed-day behaviour;
time-budget logic; daily session persists after refresh; source attribution persists; REJECT
questions cannot be selected; Legal option questions unavailable until activated; AI JSON
validation; database backup/restore; mathematics equivalent-answer checking. Useful fixtures.

## 51. Quality control scenarios
A: just started a new Maths chapter → most questions on that chapter plus controlled older
revision; no future chapter. B: maths question completely wrong → detailed solution, error
classification, earlier revision scheduling. C: superficial 4-mark English response →
appropriate partial mark, explanation of missing analysis, Band 6 model response, useful
comparison. D: Legal answer using outdated legislation → identifies the problem and provides
verified current evidence. E: everything right for weeks → difficulty rises progressively.
F: struggling badly → difficulty adapts down to rebuild understanding without abandoning
HSC-standard questions completely.

## 52. Administrative review tool
Review page for imported questions: question, source, proposed 2027 topic, proposed outcome,
relevance category, AI explanation, confidence score. Buttons: APPROVE, EDIT MAPPING, MARK
ADAPTABLE, REJECT. Do not pretend automated mapping is infallible.

## 53. Auditability
For every question: Where did this come from? Why is it relevant? Which syllabus outcome does it
test? Unobtrusively beneath the question, e.g. "Source: NESA Mathematics Advanced HSC 2023
Q12(b) · 2027 mapping: Differential calculus · Relevance: Direct".

## 54. Future: Tutor mode
Not mandatory for v1, but design the database so a future Tutor Mode can inspect progress,
assign topics/questions, see error patterns, leave comments, set next week's focus. Do not let it
overcomplicate v1.

## 55. Implementation phases
1 Foundation; 2 Question engine; 3 Daily study; 4 Assessment; 5 Adaptive learning; 6 Legal
evidence; 7 Analytics; 8 Hardening. Each phase leaves a runnable application.

## 56. Do NOT
Use random selection as primary logic; assume old syllabus questions apply; invent NESA
questions; invent NESA marking guidelines; claim AI marking is official; serve Maths Extension
content; serve future topics early; fabricate Australian cases or legislation; give a Legal model
response with invented evidence; lose answers after refresh; regenerate the day's questions on
refresh; accumulate enormous workloads after missed days; expose API keys; depend on an internet
connection for basic historical study once material is imported; scrape and redistribute
commercial resources; hard-code Legal option topics; assume the Cambridge order without obtaining
it; hide where questions came from; call generated questions "past HSC questions".

## 57. Definition of success
On an ordinary school night the student opens Chrome, clicks START TODAY and receives ~90 minutes
of practice which: matches what they are learning; revises learned material; uses genuine past
HSC material wherever appropriate; recognises the 2027 syllabus differs; avoids repetition;
revisits weaknesses intelligently; provides exceptional explanations after mistakes; demonstrates
Band 6 responses in English and Legal; uses contemporary legal evidence; shows where every
question came from; remembers performance over the whole course; becomes more exam-like as the HSC
approaches. The student should feel the app knows: what I have learned; what I am learning; what I
struggle with; what I have forgotten; what I need to practise next.

## 58. What to produce
Build the application (not architectural advice): review spec; identify blockers; project
structure; schema; Phase 1; run; test; then phase by phase. Do not ask minor design questions;
choose sensible documented defaults; only stop for decisions that materially change the
educational purpose. Provide complete source code, dependency file, migrations, tests, README,
.env.example, startup script, seed data, import tools. At the end: exact install instructions;
exact startup instructions; what is fully implemented; what remains incomplete; API keys needed;
NESA/source material to import manually; how to back up. DO NOT SUBSTITUTE A MOCK-UP FOR A WORKING
APPLICATION.
