"""Feedback round: problems and ideas households send from the web app.

docs/feedback-round/contract.md. Additive: one `feedback` table (type, message, the screen it came
from, an optional screenshot's R2 key, status) and three admin audit actions for reading a report,
opening its screenshot and setting its status. The downgrade refuses while feedback remains,
because its screenshots in R2 would lose the only record of where they are.
"""

import sqlalchemy as sa
from alembic import op

revision = "0022_feedback"
down_revision = "0021_card_replies"
branch_labels = None
depends_on = None

ACTIONS = (
    "'login','login_failed','logout','password_changed','sessions_revoked','admin_created',"
    "'admin_disabled','admin_password_reset','admin_enabled','household_signed_out',"
    "'household_suspended','household_restored','household_erased','premium_granted',"
    "'autopay_cancelled','pay_link_created','payment_reconciled','signups_tidied',"
    "'messages_viewed','media_opened'"
)
FEEDBACK_ACTIONS = "'feedback_viewed','feedback_screenshot_opened','feedback_status_changed'"


def replace(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("page", sa.Text(), server_default="", nullable=False),
        sa.Column("screenshot_key", sa.Text(), nullable=True),
        sa.Column("screenshot_type", sa.Text(), nullable=True),
        sa.Column("screenshot_bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), server_default="new", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('problem','idea','other')", name=op.f("ck_feedback_kind")),
        sa.CheckConstraint("status IN ('new','planned','done')", name=op.f("ck_feedback_status")),
        sa.CheckConstraint(
            "screenshot_type IN ('image/jpeg','image/png','image/webp')",
            name=op.f("ck_feedback_screenshot_type"),
        ),
        sa.CheckConstraint(
            "length(message) BETWEEN 1 AND 2000 AND length(page) <= 200",
            name=op.f("ck_feedback_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_feedback_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback")),
    )
    op.create_index(op.f("ix_feedback_user_id"), "feedback", ["user_id"], unique=False)
    op.create_index("ix_feedback_status_created", "feedback", ["status", "created_at"])
    replace("admin_events", "action", f"action IN ({ACTIONS},{FEEDBACK_ACTIONS})")


def downgrade() -> None:
    remaining = op.get_bind().execute(sa.text("SELECT count(*) FROM feedback")).scalar()
    if remaining:
        raise RuntimeError("Feedback remains: remove it (and its screenshots) before downgrading")
    op.execute(f"DELETE FROM admin_events WHERE action IN ({FEEDBACK_ACTIONS})")
    replace("admin_events", "action", f"action IN ({ACTIONS})")
    op.drop_index("ix_feedback_status_created", table_name="feedback")
    op.drop_index(op.f("ix_feedback_user_id"), table_name="feedback")
    op.drop_table("feedback")
