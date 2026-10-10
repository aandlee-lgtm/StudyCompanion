# Design decisions and defaults (version 1)

Low-risk choices made without asking, as the specification allowed. Each one can be changed.

| Area | Decision | Where to change |
|---|---|---|
| Stack | FastAPI + Jinja2 + SQLAlchemy 2 + SQLite + Alembic; vanilla JS; KaTeX bundled locally (works offline). | — |
| Server | Binds to 127.0.0.1:8000. A warning is printed if `HSC_HOST` is set to anything else. | `.env` |
| AI | Provider-neutral `AIProvider`; an OpenAI-compatible provider plus an **offline** provider. Offline: Maths and multiple choice are still marked exactly; written answers get a clearly labelled feature-based estimate. | `.env`, Settings |
| Maths sequence | Your confirmed CambridgeMATHS Year 12 sequence (1A–10F, 64 subtopics). Each subtopic is linked to a 2027 NESA focus area by default (e.g. 2H → Applications of calculus); edit in the Learning plan. 3D and 6F are ENRICHMENT. | Learning plan |
| Year 11 | Six Year 11 assumed-knowledge items, status LEARNED, used only for controlled revision. Three names are marked "to be confirmed". | Learning plan |
| English | Unseen texts, Texts and human experiences and The craft of writing start LEARNING; Textual conversations and Critical study start LOCKED. | Learning plan |
| Legal | Crime and Human rights LEARNING; the seven option topics are listed but inactive. | Learning plan |
| Outcomes | Official outcome codes were **not** seeded (they couldn't be verified). Each focus area has a placeholder; add the official outcomes in the Learning plan. | Learning plan |
| Dickinson poems | **Not** seeded (couldn't be verified from NESA). Enter the list in the Learning plan. | Learning plan |
| Selection weights | 30/20/15/10/10/10/5 (current, weakness, spaced, coverage, difficulty, novelty, source). Holiday mode reduces "current" and raises spaced and weakness. | Settings |
| Maths mix | 55% learning / 25% recent / 20% older; difficulty starts 2 foundation / 2 HSC / 1 challenging and shifts with year progress and performance (always keeping HSC-standard work). | Settings |
| Exact repeats | Strong 56–70 days, adequate 28–42, weak 14–21, very weak 7. Weak skills also get a *different* question in 2–5 days; strong skills are recycled at about 60 days. A correct "Guess" is not treated as mastered. | Settings (intensity) |
| English | About 80% unseen. One passage per day; a course-linked question when the recent share falls below 20%. | Settings |
| Legal extended responses | None early in the year; Fridays from about 15% of the way through the year (at most one every 3 sessions); more often after 60% and in exam mode. Never more than one a day. | `app/selection/engine.py` |
| Time estimates | Maths and Legal 1.8 min per mark, English 1.75 min per mark, plus reading time for passages (110 words/min); MCQ 1.5 min. | `app/services/question_bank.py` |
| HSC date | 11 October 2027 is an estimate, used only to measure progress through the year. | Settings |
| Holidays | Not pre-filled (school-specific). Enter the date ranges; "auto" mode switches to holiday/revision mode during them. | Settings |
| Auto-approval | Imported questions are approved automatically only when an AI mapping is DIRECT with confidence ≥ 0.85. Offline keyword mapping always goes to the review queue. | Settings key `auto_approve_direct_confidence` |
| Tutor Mode | Not built. A `students` table, `student_id` columns and a `tutor_comments` table are in place for it. | — |
