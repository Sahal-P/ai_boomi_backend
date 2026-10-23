"""Minimal WhatsApp consent/transport metadata, no content retention."""

import sqlalchemy as sa
from alembic import op

revision = "0003_whatsapp"
down_revision = "0002_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_bindings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sender_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("language", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("language IN ('en','hi','ml')", name="language"),
    )
    op.create_index("ix_whatsapp_bindings_user_id", "whatsapp_bindings", ["user_id"])
    op.create_table(
        "whatsapp_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "binding_id",
            sa.Uuid(),
            sa.ForeignKey("whatsapp_bindings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("inbound_message_id", sa.Text(), nullable=False, unique=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("language", sa.Text()),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("provider_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('text','audio','command')", name="kind"),
        sa.CheckConstraint("language IN ('en','hi','ml')", name="language"),
        sa.CheckConstraint(
            "state IN ('admitted','processing','completed','failed','interrupted','ignored')",
            name="state",
        ),
        sa.CheckConstraint(
            "error_code IN ('provider_unavailable','invalid_audio','assistant_unavailable',"
            "'processing_failed','window_expired','interrupted','disabled','stale_message')",
            name="error_code",
        ),
    )
    op.create_index(
        "ix_whatsapp_receipts_state_received_at", "whatsapp_receipts", ["state", "received_at"]
    )
    op.create_table(
        "whatsapp_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "receipt_id",
            sa.Uuid(),
            sa.ForeignKey("whatsapp_receipts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("outbound_message_id", sa.Text(), unique=True),
        sa.Column("provider_status", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("receipt_id", "kind"),
        sa.CheckConstraint("kind IN ('text','audio')", name="kind"),
        sa.CheckConstraint(
            "state IN ('pending','sending','sent','failed','unknown')", name="state"
        ),
        sa.CheckConstraint(
            "provider_status IN ('sent','delivered','read','failed')", name="status"
        ),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_deliveries")
    op.drop_index("ix_whatsapp_receipts_state_received_at", table_name="whatsapp_receipts")
    op.drop_table("whatsapp_receipts")
    op.drop_index("ix_whatsapp_bindings_user_id", table_name="whatsapp_bindings")
    op.drop_table("whatsapp_bindings")
