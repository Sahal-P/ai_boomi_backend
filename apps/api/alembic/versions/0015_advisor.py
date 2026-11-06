"""Advisor round: chats with FinBoy, the household's long-term memory and its on/off switch.

docs/advisor-round/contract.md. Additive only. Downgrade refuses while any chat or memory remains,
so a household's saved memories never disappear silently.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_advisor"
down_revision = "0014_admin"
branch_labels = None
depends_on = None

KINDS = "'about','goal','plan','preference','person','note'"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("memory_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_table(
        "advisor_threads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("summarized_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "channel IN ('web','whatsapp')", name=op.f("ck_advisor_threads_channel")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_advisor_threads_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_advisor_threads")),
    )
    op.create_index(
        "ix_advisor_threads_user_last", "advisor_threads", ["user_id", "last_at"], unique=False
    )
    op.create_table(
        "advisor_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column(
            "tool_names",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('user','assistant')", name=op.f("ck_advisor_messages_role")),
        sa.CheckConstraint(
            "length(text) BETWEEN 1 AND 4000", name=op.f("ck_advisor_messages_text")
        ),
        sa.CheckConstraint(
            "language IN ('en','hi','ml')", name=op.f("ck_advisor_messages_language")
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["advisor_threads.id"],
            name=op.f("fk_advisor_messages_thread_id_advisor_threads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_advisor_messages_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_advisor_messages")),
    )
    op.create_index(
        "ix_advisor_messages_thread_created",
        "advisor_messages",
        ["thread_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisor_messages_user_id"), "advisor_messages", ["user_id"], unique=False
    )
    op.create_table(
        "household_memories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_key", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(f"kind IN ({KINDS})", name=op.f("ck_household_memories_kind")),
        sa.CheckConstraint(
            "source IN ('web','whatsapp','user')", name=op.f("ck_household_memories_source")
        ),
        sa.CheckConstraint(
            "length(text) BETWEEN 1 AND 300", name=op.f("ck_household_memories_text")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_household_memories_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_household_memories")),
        sa.UniqueConstraint("user_id", "text_key", name="uq_household_memories_user_text"),
    )
    op.create_index(
        op.f("ix_household_memories_user_id"), "household_memories", ["user_id"], unique=False
    )


def downgrade() -> None:
    # A household's memories and chats are its own; never drop them silently.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM household_memories) "
        "OR EXISTS (SELECT 1 FROM advisor_messages) THEN "
        "RAISE EXCEPTION 'Delete advisor chats and memories first'; "
        "END IF; END $$"
    )
    op.drop_index(op.f("ix_household_memories_user_id"), table_name="household_memories")
    op.drop_table("household_memories")
    op.drop_index(op.f("ix_advisor_messages_user_id"), table_name="advisor_messages")
    op.drop_index("ix_advisor_messages_thread_created", table_name="advisor_messages")
    op.drop_table("advisor_messages")
    op.drop_index("ix_advisor_threads_user_last", table_name="advisor_threads")
    op.drop_table("advisor_threads")
    op.drop_column("users", "memory_enabled")
