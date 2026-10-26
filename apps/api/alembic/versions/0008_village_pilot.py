"""Village pilot: pilot households, consent, button prompts, reminders, rural categories.

Additive only. No message text, transcript, audio or image column is introduced.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_village_pilot"
down_revision = "0007_whatsapp_capture"
branch_labels = None
depends_on = None

SOURCES = "'gmail','eml_upload','demo_mailbox','whatsapp_image'"
CATEGORIES = (
    "'salary','other_income','rent','food_dining','groceries','transport','shopping',"
    "'utilities','subscriptions','travel','health','education','investments','loan_emi',"
    "'fees','transfer'"
)
PILOT_CATEGORIES = (
    ",'farming','livestock','phone_recharge','family_events','remittance','wages',"
    "'farm_sales','govt_benefit'"
)
RECEIPT_ERRORS = (
    "'provider_unavailable','invalid_audio','assistant_unavailable','processing_failed',"
    "'window_expired','interrupted','disabled','stale_message','invalid_image',"
    "'capture_unavailable','capture_busy'"
)
PILOT_ERRORS = ",'prompt_expired','record_changed','amount_unclear','statement_unavailable'"


def replace(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("pilot", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.add_column(
        "whatsapp_bindings", sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "whatsapp_bindings",
        sa.Column("reminders_opt_in_at", sa.DateTime(timezone=True), nullable=True),
    )
    replace("email_sources", "source", f"source IN ({SOURCES},'whatsapp_voice')")
    replace("import_runs", "mode", f"mode IN ({SOURCES},'whatsapp_voice')")
    replace("transactions", "category", f"category IN ({CATEGORIES}{PILOT_CATEGORIES},'other')")
    replace("commitments", "kind", "kind IN ('bill','emi','subscription','sip','loan')")
    replace("commitments", "status", "status IN ('upcoming','paid','dismissed','pending')")
    replace("whatsapp_receipts", "kind", "kind IN ('text','audio','image','command','button')")
    replace("whatsapp_receipts", "error_code", f"error_code IN ({RECEIPT_ERRORS}{PILOT_ERRORS})")
    replace("whatsapp_deliveries", "kind", "kind IN ('text','audio','interactive','reminder')")

    op.create_table(
        "whatsapp_prompts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=True),
        sa.Column("commitment_id", sa.Uuid(), nullable=True),
        sa.Column("decision_id", sa.Uuid(), nullable=True),
        sa.Column("fingerprint", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), server_default="open", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('consent','confirm','change_amount','undo','due_paid','due_repeat',"
            "'reminder_opt_in')",
            name=op.f("ck_whatsapp_prompts_purpose"),
        ),
        sa.CheckConstraint(
            "state IN ('open','answered','expired','superseded')",
            name=op.f("ck_whatsapp_prompts_state"),
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            ["whatsapp_bindings.id"],
            name=op.f("fk_whatsapp_prompts_binding_id_whatsapp_bindings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_whatsapp_prompts_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_whatsapp_prompts_transaction_id_transactions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["commitment_id"],
            ["commitments.id"],
            name=op.f("fk_whatsapp_prompts_commitment_id_commitments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["review_decisions.id"],
            name=op.f("fk_whatsapp_prompts_decision_id_review_decisions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_prompts")),
    )
    op.create_index(
        "ix_whatsapp_prompts_binding_id_state", "whatsapp_prompts", ["binding_id", "state"]
    )
    for column in ("user_id", "transaction_id", "commitment_id", "decision_id"):
        op.create_index(
            op.f(f"ix_whatsapp_prompts_{column}"), "whatsapp_prompts", [column], unique=False
        )

    op.create_table(
        "whatsapp_reminders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("commitment_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("outbound_message_id", sa.Text(), nullable=True),
        sa.Column("provider_status", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('two_days','due_day')", name=op.f("ck_whatsapp_reminders_kind")
        ),
        sa.CheckConstraint(
            "state IN ('sending','sent','failed','unknown')",
            name=op.f("ck_whatsapp_reminders_state"),
        ),
        sa.CheckConstraint(
            "provider_status IN ('sent','delivered','read','failed')",
            name=op.f("ck_whatsapp_reminders_status"),
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            ["whatsapp_bindings.id"],
            name=op.f("fk_whatsapp_reminders_binding_id_whatsapp_bindings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["commitment_id"],
            ["commitments.id"],
            name=op.f("fk_whatsapp_reminders_commitment_id_commitments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_reminders")),
        sa.UniqueConstraint(
            "commitment_id", "kind", name=op.f("uq_whatsapp_reminders_commitment_id")
        ),
        sa.UniqueConstraint(
            "outbound_message_id", name=op.f("uq_whatsapp_reminders_outbound_message_id")
        ),
    )


def downgrade() -> None:
    # Fails closed while pilot rows use the widened values; nothing is rewritten or deleted.
    op.drop_table("whatsapp_reminders")
    op.drop_table("whatsapp_prompts")
    replace("whatsapp_deliveries", "kind", "kind IN ('text','audio')")
    replace("whatsapp_receipts", "error_code", f"error_code IN ({RECEIPT_ERRORS})")
    replace("whatsapp_receipts", "kind", "kind IN ('text','audio','image','command')")
    replace("commitments", "status", "status IN ('upcoming','paid','dismissed')")
    replace("commitments", "kind", "kind IN ('bill','emi','subscription','sip')")
    replace("transactions", "category", f"category IN ({CATEGORIES},'other')")
    replace("import_runs", "mode", f"mode IN ({SOURCES})")
    replace("email_sources", "source", f"source IN ({SOURCES})")
    op.drop_column("whatsapp_bindings", "reminders_opt_in_at")
    op.drop_column("whatsapp_bindings", "consented_at")
    op.drop_column("users", "pilot")
