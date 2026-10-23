"""Phase 1 schema and local user

Revision ID: 0002_phase1
Revises: 0001_phase0
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase1"
down_revision: str | Sequence[str] | None = "0001_phase0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed: dependency-ordered tables; self FKs remain nullable.
    op.create_table(
        "extraction_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extraction_cache")),
        sa.UniqueConstraint("cache_key", name=op.f("uq_extraction_cache_cache_key")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_audit_events_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_user_id"), "audit_events", ["user_id"], unique=False)
    op.create_table(
        "mail_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("account_email_masked", sa.Text(), nullable=False),
        sa.Column("account_email_sha256", sa.Text(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.LargeBinary(), nullable=True),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("provider = 'gmail'", name=op.f("ck_mail_connections_provider")),
        sa.CheckConstraint(
            "status IN ('active','paused','revoked','error')",
            name=op.f("ck_mail_connections_status"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_mail_connections_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_connections")),
    )
    op.create_index(
        "ix_mail_connections_user_id_status",
        "mail_connections",
        ["user_id", "status"],
        unique=False,
    )
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("state_sha256", sa.Text(), nullable=False),
        sa.Column("encrypted_code_verifier", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_oauth_states_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_states")),
        sa.UniqueConstraint("state_sha256", name=op.f("uq_oauth_states_state_sha256")),
    )
    op.create_index(op.f("ix_oauth_states_user_id"), "oauth_states", ["user_id"], unique=False)
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default="INR", nullable=False),
        sa.Column("merchant", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_id", sa.Text(), nullable=True),
        sa.Column("payment_instrument", sa.Text(), nullable=True),
        sa.Column("account_last4", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("confidence_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("possible_duplicate_of_id", sa.Uuid(), nullable=True),
        sa.Column("linked_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("merged_into_id", sa.Uuid(), nullable=True),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column(
            "user_locked_fields",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('salary','other_income','rent','food_dining','groceries',"
            "'transport','shopping','utilities','subscriptions','travel','health',"
            "'education','investments','loan_emi','fees','transfer','other')",
            name=op.f("ck_transactions_category"),
        ),
        sa.CheckConstraint("currency = 'INR'", name=op.f("ck_transactions_currency")),
        sa.CheckConstraint("direction IN ('in','out')", name=op.f("ck_transactions_direction")),
        sa.CheckConstraint(
            "kind IN ('purchase','salary','income_other','refund','reversal','fee',"
            "'bill_payment','emi','investment','transfer')",
            name=op.f("ck_transactions_kind"),
        ),
        sa.CheckConstraint(
            "review_reason IN ('low_confidence','merchant_uncertain',"
            "'possible_duplicate','category_uncertain','unverified_payment')",
            name=op.f("ck_transactions_review_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('confirmed','needs_review','rejected','merged','failed')",
            name=op.f("ck_transactions_status"),
        ),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_transactions_positive_amount")),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_transactions_confidence")),
        sa.ForeignKeyConstraint(
            ["linked_transaction_id"],
            ["transactions.id"],
            name=op.f("fk_transactions_linked_transaction_id_transactions"),
        ),
        sa.ForeignKeyConstraint(
            ["merged_into_id"],
            ["transactions.id"],
            name=op.f("fk_transactions_merged_into_id_transactions"),
        ),
        sa.ForeignKeyConstraint(
            ["possible_duplicate_of_id"],
            ["transactions.id"],
            name=op.f("fk_transactions_possible_duplicate_of_id_transactions"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_transactions_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    op.create_index(
        op.f("ix_transactions_fingerprint"), "transactions", ["fingerprint"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_linked_transaction_id"),
        "transactions",
        ["linked_transaction_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactions_merged_into_id"), "transactions", ["merged_into_id"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_possible_duplicate_of_id"),
        "transactions",
        ["possible_duplicate_of_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactions_reference_id"), "transactions", ["reference_id"], unique=False
    )
    op.create_index(
        "ix_transactions_user_id_occurred_at",
        "transactions",
        ["user_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_transactions_user_id_status", "transactions", ["user_id", "status"], unique=False
    )
    op.create_table(
        "import_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("mail_connection_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("headers_checked", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("candidates_found", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("emails_processed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("events_extracted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "transactions_created", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("duplicates_merged", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("needs_review", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "non_financial_skipped", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("failed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "error_code IN ('configuration_missing','authorization_failed','provider_unavailable',"
            "'invalid_upload','extraction_failed','import_failed')",
            name=op.f("ck_import_runs_error_code"),
        ),
        sa.CheckConstraint(
            "mode IN ('gmail','eml_upload','demo_mailbox')", name=op.f("ck_import_runs_mode")
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed')",
            name=op.f("ck_import_runs_status"),
        ),
        sa.CheckConstraint(
            "headers_checked >= 0 AND candidates_found >= 0 "
            "AND emails_processed >= 0 AND events_extracted >= 0 "
            "AND transactions_created >= 0 AND duplicates_merged >= 0 "
            "AND needs_review >= 0 AND non_financial_skipped >= 0 AND failed >= 0",
            name=op.f("ck_import_runs_counters"),
        ),
        sa.ForeignKeyConstraint(
            ["mail_connection_id"],
            ["mail_connections.id"],
            name=op.f("fk_import_runs_mail_connection_id_mail_connections"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_import_runs_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_runs")),
    )
    op.create_index(
        op.f("ix_import_runs_mail_connection_id"),
        "import_runs",
        ["mail_connection_id"],
        unique=False,
    )
    op.create_index(
        "ix_import_runs_user_id_status", "import_runs", ["user_id", "status"], unique=False
    )
    op.create_table(
        "transaction_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("changed_by", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "changed_by IN ('user','system')", name=op.f("ck_transaction_revisions_changed_by")
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_transaction_revisions_transaction_id_transactions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction_revisions")),
    )
    op.create_index(
        op.f("ix_transaction_revisions_transaction_id"),
        "transaction_revisions",
        ["transaction_id"],
        unique=False,
    )
    op.create_table(
        "email_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("import_run_id", sa.Uuid(), nullable=False),
        sa.Column("mail_connection_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column("sender_domain", sa.Text(), nullable=False),
        sa.Column("subject_sha256", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("classification", sa.Text(), nullable=False),
        sa.Column("processing_status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "classification IN ('bank_alert','card_alert','upi_alert',"
            "'merchant_receipt','order_confirmation','bill_notice','emi_notice',"
            "'salary_credit','refund_notice','promotional','non_financial','unknown')",
            name=op.f("ck_email_sources_classification"),
        ),
        sa.CheckConstraint(
            "processing_status IN ('pending','extracted','skipped','failed')",
            name=op.f("ck_email_sources_processing_status"),
        ),
        sa.CheckConstraint(
            "source IN ('gmail','eml_upload','demo_mailbox')", name=op.f("ck_email_sources_source")
        ),
        sa.ForeignKeyConstraint(
            ["import_run_id"],
            ["import_runs.id"],
            name=op.f("fk_email_sources_import_run_id_import_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["mail_connection_id"],
            ["mail_connections.id"],
            name=op.f("fk_email_sources_mail_connection_id_mail_connections"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_email_sources_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_sources")),
        sa.UniqueConstraint(
            "user_id", "source", "provider_message_id", name=op.f("uq_email_sources_user_id")
        ),
    )
    op.create_index(
        op.f("ix_email_sources_import_run_id"), "email_sources", ["import_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_email_sources_mail_connection_id"),
        "email_sources",
        ["mail_connection_id"],
        unique=False,
    )
    op.create_index(op.f("ix_email_sources_user_id"), "email_sources", ["user_id"], unique=False)
    op.create_table(
        "source_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email_source_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default="INR", nullable=False),
        sa.Column("merchant_raw", sa.Text(), nullable=True),
        sa.Column("merchant_normalized", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("reference_id", sa.Text(), nullable=True),
        sa.Column("payment_instrument", sa.Text(), nullable=True),
        sa.Column("account_last4", sa.Text(), nullable=True),
        sa.Column("extraction_method", sa.Text(), nullable=False),
        sa.Column("extractor_id", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("field_confidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("currency = 'INR'", name=op.f("ck_source_events_currency")),
        sa.CheckConstraint(
            "event_type IN ('debit','credit','refund','reversal','fee','salary',"
            "'bill_due','emi_due','investment','transfer','failed')",
            name=op.f("ck_source_events_event_type"),
        ),
        sa.CheckConstraint(
            "extraction_method IN ('rule','llm')", name=op.f("ck_source_events_extraction_method")
        ),
        sa.ForeignKeyConstraint(
            ["email_source_id"],
            ["email_sources.id"],
            name=op.f("fk_source_events_email_source_id_email_sources"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_source_events_transaction_id_transactions"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_source_events_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_events")),
    )
    op.create_index(
        op.f("ix_source_events_email_source_id"), "source_events", ["email_source_id"], unique=False
    )
    op.create_index(
        op.f("ix_source_events_reference_id"), "source_events", ["reference_id"], unique=False
    )
    op.create_index(
        op.f("ix_source_events_transaction_id"), "source_events", ["transaction_id"], unique=False
    )
    op.create_index(op.f("ix_source_events_user_id"), "source_events", ["user_id"], unique=False)
    op.create_table(
        "commitments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default="INR", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source_event_id", sa.Uuid(), nullable=True),
        sa.Column("paid_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("currency = 'INR'", name=op.f("ck_commitments_currency")),
        sa.CheckConstraint(
            "kind IN ('bill','emi','subscription','sip')", name=op.f("ck_commitments_kind")
        ),
        sa.CheckConstraint(
            "status IN ('upcoming','paid','dismissed')", name=op.f("ck_commitments_status")
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_commitments_confidence")),
        sa.ForeignKeyConstraint(
            ["paid_transaction_id"],
            ["transactions.id"],
            name=op.f("fk_commitments_paid_transaction_id_transactions"),
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["source_events.id"],
            name=op.f("fk_commitments_source_event_id_source_events"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_commitments_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commitments")),
    )
    op.create_index(
        op.f("ix_commitments_paid_transaction_id"),
        "commitments",
        ["paid_transaction_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commitments_source_event_id"), "commitments", ["source_event_id"], unique=False
    )
    op.create_index(
        "ix_commitments_user_id_due_date", "commitments", ["user_id", "due_date"], unique=False
    )
    op.create_index(
        "ix_commitments_user_id_status", "commitments", ["user_id", "status"], unique=False
    )

    op.bulk_insert(
        sa.table("users", sa.column("id", sa.Uuid()), sa.column("display_name", sa.Text())),
        [{"id": UUID("00000000-0000-0000-0000-000000000001"), "display_name": "Arun"}],
    )


def downgrade() -> None:
    # Reviewed: dependency-ordered tables; self FKs remain nullable.
    op.drop_index("ix_commitments_user_id_status", table_name="commitments")
    op.drop_index("ix_commitments_user_id_due_date", table_name="commitments")
    op.drop_index(op.f("ix_commitments_source_event_id"), table_name="commitments")
    op.drop_index(op.f("ix_commitments_paid_transaction_id"), table_name="commitments")
    op.drop_table("commitments")
    op.drop_index(op.f("ix_source_events_user_id"), table_name="source_events")
    op.drop_index(op.f("ix_source_events_transaction_id"), table_name="source_events")
    op.drop_index(op.f("ix_source_events_reference_id"), table_name="source_events")
    op.drop_index(op.f("ix_source_events_email_source_id"), table_name="source_events")
    op.drop_table("source_events")
    op.drop_index(op.f("ix_email_sources_user_id"), table_name="email_sources")
    op.drop_index(op.f("ix_email_sources_mail_connection_id"), table_name="email_sources")
    op.drop_index(op.f("ix_email_sources_import_run_id"), table_name="email_sources")
    op.drop_table("email_sources")
    op.drop_index(
        op.f("ix_transaction_revisions_transaction_id"), table_name="transaction_revisions"
    )
    op.drop_table("transaction_revisions")
    op.drop_index("ix_import_runs_user_id_status", table_name="import_runs")
    op.drop_index(op.f("ix_import_runs_mail_connection_id"), table_name="import_runs")
    op.drop_table("import_runs")
    op.drop_index("ix_transactions_user_id_status", table_name="transactions")
    op.drop_index("ix_transactions_user_id_occurred_at", table_name="transactions")
    op.drop_index(op.f("ix_transactions_reference_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_possible_duplicate_of_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_merged_into_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_linked_transaction_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_fingerprint"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_oauth_states_user_id"), table_name="oauth_states")
    op.drop_table("oauth_states")
    op.drop_index("ix_mail_connections_user_id_status", table_name="mail_connections")
    op.drop_table("mail_connections")
    op.drop_index(op.f("ix_audit_events_user_id"), table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("users")
    op.drop_table("extraction_cache")
