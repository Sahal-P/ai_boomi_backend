"""Advisor phase 2: cached embeddings for the money guides, memories and chat summaries.

docs/advisor-round/contract.md. Additive only, and every value is regenerable: the guides live
in Git and embeddings can be computed again, so the downgrade simply drops them.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_knowledge"
down_revision = "0015_advisor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_embeddings",
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.REAL()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint(
            "content_hash", "model", "dimensions", name=op.f("pk_knowledge_embeddings")
        ),
    )
    op.add_column("household_memories", sa.Column("embedding", postgresql.ARRAY(sa.REAL())))
    op.add_column("household_memories", sa.Column("embedding_model", sa.Text()))
    op.add_column("advisor_threads", sa.Column("summary_embedding", postgresql.ARRAY(sa.REAL())))
    op.add_column("advisor_threads", sa.Column("embedding_model", sa.Text()))


def downgrade() -> None:
    op.drop_column("advisor_threads", "embedding_model")
    op.drop_column("advisor_threads", "summary_embedding")
    op.drop_column("household_memories", "embedding_model")
    op.drop_column("household_memories", "embedding")
    op.drop_table("knowledge_embeddings")
