"""Ad journey round: where each sign-up came from.

docs/ad-journey-round/contract.md. Additive: one `signup_visits` table holding a page visit's
random ref, its link's campaign tags, coarse browser and phone classes, and the times the page
opened, the WhatsApp button was tapped and the new household's first message arrived. Visits hold
no IP address, cookie, device ID, raw User-Agent or click ID, so the downgrade simply drops them.
"""

import sqlalchemy as sa
from alembic import op

revision = "0023_signup_visits"
down_revision = "0022_feedback"
branch_labels = None
depends_on = None

TAG = "^[a-z0-9._-]{1,64}$"


def upgrade() -> None:
    op.create_table(
        "signup_visits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ref", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("medium", sa.Text(), nullable=True),
        sa.Column("campaign", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("landing", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("browser", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("tapped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("ref ~ '^[2-9A-HJ-NP-Z]{6}$'", name=op.f("ck_signup_visits_ref")),
        sa.CheckConstraint(
            " AND ".join(
                f"({tag} IS NULL OR {tag} ~ '{TAG}')"
                for tag in ("source", "medium", "campaign", "content")
            ),
            name=op.f("ck_signup_visits_tags"),
        ),
        sa.CheckConstraint(
            "landing ~ '^/[a-z0-9/-]{0,63}$'", name=op.f("ck_signup_visits_landing")
        ),
        sa.CheckConstraint("language IN ('en','hi','ml')", name=op.f("ck_signup_visits_language")),
        sa.CheckConstraint(
            "browser IN ('instagram','facebook','other')", name=op.f("ck_signup_visits_browser")
        ),
        sa.CheckConstraint(
            "platform IN ('android','ios','desktop','other')",
            name=op.f("ck_signup_visits_platform"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_signup_visits_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signup_visits")),
        sa.UniqueConstraint("ref", name=op.f("uq_signup_visits_ref")),
    )
    op.create_index(
        op.f("ix_signup_visits_created_at"), "signup_visits", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_signup_visits_user_id"), "signup_visits", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_signup_visits_user_id"), table_name="signup_visits")
    op.drop_index(op.f("ix_signup_visits_created_at"), table_name="signup_visits")
    op.drop_table("signup_visits")
