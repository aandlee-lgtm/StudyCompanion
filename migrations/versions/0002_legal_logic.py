"""v2 legal-logic: evidence structure (aliases, status, sub-area, issue tags, version, related
items) and the verification history table.

Revision ID: 0002_legal_logic
Revises: 0002_english_logic
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_legal_logic"
down_revision = "0002_english_logic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("legal_evidence") as b:
        b.add_column(sa.Column("aliases", sa.JSON(), nullable=True))
        b.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="unknown"))
        b.add_column(sa.Column("superseded_by", sa.String(length=400), nullable=True))
        b.add_column(sa.Column("sub_area", sa.String(length=40), nullable=True))
        b.add_column(sa.Column("issue_tags", sa.JSON(), nullable=True))
        b.add_column(sa.Column("version_as_at", sa.String(length=40), nullable=True))
        b.add_column(sa.Column("related", sa.JSON(), nullable=True))
    op.create_table(
        "legal_evidence_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column("version_as_at", sa.String(length=40), nullable=True),
        sa.Column("checklist", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("summary_corrected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("checked_by", sa.String(length=40), nullable=False, server_default="student"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["evidence_id"], ["legal_evidence.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("legal_evidence_checks") as b:
        b.create_index("ix_legal_evidence_checks_evidence_id", ["evidence_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("legal_evidence_checks") as b:
        b.drop_index("ix_legal_evidence_checks_evidence_id")
    op.drop_table("legal_evidence_checks")
    with op.batch_alter_table("legal_evidence") as b:
        for col in ("related", "version_as_at", "issue_tags", "sub_area", "superseded_by", "status", "aliases"):
            b.drop_column(col)
