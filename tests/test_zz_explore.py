from sqlalchemy import select
from app.ingestion import pipeline
from app.models import Question, Stimulus
from tests import v2_ingestion_fixtures as fx

def show(db, r):
    print("REPORT", r.subject, r.year, "q", r.questions, "appr", r.approved, "queued", r.queued, "rej", r.rejected, "fix", r.needs_fix, "fail", r.failed, "stim", r.stimuli, "gl", r.guideline_matched, r.guideline_total, "mcq", r.mcq_keyed, r.mcq_total)
    print("WARN", r.warnings[:6], "ERR", r.errors[:4])
    for q in db.execute(select(Question).where(Question.source_id == r.source_id)).scalars():
        m = q.import_meta or {}
        print(f"Q {q.question_number:8} {q.marks:2} {q.question_type:12} {q.relevance_status:9} {q.approval_status:8} item={q.plan_item_id} cat={q.category} ans={q.answer} parts={[(p.label,p.marks) for p in q.parts]} :: {q.question_text[:70]!r}")
        print("   VAL", [i['code'] for i in m.get('validation', [])], m.get('mapping_state'))

def test_all(db, tmp_path):
    f = fx.build_all(tmp_path / "fx")
    show(db, pipeline.import_paper(db, f["maths"], title="NESA 2025 HSC Mathematics Advanced", guideline_pdf=f["maths_mg"]))
    show(db, pipeline.import_paper(db, f["english"], title="NESA 2025 HSC English Advanced Paper 1", guideline_pdf=f["english_mg"], stimulus_pdf=f["english_stimulus"]))
    show(db, pipeline.import_paper(db, f["legal"], title="NESA 2025 HSC Legal Studies", guideline_pdf=f["legal_mg"]))
    print("STIM", [(s.title, s.attribution[:30]) for s in db.execute(select(Stimulus).where(Stimulus.provenance=="historical")).scalars()])
    assert 0
