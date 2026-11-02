"""Subscription round: FinBoy Premium through PayU.

docs/subscription-round/contract.md. Additive only: one row per household for how long it has
paid and how it renews, one row per payment attempt, the payer's encrypted contact, and a
`premium_required` receipt outcome for WhatsApp. No card, UPI, bank or PayU message column is
introduced. Downgrade drops what this adds, and refuses while payment rows remain.
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_billing"
down_revision = "0012_statement_imports"
branch_labels = None
depends_on = None

RECEIPT_ERRORS = (
    "'provider_unavailable','invalid_audio','assistant_unavailable','processing_failed',"
    "'window_expired','interrupted','disabled','stale_message','invalid_image',"
    "'capture_unavailable','capture_busy','prompt_expired','record_changed','amount_unclear',"
    "'statement_unavailable','signup_full','login_expired','usage_limit','web_not_available',"
    "'invalid_document','document_unavailable'"
)


def replace(table: str, name: str, column: str, values: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, f"{column} IN ({values})")


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    replace("whatsapp_receipts", "error_code", "error_code", f"{RECEIPT_ERRORS},'premium_required'")
    op.create_table(
        "billing_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_email", sa.LargeBinary(), nullable=True),
        sa.Column("encrypted_phone", sa.LargeBinary(), nullable=True),
        sa.Column("last_nudge", sa.Text(), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "last_nudge IN ('trial_3d','trial_last','trial_over','renewal_failed')",
            name=op.f("ck_billing_profiles_last_nudge"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_billing_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_billing_profiles")),
    )
    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("paid_through", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renewal", sa.Text(), server_default="manual", nullable=False),
        sa.Column("mandate_payuid", sa.Text(), nullable=True),
        sa.Column("mandate_kind", sa.Text(), nullable=True),
        sa.Column("mandate_seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_charge_on", sa.Date(), nullable=True),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "renewal IN ('manual','autopay','off')", name=op.f("ck_subscriptions_renewal")
        ),
        sa.CheckConstraint(
            "mandate_kind IN ('upi','card')", name=op.f("ck_subscriptions_mandate_kind")
        ),
        sa.CheckConstraint(
            "renewal <> 'autopay' OR (mandate_payuid IS NOT NULL AND mandate_kind IS NOT NULL)",
            name=op.f("ck_subscriptions_mandate"),
        ),
        sa.CheckConstraint("mandate_seq >= 0", name=op.f("ck_subscriptions_mandate_seq")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_subscriptions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_subscriptions")),
        sa.UniqueConstraint("mandate_payuid", name=op.f("uq_subscriptions_mandate_payuid")),
    )
    op.create_table(
        "billing_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("txnid", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("started_via", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("autopay_offered", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "mandate_registered", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("payu_id", sa.Text(), nullable=True),
        sa.Column("mode", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("covers_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("covers_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("debit_on", sa.Date(), nullable=True),
        sa.Column("predebit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        *timestamps(),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('checkout','renewal')", name=op.f("ck_billing_payments_kind")),
        sa.CheckConstraint(
            "started_via IN ('web','link','worker')", name=op.f("ck_billing_payments_started_via")
        ),
        sa.CheckConstraint(
            "status IN ('started','scheduled','pending','paid','failed','abandoned')",
            name=op.f("ck_billing_payments_status"),
        ),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_billing_payments_amount")),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_billing_payments_attempts")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_billing_payments_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_payments")),
        sa.UniqueConstraint("txnid", name=op.f("uq_billing_payments_txnid")),
    )
    op.create_index(
        "ix_billing_payments_user_id_created_at", "billing_payments", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_billing_payments_open",
        "billing_payments",
        ["status", "updated_at"],
        postgresql_where=sa.text("status IN ('started','scheduled','pending')"),
    )


def downgrade() -> None:
    # Payment rows are FinBoy's sales records; never drop them silently.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM billing_payments) THEN "
        "RAISE EXCEPTION 'Remove billing payments before downgrading'; END IF; END $$"
    )
    op.drop_index("ix_billing_payments_open", table_name="billing_payments")
    op.drop_index("ix_billing_payments_user_id_created_at", table_name="billing_payments")
    op.drop_table("billing_payments")
    op.drop_table("subscriptions")
    op.drop_table("billing_profiles")
    op.execute(
        "UPDATE whatsapp_receipts SET error_code = 'processing_failed' "
        "WHERE error_code = 'premium_required'"
    )
    replace("whatsapp_receipts", "error_code", "error_code", RECEIPT_ERRORS)
