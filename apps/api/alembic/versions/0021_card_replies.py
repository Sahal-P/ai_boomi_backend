"""Card replies round: a swipe-reply finds its card, and receipts say what happened.

docs/whatsapp.md, "Dates and card replies". Additive: one nullable, indexed column on
`whatsapp_prompts` (the WhatsApp message that carried the card, so a reply that quotes it acts on
that card) and four receipt outcomes: date_unclear, reply_unclear, prompt_answered and
prompt_replaced. The downgrade maps those back to the nearest older outcome and drops the column.
"""

import sqlalchemy as sa
from alembic import op

revision = "0021_card_replies"
down_revision = "0020_conversations"
branch_labels = None
depends_on = None

RECEIPT_ERRORS = (
    "'provider_unavailable','invalid_audio','assistant_unavailable','processing_failed',"
    "'window_expired','interrupted','disabled','stale_message','invalid_image',"
    "'capture_unavailable','capture_busy','prompt_expired','record_changed','amount_unclear',"
    "'statement_unavailable','signup_full','login_expired','usage_limit','web_not_available',"
    "'invalid_document','document_unavailable','premium_required'"
)
NEW_ERRORS = "'date_unclear','reply_unclear','prompt_answered','prompt_replaced'"


def replace(table: str, name: str, column: str, values: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, f"{column} IN ({values})")


def upgrade() -> None:
    op.add_column("whatsapp_prompts", sa.Column("outbound_message_id", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_whatsapp_prompts_outbound_message_id"),
        "whatsapp_prompts",
        ["outbound_message_id"],
        unique=False,
    )
    replace("whatsapp_receipts", "error_code", "error_code", f"{RECEIPT_ERRORS},{NEW_ERRORS}")


def downgrade() -> None:
    op.execute(
        "UPDATE whatsapp_receipts SET error_code = 'amount_unclear' "
        "WHERE error_code IN ('date_unclear','reply_unclear')"
    )
    op.execute(
        "UPDATE whatsapp_receipts SET error_code = 'prompt_expired' "
        "WHERE error_code IN ('prompt_answered','prompt_replaced')"
    )
    replace("whatsapp_receipts", "error_code", "error_code", RECEIPT_ERRORS)
    op.drop_index(op.f("ix_whatsapp_prompts_outbound_message_id"), table_name="whatsapp_prompts")
    op.drop_column("whatsapp_prompts", "outbound_message_id")
