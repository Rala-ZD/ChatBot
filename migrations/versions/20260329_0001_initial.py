"""Initial schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260329_0001"
down_revision = None
branch_labels = None
depends_on = None


gender_enum = sa.Enum(
    "male",
    "female",
    "non_binary",
    "other",
    "prefer_not_to_say",
    name="gender_enum",
    native_enum=False,
)
preferred_gender_enum = sa.Enum(
    "any",
    "male",
    "female",
    "non_binary",
    "other",
    "prefer_not_to_say",
    name="preferred_gender_enum",
    native_enum=False,
)
queue_status_enum = sa.Enum(
    "waiting",
    "matched",
    "cancelled",
    name="queue_status_enum",
    native_enum=False,
)
session_status_enum = sa.Enum(
    "active",
    "ended",
    name="session_status_enum",
    native_enum=False,
)
session_end_reason_enum = sa.Enum(
    "user_end",
    "next",
    "report",
    "partner_unavailable",
    "internal_failure",
    "moderation",
    "blocked_bot",
    name="session_end_reason_enum",
    native_enum=False,
)
message_type_enum = sa.Enum(
    "text",
    "photo",
    "video",
    "voice",
    "document",
    "sticker",
    name="message_type_enum",
    native_enum=False,
)
report_reason_enum = sa.Enum(
    "spam",
    "harassment",
    "nudity",
    "scam",
    "underage",
    "other",
    name="report_reason_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("nickname", sa.String(length=32), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", gender_enum, nullable=True),
        sa.Column("preferred_gender", preferred_gender_enum, nullable=True),
        sa.Column(
            "interests_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("is_registered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_in_chat", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consent_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_version", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=False)

    op.create_table(
        "waiting_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("status", queue_status_enum, nullable=False, server_default="waiting"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_waiting_queue_status_joined_at",
        "waiting_queue",
        ["status", "joined_at"],
        unique=False,
    )
    op.create_index(
        "uq_waiting_queue_user_waiting",
        "waiting_queue",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'waiting'"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user1_id", sa.Integer(), nullable=False),
        sa.Column("user2_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", session_status_enum, nullable=False, server_default="active"),
        sa.Column("end_reason", session_end_reason_enum, nullable=True),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user1_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user2_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sessions_status_started_at", "sessions", ["status", "started_at"], unique=False)
    op.create_index("ix_sessions_user1_id_status", "sessions", ["user1_id", "status"], unique=False)
    op.create_index("ix_sessions_user2_id_status", "sessions", ["user2_id", "status"], unique=False)

    op.create_table(
        "session_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), nullable=False),
        sa.Column("message_type", message_type_enum, nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("file_id", sa.String(length=512), nullable=True),
        sa.Column("file_unique_id", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_session_messages_session_created",
        "session_messages",
        ["session_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), nullable=False),
        sa.Column("reported_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", report_reason_enum, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["reported_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_reports_session_created", "reports", ["session_id", "created_at"], unique=False)

    op.create_table(
        "bans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("banned_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_bans_user_id_is_active", "bans", ["user_id", "is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_bans_user_id_is_active", table_name="bans")
    op.drop_table("bans")
    op.drop_index("ix_reports_session_created", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_session_messages_session_created", table_name="session_messages")
    op.drop_table("session_messages")
    op.drop_index("ix_sessions_user2_id_status", table_name="sessions")
    op.drop_index("ix_sessions_user1_id_status", table_name="sessions")
    op.drop_index("ix_sessions_status_started_at", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("uq_waiting_queue_user_waiting", table_name="waiting_queue")
    op.drop_index("ix_waiting_queue_status_joined_at", table_name="waiting_queue")
    op.drop_table("waiting_queue")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
