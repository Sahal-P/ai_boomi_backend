"""Advisor phase 3: the proactive coach's opt-in and its exactly-once nudge claims.

docs/advisor-round/contract.md. Additive only: one nullable binding column, one wider prompt
purpose and one claim table holding kinds, keyed digests, dates and delivery states. No message
text, figure, payee name or phone number column is introduced. The downgrade drops what this
adds; the nudges' words stay in the household's chats.
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_coach"
down_revision = "0016_knowledge"
branch_labels = None
depends_on = None

PURPOSES = (
    "'consent','confirm','change_amount','undo','due_paid','due_repeat','reminder_opt_in',"
    "'web_login','link','saved','pick_item','pick_category','checkin_opt_in'"
)
KINDS = (
    "'weekly_recap','due_soon','budget_over','unusual_payment','income_in','budget_near',"
    "'goal_progress','new_regular'"
)


def replace(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.add_column(
        "whatsapp_bindings",
        sa.Column("coach_opt_in_at", sa.DateTime(timezone=True), nullable=True),
    )
    replace("whatsapp_prompts", "purpose", f"purpose IN ({PURPOSES},'coach_opt_in')")
    op.create_table(
        "advisor_nudges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("period_key", sa.Text(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("via", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("outbound_message_id", sa.Text(), nullable=True),
        sa.Column("provider_status", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(f"kind IN ({KINDS})", name=op.f("ck_advisor_nudges_kind")),
        sa.CheckConstraint("via IN ('message','template')", name=op.f("ck_advisor_nudges_via")),
        sa.CheckConstraint(
            "state IN ('sending','sent','failed','unknown')", name=op.f("ck_advisor_nudges_state")
        ),
        sa.CheckConstraint(
            "provider_status IN ('sent','delivered','read','failed')",
            name=op.f("ck_advisor_nudges_status"),
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            ["whatsapp_bindings.id"],
            name=op.f("fk_advisor_nudges_binding_id_whatsapp_bindings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_advisor_nudges_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_advisor_nudges")),
        sa.UniqueConstraint("binding_id", "kind", "period_key", name="uq_advisor_nudges_period"),
        sa.UniqueConstraint("binding_id", "day", name="uq_advisor_nudges_day"),
        sa.UniqueConstraint(
            "outbound_message_id", name=op.f("uq_advisor_nudges_outbound_message_id")
        ),
    )
    op.create_index(op.f("ix_advisor_nudges_user_id"), "advisor_nudges", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_advisor_nudges_user_id"), table_name="advisor_nudges")
    op.drop_table("advisor_nudges")
    # Pending coach buttons only; the older purpose check cannot hold them.
    op.execute("DELETE FROM whatsapp_prompts WHERE purpose = 'coach_opt_in'")
    replace("whatsapp_prompts", "purpose", f"purpose IN ({PURPOSES})")
    op.drop_column("whatsapp_bindings", "coach_opt_in_at")
