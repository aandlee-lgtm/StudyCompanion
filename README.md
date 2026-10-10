# HSC Companion 2027

A local, year-long study companion for a NSW Year 12 student sitting the **2027 HSC** in
**Mathematics Advanced**, **English Advanced** and **Legal Studies**. It runs on your own
computer and you use it in Google Chrome.

Every weekday it builds a personalised session of about 90 minutes: **5 Maths, 3 English
(mostly unseen texts) and 3 Legal Studies questions**. The session is chosen from what you are
learning, what you have learned, what you got wrong and what is due for revision. It never
serves LOCKED (future) topics, Extension Maths, or REJECT questions.

## Install (once)

You need Python 3.12 or newer.

```bash
git clone https://github.com/aandlee-lgtm/StudyCompanion.git
cd StudyCompanion
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # edit it later if you want AI marking
```

## Start

```bash
./run.sh                 # or: source .venv/bin/activate && python -m app
```

Open **http://127.0.0.1:8000** in Chrome. The first visit shows a short setup wizard. To stop
the app, press Ctrl+C.

The database is created and upgraded automatically (Alembic migrations) at
`data/hsc_companion.db`.

## AI marking (optional, recommended for English and Legal)

Without AI ("offline", the default):
- **Maths and multiple choice are marked exactly**, with SymPy for equivalent forms.
- **Written English and Legal answers** get a rough, clearly labelled estimate. You still see the
  app's model answers, the criteria and "Why did I lose the mark?".

With AI, set these in `.env`:

```
HSC_AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1   # any OpenAI-compatible endpoint
HSC_AI_MODEL=gpt-4o
```

Keys are read only from the environment; they are never stored in the database or committed.
Only the question, its context and your answer are sent. AI marks are always labelled
"AI-estimated mark based on NESA syllabus/performance criteria", unless an official NESA
marking guideline is attached to that question. AI output is validated against strict JSON
schemas; invalid output is retried once and then discarded (the offline estimate is shown
instead). To add another provider (e.g. Anthropic), subclass `app/ai/base.py:AIProvider` and
implement `_complete()`.

## What you need to provide

1. **NESA papers and marking guidelines.** The app ships with **no** NESA questions; it never
   invents them. Download the PDFs from the NESA website yourself, then import them under
   Questions → Import a paper, or from the command line:
   ```bash
   python scripts/import_nesa.py paper.pdf --title "NESA 2023 HSC Mathematics Advanced" \
       --type hsc_exam --subject MATHS --year 2023 --guideline guidelines.pdf
   ```
   Uncertain mappings wait in **Questions → Review queue** until you approve them. Start with
   the **2027 sample papers** (`--type sample_exam`), because 2027 is the first exam under the
   new Maths and English syllabuses. Trial papers (`--type trial`) are labelled
   TRIAL / NON-NESA.
2. **The prescribed Emily Dickinson poems**, under Learning plan → English. Confirm the other
   texts against the NESA prescriptions and tick "confirmed".
3. **Official syllabus outcome codes**, added per focus area under the Learning plan.
4. **Legal evidence.** The seeded items (Crimes Act, Bail Act, UDHR, Mabo, …) are marked **not
   yet verified**. Open each source and click "Mark verified today". Add current cases, reforms
   and reports as you meet them.
5. **School holiday dates** (Settings), if you want automatic holiday mode.
6. **Your Legal option topics**, once you know them: Learning plan → Legal Studies → Activate option.

## Back up

- **Settings → Export backup** downloads a `.zip` of the whole database. **Import backup**
  restores one; a safety copy of the current data is saved first.
- Command line: `python scripts/backup.py --out ~/Backups` (store backups outside the project
  folder). Restore with `python scripts/backup.py --restore file.zip`.
- Progress → **Export all answers (CSV)**.

## What's included

| Area | Status |
|---|---|
| First-run wizard, dashboard, learning plans (statuses, drag-and-drop/numeric reorder, "start here", sequence import, Legal options) | Done |
| Daily session engine: weighted scoring, quotas, duplicate suppression, 80–95 min budget, saved in SQLite (a refresh never regenerates it), timers, autosave, missed days, modes (normal/holiday/exam/light), "Why these questions?" | Done |
| Maths: 66 SymPy templates across 1A–10F and Year 11 (labelled GENERATED, with worked solutions); exact/equivalent/tolerance/units/sets/primitive marking; error classification; ten-part feedback | Done |
| English: original unseen passages (5 texts, 1 paired) with Band 6 model answers; course-linked questions for each module; AI marking with comparison and an improved version of your answer | Done (more unseen texts needed) |
| Legal: MCQ, short and extended questions; evidence bank (manual or fetched from a URL plus AI summary); citation check flags authorities not in your verified bank; "Current information checked" date | Done |
| "Why did I lose the mark?", Try again (attempt 1 vs 2), confidence ratings, spaced repetition, error journal | Done |
| Question library, filters, detail and audit trail; source registry; PDF ingestion (PyMuPDF → pdfplumber → optional OCR), diagram rendering, guideline matching; admin review (Approve / Edit mapping / Mark adaptable / Reject) | Done |
| Progress (7/30/60/90/all), written interpretation, HSC READINESS, historical-coverage indicator, end-of-day / weekly / monthly reviews | Done |
| Backup/restore, CSV export, 73 automated tests including quality scenarios A–F | Done |

## Not yet done

- AI **generation of new questions or unseen texts** is defined in the provider interface
  (`generate_question_variant`) but not yet wired into the daily engine. Until it is, the
  English and Legal banks grow by importing papers. Maths never runs out because of the
  templates.
- The seeded English and Legal banks are small (about 4 days of unseen English before repeats,
  which are labelled as such). Import material early.
- Seeded questions are short, so early sessions run about 55–75 minutes (the session says so).
  Longer imported HSC questions bring sessions up to 90 minutes.
- Importing a table of contents from a photo or PDF, and Tutor Mode (the database is ready
  for it).
- PDF question segmentation is heuristic: check every import in the review queue.

## Development

```bash
python -m pytest -q          # 73 tests
```

The project is laid out as follows:

| Folder | Contents |
|---|---|
| `app/models` | Tables |
| `app/selection` | Daily selection engine |
| `app/marking` | SymPy marking and the offline rubric |
| `app/ai` | Providers, prompts and JSON schemas |
| `app/ingestion` | PDF pipeline |
| `app/services` | Sessions, assessment, mastery, analytics, backup |
| `app/routes`, `app/templates` | User interface |
| `migrations/` | Alembic migrations |
| `data/seed/` | Editable seed JSON |
| `scripts/` | Command-line tools |
| `tests/` | Automated tests |

Design defaults are listed in [docs/DECISIONS.md](docs/DECISIONS.md). The confirmed Maths
sequence is in [docs/5A-maths-learning-sequence.md](docs/5A-maths-learning-sequence.md).

This is a private study tool. It does not redistribute examination or commercial material:
imported PDFs stay in `data/sources/` and are git-ignored. Legal feedback is educational,
not legal advice.
