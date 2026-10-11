"""Follow-up questions about feedback ("Ask about this feedback", "Questions for my teacher")

Revision ID: 0005_followup
Revises: 0004_swap (or 0003_working_photos on a branch that does not contain the swap package)
"""
from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision = "0005_followup"
# The plan chains this after the swap package's 0004_swap. On a branch without that migration
# (this package was built in parallel with swap), chain after 0003_working_photos instead, so the
# migration history is valid both before and after the two branches are merged.
down_revision = "0004_swap" if any(Path(__file__).parent.glob("0004_swap*.py")) else "0003_working_photos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("attempts.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("turn", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("chip", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("page_url", sa.String(length=300), nullable=True),
        sa.Column("for_teacher", sa.Boolean(), nullable=False),
        sa.Column("teacher_resolved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_feedback_questions_attempt_id", "feedback_questions", ["attempt_id"])
    op.create_index("ix_feedback_questions_for_teacher", "feedback_questions", ["for_teacher"])


def downgrade() -> None:
    op.drop_index("ix_feedback_questions_for_teacher", table_name="feedback_questions")
    op.drop_index("ix_feedback_questions_attempt_id", table_name="feedback_questions")
    op.drop_table("feedback_questions")
