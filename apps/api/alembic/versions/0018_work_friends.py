"""Add Work and Friends & outings to the closed category list.

Widens the checks on records, budgets and learned payees. No row changes. Downgrade refuses
while either category is still in use.
"""

from alembic import op

revision = "0018_work_friends"
down_revision = "0017_coach"
branch_labels = None
depends_on = None

TRANSACTIONS = (
    "'salary','other_income','rent','food_dining','groceries','transport','shopping',"
    "'utilities','subscriptions','travel','health','education','investments','loan_emi','fees',"
    "'transfer','farming','livestock','phone_recharge','family_events','work','friends',"
    "'remittance','wages','farm_sales','govt_benefit','other'"
)
OLD_TRANSACTIONS = (
    "'salary','other_income','rent','food_dining','groceries','transport','shopping',"
    "'utilities','subscriptions','travel','health','education','investments','loan_emi','fees',"
    "'transfer','farming','livestock','phone_recharge','family_events','remittance','wages',"
    "'farm_sales','govt_benefit','other'"
)
BUDGETS = (
    "'total','rent','food_dining','groceries','transport','shopping','utilities','subscriptions',"
    "'travel','health','education','investments','loan_emi','fees','farming','livestock',"
    "'phone_recharge','family_events','work','friends','remittance','other'"
)
OLD_BUDGETS = (
    "'total','rent','food_dining','groceries','transport','shopping','utilities','subscriptions',"
    "'travel','health','education','investments','loan_emi','fees','farming','livestock',"
    "'phone_recharge','family_events','remittance','other'"
)
PAYEES = (
    "'salary','other_income','rent','food_dining','groceries','transport','shopping','utilities',"
    "'subscriptions','travel','health','education','investments','loan_emi','fees','transfer',"
    "'farming','livestock','phone_recharge','family_events','work','friends','remittance','wages',"
    "'farm_sales','govt_benefit','other'"
)
OLD_PAYEES = (
    "'salary','other_income','rent','food_dining','groceries','transport','shopping','utilities',"
    "'subscriptions','travel','health','education','investments','loan_emi','fees','transfer',"
    "'farming','livestock','phone_recharge','family_events','remittance','wages','farm_sales',"
    "'govt_benefit','other'"
)


def replace(table: str, name: str, values: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, f"category IN ({values})")


def upgrade() -> None:
    replace("transactions", "category", TRANSACTIONS)
    replace("budgets", "category", BUDGETS)
    replace("merchant_categories", "category", PAYEES)


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM transactions WHERE category IN ('work','friends')) "
        "OR EXISTS (SELECT 1 FROM budgets WHERE category IN ('work','friends')) "
        "OR EXISTS (SELECT 1 FROM merchant_categories WHERE category IN ('work','friends')) THEN "
        "RAISE EXCEPTION 'Move Work and Friends & outings records first'; "
        "END IF; END $$"
    )
    replace("transactions", "category", OLD_TRANSACTIONS)
    replace("budgets", "category", OLD_BUDGETS)
    replace("merchant_categories", "category", OLD_PAYEES)
