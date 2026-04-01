"""Move aggregate rating_score to a non-null 5.0 baseline."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_rating_score_default_5"
down_revision = "0005_ratings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "rating_score",
        existing_type=sa.Numeric(2, 1),
        server_default=sa.text("5.0"),
        existing_nullable=True,
    )

    op.execute(
        sa.text(
            """
            UPDATE users
            SET rating_score = 5.0
            """
        )
    )

    op.execute(
        sa.text(
            """
            WITH rating_deltas AS (
                SELECT
                    to_user_id AS user_id,
                    SUM(
                        CASE
                            WHEN value = 'good' THEN 0.2
                            WHEN value = 'bad' THEN -0.2
                            ELSE 0.0
                        END
                    ) AS delta
                FROM session_ratings
                GROUP BY to_user_id
            )
            UPDATE users AS u
            SET rating_score = CAST(
                LEAST(5.0, GREATEST(-5.0, 5.0 + rating_deltas.delta)) AS NUMERIC(2, 1)
            )
            FROM rating_deltas
            WHERE u.id = rating_deltas.user_id
            """
        )
    )

    op.alter_column(
        "users",
        "rating_score",
        existing_type=sa.Numeric(2, 1),
        nullable=False,
        server_default=sa.text("5.0"),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "rating_score",
        existing_type=sa.Numeric(2, 1),
        nullable=True,
        server_default=None,
        existing_nullable=False,
    )
