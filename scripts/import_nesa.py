"""Import an examination paper (and optional marking guidelines) into the question bank.

    python scripts/import_nesa.py paper.pdf --title "NESA 2023 HSC Mathematics Advanced" \
        --type hsc_exam --subject MATHS --year 2023 --guideline guidelines.pdf --url https://...

Types: hsc_exam (NESA HSC), sample_exam (NESA sample/specimen), trial (TRIAL / NON-NESA).
Download the PDFs yourself from the NESA website; this tool does not scrape anything.
Uncertain mappings go to the review queue (Questions -> Review queue).
"""
import argparse
from pathlib import Path

import _bootstrap  # noqa: F401

from app.database_setup import prepare_database
from app.db import session_scope
from app.ingestion.pipeline import import_paper


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
    a = ap.parse_args()
    prepare_database(seed=True)
    with session_scope() as db:
        r = import_paper(db, a.pdf, title=a.title, source_type=a.type, subject_code=a.subject, year=a.year, url=a.url,
                         guideline_pdf=a.guideline, organisation=a.organisation)
    print(f"Imported {r.questions} questions: {r.approved} approved, {r.queued} queued for review, {r.rejected} rejected, {r.duplicates} duplicates skipped.")
    for w in r.warnings:
        print("  warning:", w)


if __name__ == "__main__":
    main()
