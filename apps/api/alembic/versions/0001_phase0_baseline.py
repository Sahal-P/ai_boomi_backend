"""Establish the Phase 0 migration baseline without domain tables.

Revision ID: 0001_phase0
Revises: none
"""

revision: str = "0001_phase0"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Alembic creates its version table; domain schema belongs to later phases.
    pass


def downgrade() -> None:
    pass
