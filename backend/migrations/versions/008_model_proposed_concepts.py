"""Model-proposed concepts replace the fixed A/B batches.

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "concept_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("master_version_id", sa.String(36), sa.ForeignKey("master_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("brief", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_concept_proposals_project_id", "concept_proposals", ["project_id"])
    with op.batch_alter_table("concepts") as batch:
        batch.drop_column("batch")


def downgrade():
    with op.batch_alter_table("concepts") as batch:
        batch.add_column(sa.Column("batch", sa.String(1), nullable=False, server_default="A"))
    op.drop_index("ix_concept_proposals_project_id", table_name="concept_proposals")
    op.drop_table("concept_proposals")
