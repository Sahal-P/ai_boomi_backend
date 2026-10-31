"""Statement round: Google Pay statements imported as dated, referenced records.

docs/statement-round/contract.md. Additive only: `gpay_statement` as a source and import mode, one
table for each imported statement's period, own totals and counts, and WhatsApp receipts for a
statement sent as a document. No file, phone number or email column is introduced. Downgrade drops
what this adds, and refuses while statement rows remain.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_statement_imports"
down_revision = "0011_money_manager"
branch_labels = None
depends_on = None

MODES = "'gmail','eml_upload','demo_mailbox','whatsapp_image','whatsapp_voice','manual_entry'"
RECEIPT_KINDS = "'text','audio','image','command','button'"
RECEIPT_ERRORS = (
    "'provider_unavailable','invalid_audio','assistant_unavailable','processing_failed',"
    "'window_expired','interrupted','disabled','stale_message','invalid_image',"
    "'capture_unavailable','capture_busy','prompt_expired','record_changed','amount_unclear',"
    "'statement_unavailable','signup_full','login_expired','usage_limit','web_not_available'"
)


def replace(table: str, name: str, column: str, values: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, f"{column} IN ({values})")


def upgrade() -> None:
    replace("email_sources", "source", "source", f"{MODES},'gpay_statement'")
    replace("import_runs", "mode", "mode", f"{MODES},'gpay_statement'")
    replace("whatsapp_receipts", "kind", "kind", f"{RECEIPT_KINDS},'document'")
    replace(
        "whatsapp_receipts",
        "error_code",
        "error_code",
        f"{RECEIPT_ERRORS},'invalid_document','document_unavailable'",
    )
    op.create_table(
        "statement_imports",
        sa.Column("import_run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("rows_new", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rows_linked", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "rows_possible_duplicate", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "rows_already_imported", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("rows_not_counted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sent_minor", sa.BigInteger(), nullable=False),
        sa.Column("received_minor", sa.BigInteger(), nullable=False),
        sa.Column("paid_minor", sa.BigInteger(), nullable=False),
        sa.Column("got_minor", sa.BigInteger(), nullable=False),
        sa.Column("reconciled", sa.Boolean(), nullable=False),
        sa.Column(
            "accounts",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("file_sha256", sa.Text(), nullable=False),
        sa.Column("holder_matches", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("provider = 'gpay'", name=op.f("ck_statement_imports_provider")),
        sa.CheckConstraint("period_start <= period_end", name=op.f("ck_statement_imports_period")),
        sa.CheckConstraint(
            "pages > 0 AND rows_total >= 0 AND rows_new >= 0 AND rows_linked >= 0 "
            "AND rows_possible_duplicate >= 0 AND rows_already_imported >= 0 "
            "AND rows_not_counted >= 0 AND sent_minor >= 0 AND received_minor >= 0 "
            "AND paid_minor >= 0 AND got_minor >= 0",
            name=op.f("ck_statement_imports_counters"),
        ),
        sa.ForeignKeyConstraint(
            ["import_run_id"],
            ["import_runs.id"],
            name=op.f("fk_statement_imports_import_run_id_import_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_statement_imports_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("import_run_id", name=op.f("pk_statement_imports")),
    )
    op.create_index(
        "ix_statement_imports_user_id_file_sha256",
        "statement_imports",
        ["user_id", "file_sha256"],
    )


def downgrade() -> None:
    # Statement evidence backs ledger records; removing it here would leave them unexplained.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM email_sources WHERE source = 'gpay_statement') "
        "OR EXISTS (SELECT 1 FROM import_runs WHERE mode = 'gpay_statement') THEN "
        "RAISE EXCEPTION 'Remove statement imports before downgrading'; END IF; END $$"
    )
    op.drop_index("ix_statement_imports_user_id_file_sha256", table_name="statement_imports")
    op.drop_table("statement_imports")
    # Receipts keep no content; a document's receipt has no older kind to become.
    op.execute("DELETE FROM whatsapp_receipts WHERE kind = 'document'")
    op.execute(
        "UPDATE whatsapp_receipts SET error_code = 'processing_failed' "
        "WHERE error_code IN ('invalid_document','document_unavailable')"
    )
    replace("whatsapp_receipts", "error_code", "error_code", RECEIPT_ERRORS)
    replace("whatsapp_receipts", "kind", "kind", RECEIPT_KINDS)
    replace("import_runs", "mode", "mode", MODES)
    replace("email_sources", "source", "source", MODES)
