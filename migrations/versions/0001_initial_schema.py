"""Initial schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("nickname", sa.String(length=32), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column(
            "gender",
            sa.Enum("male", "female", "other", name="gender_enum", native_enum=False),
            nullable=True,
        ),
        sa.Column(
            "preferred_gender",
            sa.Enum("any", "male", "female", "other", name="preferred_gender_enum", native_enum=False),
            nullable=False,
            server_default="any",
        ),
        sa.Column("interests_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("is_registered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=False)
    op.create_index("ix_users_is_registered", "users", ["is_registered"], unique=False)
    op.create_index("ix_users_is_banned", "users", ["is_banned"], unique=False)

    op.create_table(
        "waiting_queue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("waiting", "matched", "cancelled", "expired", name="queue_status_enum", native_enum=False),
            nullable=False,
            server_default="waiting",
        ),
        sa.Column("match_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_waiting_queue_user_id", "waiting_queue", ["user_id"], unique=False)
    op.create_index("ix_waiting_queue_status", "waiting_queue", ["status"], unique=False)
    op.create_index("ix_waiting_queue_status_joined", "waiting_queue", ["status", "joined_at"], unique=False)
    op.create_index(
        "uq_waiting_queue_user_active",
        "waiting_queue",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'waiting'"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user1_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user2_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "ended", name="session_status_enum", native_enum=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "end_reason",
            sa.Enum(
                "end",
                "next",
                "report",
                "partner_unreachable",
                "moderation",
                "internal_failure",
                name="end_reason_enum",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("ended_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_sessions_status", "sessions", ["status"], unique=False)
    op.create_index("ix_sessions_status_started", "sessions", ["status", "started_at"], unique=False)
    op.create_index("ix_sessions_user1_status", "sessions", ["user1_id", "status"], unique=False)
    op.create_index("ix_sessions_user2_status", "sessions", ["user2_id", "status"], unique=False)
    op.create_index(
        "ix_sessions_active_user1",
        "sessions",
        ["user1_id"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_sessions_active_user2",
        "sessions",
        ["user2_id"],
        unique=False,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "session_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "message_type",
            sa.Enum(
                "text",
                "photo",
                "video",
                "voice",
                "document",
                "sticker",
                "unsupported",
                name="message_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("relay_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("relay_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "delivery_status",
            sa.Enum("delivered", "failed", name="delivery_status_enum", native_enum=False),
            nullable=False,
            server_default="delivered",
        ),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("file_id", sa.String(length=512), nullable=True),
        sa.Column("file_unique_id", sa.String(length=255), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_session_messages_session_id", "session_messages", ["session_id"], unique=False)
    op.create_index("ix_session_messages_sender_user_id", "session_messages", ["sender_user_id"], unique=False)
    op.create_index(
        "ix_session_messages_session_created",
        "session_messages",
        ["session_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reported_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reports_session_id", "reports", ["session_id"], unique=False)
    op.create_index("ix_reports_reporter_user_id", "reports", ["reporter_user_id"], unique=False)
    op.create_index("ix_reports_reported_user_id", "reports", ["reported_user_id"], unique=False)

    op.create_table(
        "bans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("banned_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bans_user_id", "bans", ["user_id"], unique=False)
    op.create_index("ix_bans_is_active", "bans", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_bans_is_active", table_name="bans")
    op.drop_index("ix_bans_user_id", table_name="bans")
    op.drop_table("bans")

    op.drop_index("ix_reports_reported_user_id", table_name="reports")
    op.drop_index("ix_reports_reporter_user_id", table_name="reports")
    op.drop_index("ix_reports_session_id", table_name="reports")
    op.drop_table("reports")

    op.drop_index("ix_session_messages_session_created", table_name="session_messages")
    op.drop_index("ix_session_messages_sender_user_id", table_name="session_messages")
    op.drop_index("ix_session_messages_session_id", table_name="session_messages")
    op.drop_table("session_messages")

    op.drop_index("ix_sessions_active_user2", table_name="sessions")
    op.drop_index("ix_sessions_active_user1", table_name="sessions")
    op.drop_index("ix_sessions_user2_status", table_name="sessions")
    op.drop_index("ix_sessions_user1_status", table_name="sessions")
    op.drop_index("ix_sessions_status_started", table_name="sessions")
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("uq_waiting_queue_user_active", table_name="waiting_queue")
    op.drop_index("ix_waiting_queue_status_joined", table_name="waiting_queue")
    op.drop_index("ix_waiting_queue_status", table_name="waiting_queue")
    op.drop_index("ix_waiting_queue_user_id", table_name="waiting_queue")
    op.drop_table("waiting_queue")

    op.drop_index("ix_users_is_banned", table_name="users")
    op.drop_index("ix_users_is_registered", table_name="users")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
