"""v2 adaptive: attempt chain flags, revision-queue lifecycle, error-journal axes, mastery state,
practice drafts, exposure event log and revision sets.

Revision ID: 0002_adaptive
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_adaptive"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("attempts") as b:
        b.add_column(sa.Column("counts_for_mastery", sa.Boolean(), nullable=False, server_default="1"))
        b.add_column(sa.Column("after_reveal", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("evidence_role", sa.String(length=20), nullable=True))
        b.add_column(sa.Column("model_viewed_at", sa.DateTime(), nullable=True))
    # v1 data: only first attempts updated the schedule
    op.execute("UPDATE attempts SET counts_for_mastery = CASE WHEN attempt_number = 1 THEN 1 ELSE 0 END, "
               "evidence_role = CASE WHEN attempt_number = 1 THEN 'first' ELSE 'retry' END")

    with op.batch_alter_table("mastery") as b:
        b.add_column(sa.Column("state", sa.String(length=20), nullable=False, server_default="normal"))
        b.add_column(sa.Column("state_since", sa.Date(), nullable=True))
        b.add_column(sa.Column("rebuild_correct", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("lapses", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("ease", sa.Float(), nullable=False, server_default="2.0"))
        b.add_column(sa.Column("last_success", sa.Date(), nullable=True))

    with op.batch_alter_table("question_exposure") as b:
        b.add_column(sa.Column("ease", sa.Float(), nullable=False, server_default="2.0"))
        b.add_column(sa.Column("lapses", sa.Integer(), nullable=False, server_default="0"))

    with op.batch_alter_table("revision_queue") as b:
        b.add_column(sa.Column("kind", sa.String(length=30), nullable=False, server_default="weak_revisit"))
        b.add_column(sa.Column("tag", sa.String(length=60), nullable=True))
        b.add_column(sa.Column("source_attempt_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("completed_at", sa.Date(), nullable=True))
        b.add_column(sa.Column("served_by_attempt_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("outcome", sa.Float(), nullable=True))
    op.execute("UPDATE revision_queue SET kind = 'recycle' WHERE reason LIKE 'Two-month recycle%'")

    with op.batch_alter_table("error_journal") as b:
        b.add_column(sa.Column("topic_tag", sa.String(length=60), nullable=True))
        b.add_column(sa.Column("study_date", sa.Date(), nullable=True))
        b.add_column(sa.Column("fixed_on_retry", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("resolved_on", sa.Date(), nullable=True))
        b.add_column(sa.Column("auto_resolved", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("source", sa.String(length=20), nullable=True))

    op.create_table(
        "practice_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("time_seconds", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "question_id"),
    )
    op.create_table(
        "exposure_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("plan_item_id", sa.Integer(), nullable=True),
        sa.Column("study_date", sa.Date(), nullable=False),
        sa.Column("fraction", sa.Float(), nullable=False),
        sa.Column("evidence", sa.Float(), nullable=False),
        sa.Column("reliability", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=True),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("outcome_kind", sa.String(length=30), nullable=False),
        sa.Column("bucket", sa.String(length=20), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("time_seconds", sa.Integer(), nullable=False),
        sa.Column("after_reveal", sa.Boolean(), nullable=False),
        sa.Column("counted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["plan_item_id"], ["learning_plan_items.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exposure_events_plan_date", "exposure_events", ["plan_item_id", "study_date"])
    op.create_table(
        "revision_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("created_on", sa.Date(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expected_minutes", sa.Float(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("revision_sets")
    op.drop_index("ix_exposure_events_plan_date", table_name="exposure_events")
    op.drop_table("exposure_events")
    op.drop_table("practice_drafts")
    with op.batch_alter_table("error_journal") as b:
        for c in ("source", "auto_resolved", "resolved_on", "fixed_on_retry", "study_date", "topic_tag"):
            b.drop_column(c)
    with op.batch_alter_table("revision_queue") as b:
        for c in ("outcome", "served_by_attempt_id", "completed_at", "source_attempt_id", "tag", "kind"):
            b.drop_column(c)
    with op.batch_alter_table("question_exposure") as b:
        for c in ("lapses", "ease"):
            b.drop_column(c)
    with op.batch_alter_table("mastery") as b:
        for c in ("last_success", "ease", "lapses", "rebuild_correct", "state_since", "state"):
            b.drop_column(c)
    with op.batch_alter_table("attempts") as b:
        for c in ("model_viewed_at", "evidence_role", "after_reveal", "counts_for_mastery"):
            b.drop_column(c)
