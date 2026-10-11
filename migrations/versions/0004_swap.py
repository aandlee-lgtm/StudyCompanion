"""Real-time swaps in daily sessions (who, when, why, from, to)

Revision ID: 0004_swap
Revises: 0003_working_photos
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_swap"
down_revision = "0003_working_photos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_swaps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("daily_sessions.id"), nullable=False),
        sa.Column("actor", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("subject_code", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("from_question_ids", sa.JSON(), nullable=False),
        sa.Column("to_question_ids", sa.JSON(), nullable=False),
        sa.Column("plan_item_id", sa.Integer(), sa.ForeignKey("learning_plan_items.id"), nullable=True),
        sa.Column("locked_plan_item_id", sa.Integer(), sa.ForeignKey("learning_plan_items.id"), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_session_swaps_session_id", "session_swaps", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_session_swaps_session_id", table_name="session_swaps")
    op.drop_table("session_swaps")
