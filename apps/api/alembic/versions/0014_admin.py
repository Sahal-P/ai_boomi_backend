"""Admin round: admin accounts, server-side admin sessions, the admin audit log and suspension.

docs/admin-round/contract.md. Additive only. Passwords are scrypt hashes and session tokens are
kept only as SHA-256 digests. Downgrade refuses while admin accounts or suspended households
remain, so neither the audit trail nor a suspension disappears silently.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_admin"
down_revision = "0013_billing"
branch_labels = None
depends_on = None

ACTIONS = (
    "'login','login_failed','logout','password_changed','sessions_revoked','admin_created',"
    "'admin_disabled','admin_password_reset','admin_enabled','household_signed_out',"
    "'household_suspended',"
    "'household_restored','household_erased','premium_granted','autopay_cancelled',"
    "'pay_link_created','payment_reconciled','signups_tidied'"
)


def upgrade() -> None:
    op.add_column("users", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("failed_logins", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_admin_users_email_lower")),
        sa.ForeignKeyConstraint(
            ["created_by"], ["admin_users.id"], name=op.f("fk_admin_users_created_by_admin_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_users")),
        sa.UniqueConstraint("email", name=op.f("uq_admin_users_email")),
    )
    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=False),
        sa.Column("token_sha256", sa.Text(), nullable=False),
        sa.Column("device", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admin_users.id"],
            name=op.f("fk_admin_sessions_admin_id_admin_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_sessions")),
        sa.UniqueConstraint("token_sha256", name=op.f("uq_admin_sessions_token_sha256")),
    )
    op.create_index(
        op.f("ix_admin_sessions_admin_id"), "admin_sessions", ["admin_id"], unique=False
    )
    op.create_table(
        "admin_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(f"action IN ({ACTIONS})", name=op.f("ck_admin_events_action")),
        sa.ForeignKeyConstraint(
            ["admin_id"], ["admin_users.id"], name=op.f("fk_admin_events_admin_id_admin_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_events")),
    )
    op.create_index("ix_admin_events_created_at", "admin_events", ["created_at"], unique=False)
    op.create_index("ix_admin_events_household_id", "admin_events", ["household_id"], unique=False)


def downgrade() -> None:
    # Admin accounts carry the audit trail, and a suspension is a deliberate stop.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM admin_users) "
        "OR EXISTS (SELECT 1 FROM users WHERE suspended_at IS NOT NULL) THEN "
        "RAISE EXCEPTION 'Remove admin accounts and restore suspended households first'; "
        "END IF; END $$"
    )
    op.drop_index("ix_admin_events_household_id", table_name="admin_events")
    op.drop_index("ix_admin_events_created_at", table_name="admin_events")
    op.drop_table("admin_events")
    op.drop_index(op.f("ix_admin_sessions_admin_id"), table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_table("admin_users")
    op.drop_column("users", "suspended_at")
