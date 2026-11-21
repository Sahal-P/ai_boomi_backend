"""Names and search round: the name a household gives and an encrypted Google email.

docs/names-search-round/contract.md. `users.display_name` becomes nullable: NULL means a
self-serve household has not named itself yet, so the placeholder "Household" those rows held
turns into NULL. Google identities gain a Fernet copy of the account's email for the admin panel,
filled in on each Google sign-in. The downgrade restores the placeholder and drops the copy.
"""

import sqlalchemy as sa
from alembic import op

revision = "0019_names"
down_revision = "0018_work_friends"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "display_name", existing_type=sa.Text(), nullable=True)
    op.execute(
        "UPDATE users SET display_name = NULL "
        "WHERE joined_via IS NOT NULL AND display_name = 'Household'"
    )
    op.add_column("user_identities", sa.Column("encrypted_email", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_identities", "encrypted_email")
    op.execute("UPDATE users SET display_name = 'Household' WHERE display_name IS NULL")
    op.alter_column("users", "display_name", existing_type=sa.Text(), nullable=False)
