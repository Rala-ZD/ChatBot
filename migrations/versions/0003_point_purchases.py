"""Add point purchases table for Telegram payments."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_point_purchases"
down_revision = "0002_referrals_vip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "point_purchases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("package_code", sa.String(length=32), nullable=False),
        sa.Column("points_amount", sa.Integer(), nullable=False),
        sa.Column("total_amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("invoice_payload", sa.String(length=128), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(length=255), nullable=True),
        sa.Column("provider_payment_charge_id", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "paid", name="point_purchase_status_enum", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_point_purchases")),
        sa.UniqueConstraint("invoice_payload", name=op.f("uq_point_purchases_invoice_payload")),
        sa.UniqueConstraint(
            "provider_payment_charge_id",
            name=op.f("uq_point_purchases_provider_payment_charge_id"),
        ),
        sa.UniqueConstraint(
            "telegram_payment_charge_id",
            name=op.f("uq_point_purchases_telegram_payment_charge_id"),
        ),
    )
    op.create_index(op.f("ix_point_purchases_user_id"), "point_purchases", ["user_id"], unique=False)
    op.create_index(
        "ix_point_purchases_user_status",
        "point_purchases",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(op.f("ix_point_purchases_status"), "point_purchases", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_point_purchases_status"), table_name="point_purchases")
    op.drop_index("ix_point_purchases_user_status", table_name="point_purchases")
    op.drop_index(op.f("ix_point_purchases_user_id"), table_name="point_purchases")
    op.drop_table("point_purchases")
