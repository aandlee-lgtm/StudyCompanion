"""v2 selection: active-time timer columns on daily_sessions

Revision ID: 0002_selection
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_selection"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("daily_sessions") as batch:
        batch.add_column(sa.Column("last_active_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("pause_note", sa.String(length=200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_sessions") as batch:
        batch.drop_column("pause_note")
        batch.drop_column("last_active_at")
