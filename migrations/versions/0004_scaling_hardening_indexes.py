"""Add hot-path indexes for scaling hardening."""

from __future__ import annotations

from alembic import op


revision = "0004_scaling_hardening_indexes"
down_revision = "0003_point_purchases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_bans_user_active",
        "bans",
        ["user_id", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bans_user_active", table_name="bans")
