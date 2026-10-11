"""v2 english-logic: stimulus headnote, text complexity and seed metadata

Revision ID: 0002_english_logic
Revises: 0002_adaptive
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_english_logic"
down_revision = "0002_adaptive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stimuli") as batch:
        batch.add_column(sa.Column("headnote", sa.Text(), nullable=True))
        batch.add_column(sa.Column("complexity", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("stimuli") as batch:
        batch.drop_column("meta")
        batch.drop_column("complexity")
        batch.drop_column("headnote")
