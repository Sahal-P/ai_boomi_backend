"""Advisor edits round: changes the advisor proposes, applied on a tap and undone in one step.

docs/advisor-edits-round/contract.md. Additive:
- the `record_change_sets` table;
- `whatsapp_prompts.change_set_id` and two card purposes (`advisor_changes`, `advisor_undo`);
- a remembered payee name: `merchant_categories.display_name`, with `category` now optional.

The downgrade refuses while change sets or remembered names remain, since dropping them would lose
what an Undo needs and the names households chose.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024_record_changes"
down_revision = "0023_signup_visits"
branch_labels = None
depends_on = None

PURPOSES = (
    "'consent','confirm','change_amount','undo','due_paid','due_repeat','reminder_opt_in',"
    "'web_login','link','saved','pick_item','pick_category','checkin_opt_in','coach_opt_in'"
)
NEW_PURPOSES = "'advisor_changes','advisor_undo'"


def replace(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.create_table(
        "record_change_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="proposed", nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("before_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('proposed','applied','undone','declined','expired')",
            name=op.f("ck_record_change_sets_state"),
        ),
        sa.CheckConstraint(
            "channel IN ('web','whatsapp')", name=op.f("ck_record_change_sets_channel")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_record_change_sets_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["advisor_messages.id"],
            name=op.f("fk_record_change_sets_message_id_advisor_messages"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record_change_sets")),
    )
    op.create_index(
        op.f("ix_record_change_sets_user_id"), "record_change_sets", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_record_change_sets_message_id"),
        "record_change_sets",
        ["message_id"],
        unique=False,
    )
    op.add_column("whatsapp_prompts", sa.Column("change_set_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_whatsapp_prompts_change_set_id_record_change_sets"),
        "whatsapp_prompts",
        "record_change_sets",
        ["change_set_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_whatsapp_prompts_change_set_id"),
        "whatsapp_prompts",
        ["change_set_id"],
        unique=False,
    )
    replace("whatsapp_prompts", "purpose", f"purpose IN ({PURPOSES},{NEW_PURPOSES})")
    op.add_column("merchant_categories", sa.Column("display_name", sa.Text(), nullable=True))
    op.alter_column("merchant_categories", "category", existing_type=sa.Text(), nullable=True)
    op.create_check_constraint(
        op.f("ck_merchant_categories_remembers_something"),
        "merchant_categories",
        "category IS NOT NULL OR display_name IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_merchant_categories_display_name"),
        "merchant_categories",
        "length(display_name) BETWEEN 1 AND 60",
    )


def downgrade() -> None:
    bind = op.get_bind()
    sets = bind.execute(sa.text("SELECT count(*) FROM record_change_sets")).scalar()
    names = bind.execute(
        sa.text("SELECT count(*) FROM merchant_categories WHERE display_name IS NOT NULL")
    ).scalar()
    if sets or names:
        raise RuntimeError(
            "Advisor change sets or remembered payee names remain; remove them first"
        )
    op.drop_constraint(
        op.f("ck_merchant_categories_display_name"), "merchant_categories", type_="check"
    )
    op.drop_constraint(
        op.f("ck_merchant_categories_remembers_something"), "merchant_categories", type_="check"
    )
    op.alter_column("merchant_categories", "category", existing_type=sa.Text(), nullable=False)
    op.drop_column("merchant_categories", "display_name")
    op.execute("DELETE FROM whatsapp_prompts WHERE purpose IN ('advisor_changes','advisor_undo')")
    replace("whatsapp_prompts", "purpose", f"purpose IN ({PURPOSES})")
    op.drop_index(op.f("ix_whatsapp_prompts_change_set_id"), table_name="whatsapp_prompts")
    op.drop_constraint(
        op.f("fk_whatsapp_prompts_change_set_id_record_change_sets"),
        "whatsapp_prompts",
        type_="foreignkey",
    )
    op.drop_column("whatsapp_prompts", "change_set_id")
    op.drop_index(op.f("ix_record_change_sets_message_id"), table_name="record_change_sets")
    op.drop_index(op.f("ix_record_change_sets_user_id"), table_name="record_change_sets")
    op.drop_table("record_change_sets")
