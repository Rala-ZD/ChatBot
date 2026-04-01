"""Add nullable match_region to users."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_match_region"
down_revision = "0006_rating_score_default_5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("match_region", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "match_region")
