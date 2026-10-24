"""Preserve original source lineage across merges for exact privacy removal."""

import sqlalchemy as sa
from alembic import op

revision = "0006_event_origins"
down_revision = "0005_scan_continuation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_events",
        sa.Column("origin_transaction_id", sa.Uuid(), sa.ForeignKey("transactions.id")),
    )
    op.create_index(
        "ix_source_events_origin_transaction_id", "source_events", ["origin_transaction_id"]
    )
    op.execute(
        "UPDATE source_events SET origin_transaction_id=transaction_id "
        "WHERE transaction_id IS NOT NULL"
    )

    op.execute("""
      WITH origins AS (
        SELECT DISTINCT ON (d.user_id,e.key) d.user_id,e.key event_id,
               (e.value->>'transaction_id')::uuid origin
        FROM review_decisions d
        CROSS JOIN LATERAL jsonb_each(coalesce(d.before_state->'source_events','{}')) e
        WHERE e.value->>'transaction_id' IS NOT NULL
        ORDER BY d.user_id,e.key,d.created_at,d.id
      ) UPDATE source_events e SET origin_transaction_id=o.origin
        FROM origins o WHERE e.user_id=o.user_id AND e.id=o.event_id::uuid
    """)


def downgrade() -> None:
    op.drop_index("ix_source_events_origin_transaction_id", table_name="source_events")
    op.drop_column("source_events", "origin_transaction_id")
