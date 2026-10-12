"""v2 ingestion: question import metadata, part guidelines, structured guidelines, required
subtopics, linked stimuli, outcomes and the review audit trail

Revision ID: 0002_ingestion
Revises: 0002_legal_logic
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_ingestion"
down_revision = "0002_legal_logic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("questions") as batch:
        batch.add_column(sa.Column("import_meta", sa.JSON(), nullable=True))
    with op.batch_alter_table("question_parts") as batch:
        batch.add_column(sa.Column("guideline", sa.Text(), nullable=True))
        batch.add_column(sa.Column("meta", sa.JSON(), nullable=True))
    with op.batch_alter_table("marking_guidelines") as batch:
        batch.add_column(sa.Column("label", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("kind", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("criteria", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("sample_answer", sa.Text(), nullable=True))
        batch.add_column(sa.Column("top_mark", sa.Integer(), nullable=True))
    with op.batch_alter_table("source_documents") as batch:
        batch.add_column(sa.Column("meta", sa.JSON(), nullable=True))
    op.create_table(
        "question_plan_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("plan_item_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_item_id"], ["learning_plan_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_plan_items_question_id", "question_plan_items", ["question_id"])
    op.create_table(
        "question_stimuli",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("stimulus_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=40), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stimulus_id"], ["stimuli.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_stimuli_question_id", "question_stimuli", ["question_id"])
    op.create_table(
        "question_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outcome_id"], ["syllabus_outcomes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_outcomes_question_id", "question_outcomes", ["question_id"])
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("actor", sa.String(length=20), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_decisions_question_id", "review_decisions", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_review_decisions_question_id", table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_index("ix_question_outcomes_question_id", table_name="question_outcomes")
    op.drop_table("question_outcomes")
    op.drop_index("ix_question_stimuli_question_id", table_name="question_stimuli")
    op.drop_table("question_stimuli")
    op.drop_index("ix_question_plan_items_question_id", table_name="question_plan_items")
    op.drop_table("question_plan_items")
    with op.batch_alter_table("source_documents") as batch:
        batch.drop_column("meta")
    with op.batch_alter_table("marking_guidelines") as batch:
        for c in ("top_mark", "sample_answer", "criteria", "kind", "label"):
            batch.drop_column(c)
    with op.batch_alter_table("question_parts") as batch:
        batch.drop_column("meta")
        batch.drop_column("guideline")
    with op.batch_alter_table("questions") as batch:
        batch.drop_column("import_meta")
