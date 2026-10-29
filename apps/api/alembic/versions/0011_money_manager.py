"""Money-manager round: budgets, a savings goal, merchant memory and monthly check-ins.

docs/money-manager-round/contract.md. Additive only: two new household tables, one per-month
check-in claim table, two nullable columns and wider prompt purposes. No message text, audio,
image, transcript or phone number column is introduced. Downgrade drops what this adds.
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_money_manager"
down_revision = "0010_whatsapp_last_language"
branch_labels = None
depends_on = None

PURPOSES = (
    "'consent','confirm','change_amount','undo','due_paid','due_repeat','reminder_opt_in',"
    "'web_login','link'"
)
NEW_PURPOSES = ",'saved','pick_item','pick_category','checkin_opt_in'"
BUDGET_CATEGORIES = (
    "'total','rent','food_dining','groceries','transport','shopping','utilities',"
    "'subscriptions','travel','health','education','investments','loan_emi','fees','farming',"
    "'livestock','phone_recharge','family_events','remittance','other'"
)
CATEGORIES = (
    "'salary','other_income','rent','food_dining','groceries','transport','shopping','utilities',"
    "'subscriptions','travel','health','education','investments','loan_emi','fees','transfer',"
    "'farming','livestock','phone_recharge','family_events','remittance','wages','farm_sales',"
    "'govt_benefit','other'"
)


def replace(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.add_column("users", sa.Column("monthly_savings_goal_minor", sa.BigInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_users_savings_goal"),
        "users",
        "monthly_savings_goal_minor > 0 AND monthly_savings_goal_minor <= 1000000000",
    )
    op.add_column(
        "whatsapp_bindings",
        sa.Column("checkin_opt_in_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("whatsapp_prompts", sa.Column("group_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_whatsapp_prompts_group_id_whatsapp_prompts"),
        "whatsapp_prompts",
        "whatsapp_prompts",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_whatsapp_prompts_group_id"), "whatsapp_prompts", ["group_id"])
    replace("whatsapp_prompts", "purpose", f"purpose IN ({PURPOSES}{NEW_PURPOSES})")

    op.create_table(
        "budgets",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("limit_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(f"category IN ({BUDGET_CATEGORIES})", name=op.f("ck_budgets_category")),
        sa.CheckConstraint(
            "limit_minor > 0 AND limit_minor <= 1000000000", name=op.f("ck_budgets_limit_minor")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_budgets_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "category", name=op.f("pk_budgets")),
    )
    op.create_table(
        "merchant_categories",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("merchant_key", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            f"category IN ({CATEGORIES})", name=op.f("ck_merchant_categories_category")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_merchant_categories_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "merchant_key", name=op.f("pk_merchant_categories")),
    )
    op.create_table(
        "whatsapp_checkins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("outbound_message_id", sa.Text(), nullable=True),
        sa.Column("provider_status", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "state IN ('sending','sent','failed','unknown')",
            name=op.f("ck_whatsapp_checkins_state"),
        ),
        sa.CheckConstraint(
            "provider_status IN ('sent','delivered','read','failed')",
            name=op.f("ck_whatsapp_checkins_status"),
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            ["whatsapp_bindings.id"],
            name=op.f("fk_whatsapp_checkins_binding_id_whatsapp_bindings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_checkins")),
        sa.UniqueConstraint("binding_id", "month", name=op.f("uq_whatsapp_checkins_binding_id")),
        sa.UniqueConstraint(
            "outbound_message_id", name=op.f("uq_whatsapp_checkins_outbound_message_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_checkins")
    op.drop_table("merchant_categories")
    op.drop_table("budgets")
    # Pending buttons of the new kinds only; the older purpose check cannot hold them.
    op.execute(
        "DELETE FROM whatsapp_prompts "
        "WHERE purpose IN ('saved','pick_item','pick_category','checkin_opt_in')"
    )
    replace("whatsapp_prompts", "purpose", f"purpose IN ({PURPOSES})")
    op.drop_index(op.f("ix_whatsapp_prompts_group_id"), table_name="whatsapp_prompts")
    op.drop_constraint(
        op.f("fk_whatsapp_prompts_group_id_whatsapp_prompts"),
        "whatsapp_prompts",
        type_="foreignkey",
    )
    op.drop_column("whatsapp_prompts", "group_id")
    op.drop_column("whatsapp_bindings", "checkin_opt_in_at")
    op.drop_constraint(op.f("ck_users_savings_goal"), "users", type_="check")
    op.drop_column("users", "monthly_savings_goal_minor")
