"""Additive scope inventory, source recovery and optimistic snapshot versions.

No sources, canonical values or revisions are removed. Mixed values are quarantined.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_ux_trust"
down_revision = "0003_whatsapp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("data_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    )
    for table in ("transactions", "commitments"):
        op.add_column(
            table, sa.Column("dataset", sa.Text(), nullable=False, server_default="household")
        )
        op.create_index(f"ix_{table}_dataset", table, ["dataset"])
    op.add_column(
        "commitments",
        sa.Column("user_resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("email_sources", sa.Column("issue_reason", sa.Text()))
    op.add_column(
        "email_sources",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    for name in ("cancel_requested", "truncated"):
        op.add_column(
            "import_runs",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    for name in ("window_start", "window_end"):
        op.add_column("import_runs", sa.Column(name, sa.Date()))
    op.add_column("import_runs", sa.Column("outcome_detail", sa.Text()))
    op.add_column(
        "import_runs",
        sa.Column(
            "retry_source_ids",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "transaction_id",
            sa.Uuid(),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("before_state", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("after_state", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("result_version", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("undone_at", sa.DateTime(timezone=True)),
    )
    for name in ("user_id", "transaction_id"):
        op.create_index(f"ix_review_decisions_{name}", "review_decisions", [name])
    op.execute("""
      WITH provenance AS (
        SELECT se.transaction_id, bool_or(es.source = 'demo_mailbox') demo,
               bool_or(es.source <> 'demo_mailbox') household
        FROM source_events se JOIN email_sources es ON es.id=se.email_source_id
        GROUP BY se.transaction_id
      ) UPDATE transactions t SET dataset = CASE WHEN p.household THEN 'quarantined' ELSE 'demo' END
        FROM provenance p WHERE t.id=p.transaction_id AND p.demo;
      WITH RECURSIVE tainted AS (
        SELECT id, merged_into_id, dataset FROM transactions WHERE dataset <> 'household'
        UNION SELECT t.id,t.merged_into_id,a.dataset FROM transactions t
          JOIN tainted a ON t.merged_into_id=a.id
      ) UPDATE transactions SET dataset='quarantined'
          WHERE id IN (SELECT id FROM tainted) AND dataset='household';
      UPDATE commitments c SET dataset=CASE WHEN EXISTS (
        SELECT 1 FROM source_events e JOIN email_sources s ON s.id=e.email_source_id
        WHERE s.source <> 'demo_mailbox' AND e.user_id=c.user_id AND e.amount_minor=c.amount_minor
          AND e.due_date=c.due_date
          AND coalesce(e.merchant_normalized,'Unidentified obligation')=c.label
          AND e.event_type IN ('bill_due','emi_due')) THEN 'quarantined' ELSE 'demo' END
        WHERE EXISTS (SELECT 1 FROM source_events e JOIN email_sources s ON s.id=e.email_source_id
          WHERE s.source='demo_mailbox' AND e.user_id=c.user_id
          AND e.amount_minor=c.amount_minor
          AND e.due_date=c.due_date
          AND coalesce(e.merchant_normalized,'Unidentified obligation')=c.label
          AND e.event_type IN ('bill_due','emi_due'));
      UPDATE email_sources SET issue_reason='extraction_failed'
        WHERE processing_status='failed';
    """)
    # A monotonic token covers ingestion, review, imports, privacy and legacy writes.
    op.execute("""CREATE FUNCTION finboy_bump_version() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE uid uuid;
      BEGIN
        IF TG_TABLE_NAME='transaction_revisions' THEN
          SELECT user_id INTO uid FROM transactions
            WHERE id=coalesce(NEW.transaction_id,OLD.transaction_id);
        ELSE uid:=coalesce(NEW.user_id,OLD.user_id); END IF;
        UPDATE users SET data_version=data_version+1 WHERE id=uid;
        RETURN NULL;
      END $$""")
    for table in (
        "transactions",
        "commitments",
        "source_events",
        "email_sources",
        "transaction_revisions",
        "import_runs",
        "mail_connections",
    ):
        op.execute(
            f"CREATE TRIGGER ux_version AFTER INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION finboy_bump_version()"
        )


def downgrade() -> None:
    # Schema-only rollback preserves canonical values/revisions; scope is required by new code.
    for table in (
        "transactions",
        "commitments",
        "source_events",
        "email_sources",
        "transaction_revisions",
        "import_runs",
        "mail_connections",
    ):
        op.execute(f"DROP TRIGGER ux_version ON {table}")
    op.execute("DROP FUNCTION finboy_bump_version()")
    op.drop_table("review_decisions")
    for name in (
        "outcome_detail",
        "retry_source_ids",
        "window_start",
        "window_end",
        "cancel_requested",
        "truncated",
    ):
        op.drop_column("import_runs", name)
    op.drop_column("email_sources", "issue_reason")
    op.drop_column("email_sources", "attempts")
    op.drop_column("commitments", "user_resolved")
    for table in ("transactions", "commitments"):
        op.drop_index(f"ix_{table}_dataset", table_name=table)
        op.drop_column(table, "dataset")
    op.drop_column("users", "data_version")
