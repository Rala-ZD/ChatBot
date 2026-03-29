"""Add referral, points, and VIP fields."""

from __future__ import annotations

import secrets
import string

from alembic import op
import sqlalchemy as sa


revision = "0002_referrals_vip"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _generate_referral_code(existing_codes: set[str], length: int = 10) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        if code not in existing_codes:
            existing_codes.add(code)
            return code


def upgrade() -> None:
    op.add_column("users", sa.Column("referral_code", sa.String(length=32), nullable=True))
    op.add_column(
        "users",
        sa.Column("referred_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("points_balance", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("vip_until", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_users_referred_by_user_id", "users", ["referred_by_user_id"], unique=False)
    op.create_foreign_key(
        "fk_users_referred_by_user_id_users",
        "users",
        "users",
        ["referred_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    bind = op.get_bind()
    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer()),
        sa.column("referral_code", sa.String(length=32)),
    )

    rows = bind.execute(sa.select(users_table.c.id, users_table.c.referral_code)).all()
    existing_codes = {row.referral_code for row in rows if row.referral_code}
    for row in rows:
        if row.referral_code:
            continue
        bind.execute(
            sa.update(users_table)
            .where(users_table.c.id == row.id)
            .values(referral_code=_generate_referral_code(existing_codes))
        )

    op.alter_column("users", "referral_code", nullable=False)
    op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_referral_code", table_name="users")
    op.drop_constraint("fk_users_referred_by_user_id_users", "users", type_="foreignkey")
    op.drop_index("ix_users_referred_by_user_id", table_name="users")
    op.drop_column("users", "vip_until")
    op.drop_column("users", "points_balance")
    op.drop_column("users", "referred_by_user_id")
    op.drop_column("users", "referral_code")
