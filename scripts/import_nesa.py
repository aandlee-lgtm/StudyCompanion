"""Import an examination paper (and optional marking guidelines) into the question bank.

    python scripts/import_nesa.py paper.pdf --title "NESA 2023 HSC Mathematics Advanced" \
        --type hsc_exam --subject MATHS --year 2023 --guideline guidelines.pdf --url https://...
    python scripts/import_nesa.py p1.pdf --title "NESA 2025 HSC English Advanced Paper 1" \
        --guideline p1_mg.pdf --stimulus p1_stimulus.pdf --dry-run

--dry-run prints the segmentation table (marks, parts, options, key, guideline match) and the
expected/detected counts without saving anything. --replace re-segments a PDF imported before
(attempted or approved questions are kept).

Types: hsc_exam (NESA HSC), sample_exam (NESA sample/specimen), trial (TRIAL / NON-NESA).
Download the PDFs yourself from the NESA website; this tool does not scrape anything.
Uncertain mappings go to the review queue (Questions -> Review queue).
"""
import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from app.database_setup import prepare_database
from app.db import session_scope
from app.ingestion.pipeline import ImportFailed, import_paper


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--title", required=True)
    ap.add_argument("--type", default="hsc_exam", choices=["hsc_exam", "sample_exam", "trial"])
    ap.add_argument("--subject", choices=["MATHS", "ENGLISH", "LEGAL"])
    ap.add_argument("--year", type=int)
    ap.add_argument("--url")
    ap.add_argument("--organisation")
    ap.add_argument("--guideline", type=Path)
    ap.add_argument("--guideline-kind", choices=["official_nesa", "school_trial", "third_party"])
    ap.add_argument("--stimulus", type=Path, help="English Paper 1 stimulus booklet (PDF)")
    ap.add_argument("--dry-run", action="store_true", help="print the segmentation table; save nothing")
    ap.add_argument("--replace", action="store_true", help="re-segment a PDF that was imported before")
    ap.add_argument("--confirm-subject", action="store_true", help="import even if --subject differs from the detected subject")
    a = ap.parse_args()
    prepare_database(seed=True)
    try:
        with session_scope() as db:
            r = import_paper(db, a.pdf, title=a.title, source_type=a.type, subject_code=a.subject, year=a.year, url=a.url,
                             guideline_pdf=a.guideline, organisation=a.organisation, stimulus_pdf=a.stimulus,
                             guideline_kind=a.guideline_kind, dry_run=a.dry_run, replace=a.replace, confirm_subject=a.confirm_subject)
    except ImportFailed as exc:
        raise SystemExit(f"Import refused: {exc}")
    for e in r.expected:
        flag = "" if e["expected"] == e["detected"] else "   <-- check"
        print(f"Section {e['section']} ({e['mode']}): expected {e['expected']} (Questions {e['range']}), detected {e['detected']}{flag}")
    if r.guideline_total:
        print(f"Marking guideline matched for {r.guideline_matched}/{r.guideline_total} written units.")
    if r.mcq_total:
        print(f"Multiple-choice key found for {r.mcq_keyed}/{r.mcq_total}.")
    if a.dry_run:
        print(f"{'Q':8} {'sec':4} {'marks':5} {'parts':12} {'opt':3} {'key':3} {'gl':3} issues / start of text")
        for s in r.segments:
            print(f"{s['number']:8} {s['section']:4} {str(s['marks'] if s['marks'] is not None else '?'):5} {' '.join(s['parts']):12} "
                  f"{s['options'] or '':3} {s['key'] or '':3} {'yes' if s['guideline'] else '':3} {'; '.join(s['issues']) or s['preview'][:60]}")
        print("Dry run: nothing was saved.")
    else:
        print(f"Imported {r.questions} questions: {r.approved} approved (passed every check), {r.queued} queued for review "
              f"({r.needs_fix} need fixing), {r.rejected} rejected, {r.duplicates} duplicates skipped, {r.failed} failed, {r.stimuli} texts.")
    for w in r.warnings:
        print("  warning:", w)
    for e in r.errors:
        print("  error:", e)


if __name__ == "__main__":
    main()
