"""How tests/fixtures/v1_database.sqlite.gz was built (kept for reference; not collected by pytest).

Build a database with the v1 app (e18d23d): migrate to 0001, seed v1 content, complete setup,
create two days of sessions and answer every question (MCQ right, Maths wrong, written answers,
every fourth question skipped). Usage: git archive e18d23d | tar -x -C /tmp/v1 && python3 tests/fixtures/make_v1_database.py /tmp/v1 /tmp/v1data
(then VACUUM /tmp/v1data/hsc.db and gzip -9 it)."""
import sys
from datetime import date, timedelta
from pathlib import Path

tree, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(tree))
from app.config import config  # noqa: E402

config.data_dir = out
from app.database_setup import prepare_database  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services import assessment, clock, sessions  # noqa: E402
from app.services import settings as st  # noqa: E402

day1 = date(2026, 10, 13)
clock.set_today(day1)
prepare_database(f"sqlite:///{out / 'hsc.db'}")
db = SessionLocal()
st.set_(db, "setup_complete", True)
st.set_(db, "year12_start_date", day1.isoformat())
st.set_(db, "student_name", "V1 Student")
db.commit()
for d in (day1, day1 + timedelta(days=1)):
    clock.set_today(d)
    s = sessions.get_or_create_today(db)
    db.commit()
    for i, sq in enumerate(s.questions):
        q = sq.question
        if i % 4 == 3:
            assessment.submit(db, q, "", sq=sq, skipped=True, today=d)
        elif q.answer and q.answer.get("type") == "mcq":
            assessment.submit(db, q, q.answer["value"], sq=sq, confidence="confident", today=d)
        elif q.answer:
            assessment.submit(db, q, "999999", sq=sq, confidence="unsure", today=d)
        else:
            assessment.submit(db, q, (q.model_answer or "A short answer about the text and its ideas.")[:400], sq=sq, today=d)
        db.commit()
from sqlalchemy import text  # noqa: E402

counts = {t: db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in
          ("attempts", "attempt_feedback", "daily_sessions", "session_questions", "questions", "error_journal", "question_exposure",
           "revision_queue", "mastery", "learning_plan_items", "legal_evidence", "stimuli", "settings")}
print(counts)
print("version", db.execute(text("SELECT version_num FROM alembic_version")).scalar())
db.close()
