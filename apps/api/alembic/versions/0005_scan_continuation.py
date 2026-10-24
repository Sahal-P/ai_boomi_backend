"""Bounded scan continuation and retry attempt provenance; no message content."""

import sqlalchemy as sa
from alembic import op

revision = "0005_scan_continuation"
down_revision = "0004_ux_trust"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("next_page_token_encrypted", "resume_page_token_encrypted"):
        op.add_column("import_runs", sa.Column(name, sa.LargeBinary()))
    op.add_column(
        "email_sources",
        sa.Column("last_attempt_run_id", sa.Uuid(), sa.ForeignKey("import_runs.id")),
    )
    op.create_index(
        "ix_email_sources_last_attempt_run_id", "email_sources", ["last_attempt_run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_email_sources_last_attempt_run_id", table_name="email_sources")
    op.drop_column("email_sources", "last_attempt_run_id")
    for name in ("next_page_token_encrypted", "resume_page_token_encrypted"):
        op.drop_column("import_runs", name)
