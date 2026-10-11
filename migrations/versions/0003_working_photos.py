"""Photos of handwritten working attached to answers

Revision ID: 0003_working_photos
Revises: 0002_selection
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_working_photos"
down_revision = "0002_selection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "working_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("session_question_id", sa.Integer(), sa.ForeignKey("session_questions.id"), nullable=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("attempts.id"), nullable=True),
        sa.Column("filename", sa.String(length=80), nullable=False, unique=True),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("reading", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_working_photos_question_id", "working_photos", ["question_id"])
    op.create_index("ix_working_photos_attempt_id", "working_photos", ["attempt_id"])


def downgrade() -> None:
    op.drop_index("ix_working_photos_attempt_id", table_name="working_photos")
    op.drop_index("ix_working_photos_question_id", table_name="working_photos")
    op.drop_table("working_photos")
