"""WhatsApp replies follow each person's language (29 October 2026, docs/whatsapp.md).

`whatsapp_bindings.language` now holds only a language the person chose with a command; NULL means
FinBoy follows each message. The new `last_language` keeps the language FinBoy last replied in, for
a message that shows none (a button tap, a login code, a photo).

Existing `language` values came from code defaults (Hindi for diary households) or from a "hi"
greeting read as the Hindi command, not from choices, so they are cleared: every number starts
again in English and follows its next message. No message content is involved. Downgrade drops the
new column; cleared values are not restored.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_whatsapp_last_language"
down_revision = "0009_signup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("whatsapp_bindings", sa.Column("last_language", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_whatsapp_bindings_last_language"),
        "whatsapp_bindings",
        "last_language IN ('en','hi','ml')",
    )
    op.execute("UPDATE whatsapp_bindings SET language = NULL WHERE language IS NOT NULL")


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_whatsapp_bindings_last_language"), "whatsapp_bindings", type_="check"
    )
    op.drop_column("whatsapp_bindings", "last_language")
