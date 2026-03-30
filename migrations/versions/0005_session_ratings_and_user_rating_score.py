"""Add session ratings and aggregate user rating score."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_session_ratings_and_user_rating_score"
down_revision = "0004_scaling_hardening_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("rating_score", sa.Numeric(2, 1), nullable=True),
    )
    op.create_check_constraint(
        "ck_users_rating_score_range",
        "users",
        "rating_score IS NULL OR (rating_score >= -5.0 AND rating_score <= 5.0)",
    )

    op.create_table(
        "session_ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "value",
            sa.Enum("good", "bad", name="session_rating_value_enum", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_ratings")),
        sa.UniqueConstraint("session_id", "from_user_id", name="uq_session_ratings_session_from_user"),
    )
    op.create_index("ix_session_ratings_session_id", "session_ratings", ["session_id"], unique=False)
    op.create_index("ix_session_ratings_to_user_id", "session_ratings", ["to_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_session_ratings_to_user_id", table_name="session_ratings")
    op.drop_index("ix_session_ratings_session_id", table_name="session_ratings")
    op.drop_table("session_ratings")
    op.drop_constraint("ck_users_rating_score_range", "users", type_="check")
    op.drop_column("users", "rating_score")
