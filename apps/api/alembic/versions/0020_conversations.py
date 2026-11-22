"""Conversation round: the message log a household agreed to, and who agreed when.

docs/conversation-round/contract.md. Additive: two nullable `users` columns, one table of
messages (text, transcripts, offered choices and R2 keys of voice notes and photos) and two
admin audit actions. The owner, who runs FinBoy, is kept from now. The downgrade refuses while
messages remain, because their files in R2 would lose the only record of where they are; clear
them first.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020_conversations"
down_revision = "0019_names"
branch_labels = None
depends_on = None

OWNER = "00000000-0000-0000-0000-000000000001"
ACTIONS = (
    "'login','login_failed','logout','password_changed','sessions_revoked','admin_created',"
    "'admin_disabled','admin_password_reset','admin_enabled','household_signed_out',"
    "'household_suspended',"
    "'household_restored','household_erased','premium_granted','autopay_cancelled',"
    "'pay_link_created','payment_reconciled','signups_tidied'"
)
KINDS = (
    "'text','voice','photo','document','tap','command','buttons','list','voice_reply','template'"
)
MEDIA_TYPES = (
    "'audio/aac','audio/amr','audio/mpeg','audio/mp4','audio/ogg','image/jpeg','image/png'"
)


def replace(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    for column in ("messages_kept_from", "messages_declined_at"):
        op.add_column("users", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.execute(f"UPDATE users SET messages_kept_from = now() WHERE id = '{OWNER}'")
    replace("admin_events", "action", f"action IN ({ACTIONS},'messages_viewed','media_opened')")
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_id", sa.Uuid(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("choices", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("media_key", sa.Text(), nullable=True),
        sa.Column("media_type", sa.Text(), nullable=True),
        sa.Column("media_bytes", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "direction IN ('in','out')", name=op.f("ck_conversation_messages_direction")
        ),
        sa.CheckConstraint(f"kind IN ({KINDS})", name=op.f("ck_conversation_messages_kind")),
        sa.CheckConstraint(
            "language IN ('en','hi','ml')", name=op.f("ck_conversation_messages_language")
        ),
        sa.CheckConstraint(
            f"media_type IN ({MEDIA_TYPES})", name=op.f("ck_conversation_messages_media_type")
        ),
        sa.CheckConstraint(
            "length(text) <= 4096 AND length(transcript) <= 4096",
            name=op.f("ck_conversation_messages_length"),
        ),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["whatsapp_deliveries.id"],
            name=op.f("fk_conversation_messages_delivery_id_whatsapp_deliveries"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["whatsapp_receipts.id"],
            name=op.f("fk_conversation_messages_receipt_id_whatsapp_receipts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_conversation_messages_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_messages")),
    )
    op.create_index(
        op.f("ix_conversation_messages_receipt_id"),
        "conversation_messages",
        ["receipt_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_messages_user_created",
        "conversation_messages",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    remaining = op.get_bind().execute(sa.text("SELECT count(*) FROM conversation_messages"))
    if remaining.scalar_one():
        raise RuntimeError(
            "conversation_messages still holds messages; clear them (and their R2 files) first"
        )
    op.drop_index("ix_conversation_messages_user_created", table_name="conversation_messages")
    op.drop_index(op.f("ix_conversation_messages_receipt_id"), table_name="conversation_messages")
    op.drop_table("conversation_messages")
    # The older checks cannot hold these; the messages they were about are already gone.
    op.execute("DELETE FROM admin_events WHERE action IN ('messages_viewed','media_opened')")
    replace("admin_events", "action", f"action IN ({ACTIONS})")
    for column in ("messages_declined_at", "messages_kept_from"):
        op.drop_column("users", column)
