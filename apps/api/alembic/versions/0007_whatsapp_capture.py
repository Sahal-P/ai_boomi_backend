"""Allow WhatsApp screenshot sources and receipts; widens check constraints only."""

from alembic import op

revision = "0007_whatsapp_capture"
down_revision = "0006_event_origins"
branch_labels = None
depends_on = None

RECEIPT_ERRORS = (
    "'provider_unavailable','invalid_audio','assistant_unavailable','processing_failed',"
    "'window_expired','interrupted','disabled','stale_message'"
)
CAPTURE_ERRORS = ",'invalid_image','capture_unavailable','capture_busy'"


def replace(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    sources = "'gmail','eml_upload','demo_mailbox','whatsapp_image'"
    replace("email_sources", "source", f"source IN ({sources})")
    replace("import_runs", "mode", f"mode IN ({sources})")
    replace("whatsapp_receipts", "kind", "kind IN ('text','audio','image','command')")
    replace("whatsapp_receipts", "error_code", f"error_code IN ({RECEIPT_ERRORS}{CAPTURE_ERRORS})")


def downgrade() -> None:
    # Fails closed while screenshot rows exist; they are never rewritten or deleted here.
    sources = "'gmail','eml_upload','demo_mailbox'"
    replace("email_sources", "source", f"source IN ({sources})")
    replace("import_runs", "mode", f"mode IN ({sources})")
    replace("whatsapp_receipts", "kind", "kind IN ('text','audio','command')")
    replace("whatsapp_receipts", "error_code", f"error_code IN ({RECEIPT_ERRORS})")
