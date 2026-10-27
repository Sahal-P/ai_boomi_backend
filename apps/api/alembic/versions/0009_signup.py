"""Sign-up round: self-serve households, sign-in identities, login requests, usage counts.

Additive only. No login code, ID token, name, phone number in clear or message text column is
introduced (docs/signup-round/contract.md).
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_signup"
down_revision = "0008_village_pilot"
branch_labels = None
depends_on = None

SOURCES = "'gmail','eml_upload','demo_mailbox','whatsapp_image','whatsapp_voice'"
PURPOSES = "'consent','confirm','change_amount','undo','due_paid','due_repeat','reminder_opt_in'"
RECEIPT_ERRORS = (
    "'provider_unavailable','invalid_audio','assistant_unavailable','processing_failed',"
    "'window_expired','interrupted','disabled','stale_message','invalid_image',"
    "'capture_unavailable','capture_busy','prompt_expired','record_changed','amount_unclear',"
    "'statement_unavailable'"
)
SIGNUP_ERRORS = ",'signup_full','login_expired','usage_limit','web_not_available'"


def replace(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.add_column("users", sa.Column("joined_via", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("session_epoch", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f("ck_users_joined_via"), "users", "joined_via IN ('whatsapp','google')"
    )
    op.add_column(
        "whatsapp_bindings", sa.Column("encrypted_sender", sa.LargeBinary(), nullable=True)
    )
    replace("email_sources", "source", f"source IN ({SOURCES},'manual_entry')")
    replace("import_runs", "mode", f"mode IN ({SOURCES},'manual_entry')")
    replace("whatsapp_prompts", "purpose", f"purpose IN ({PURPOSES},'web_login','link')")
    replace("whatsapp_receipts", "error_code", f"error_code IN ({RECEIPT_ERRORS}{SIGNUP_ERRORS})")

    op.create_table(
        "user_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("subject_sha256", sa.Text(), nullable=False),
        sa.Column("email_masked", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("provider IN ('google')", name=op.f("ck_user_identities_provider")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_identities_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_identities")),
        sa.UniqueConstraint("provider", "subject_sha256", name=op.f("uq_user_identities_provider")),
    )
    op.create_index(op.f("ix_user_identities_user_id"), "user_identities", ["user_id"])

    op.create_table(
        "login_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code_digest", sa.Text(), nullable=False),
        sa.Column("nonce_digest", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="pending", nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("binding_id", sa.Uuid(), nullable=True),
        sa.Column("device", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("purpose IN ('sign_in','link')", name=op.f("ck_login_requests_purpose")),
        sa.CheckConstraint(
            "state IN ('pending','confirmed','declined','used')",
            name=op.f("ck_login_requests_state"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_login_requests_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            ["whatsapp_bindings.id"],
            name=op.f("fk_login_requests_binding_id_whatsapp_bindings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_requests")),
        sa.UniqueConstraint("code_digest", name=op.f("uq_login_requests_code_digest")),
    )
    op.create_index(op.f("ix_login_requests_user_id"), "login_requests", ["user_id"])
    op.create_index(op.f("ix_login_requests_binding_id"), "login_requests", ["binding_id"])

    op.add_column("whatsapp_prompts", sa.Column("login_request_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_whatsapp_prompts_login_request_id_login_requests"),
        "whatsapp_prompts",
        "login_requests",
        ["login_request_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_whatsapp_prompts_login_request_id"), "whatsapp_prompts", ["login_request_id"]
    )

    op.create_table(
        "signup_waitlist",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sender_hash", sa.Text(), nullable=False),
        sa.Column("encrypted_sender", sa.LargeBinary(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "language IN ('en','hi','ml')", name=op.f("ck_signup_waitlist_language")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signup_waitlist")),
        sa.UniqueConstraint("sender_hash", name=op.f("uq_signup_waitlist_sender_hash")),
    )

    op.create_table(
        "usage_counters",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("kind IN ('ai','voice')", name=op.f("ck_usage_counters_kind")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_usage_counters_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", "day", "kind", name=op.f("pk_usage_counters")),
    )


def downgrade() -> None:
    # Fails closed while sign-up rows use the widened values; nothing is rewritten or deleted.
    op.drop_table("usage_counters")
    op.drop_table("signup_waitlist")
    op.drop_index(op.f("ix_whatsapp_prompts_login_request_id"), table_name="whatsapp_prompts")
    op.drop_constraint(
        op.f("fk_whatsapp_prompts_login_request_id_login_requests"),
        "whatsapp_prompts",
        type_="foreignkey",
    )
    op.drop_column("whatsapp_prompts", "login_request_id")
    op.drop_table("login_requests")
    op.drop_table("user_identities")
    replace("whatsapp_receipts", "error_code", f"error_code IN ({RECEIPT_ERRORS})")
    replace("whatsapp_prompts", "purpose", f"purpose IN ({PURPOSES})")
    replace("import_runs", "mode", f"mode IN ({SOURCES})")
    replace("email_sources", "source", f"source IN ({SOURCES})")
    op.drop_column("whatsapp_bindings", "encrypted_sender")
    op.drop_constraint(op.f("ck_users_joined_via"), "users", type_="check")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "session_epoch")
    op.drop_column("users", "consented_at")
    op.drop_column("users", "joined_via")
