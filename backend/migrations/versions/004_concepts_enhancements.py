"""Versioned concept slots and enhancements.

Revision ID: 004
Revises: 003
"""
import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "concepts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch", sa.String(1), nullable=False),
        sa.Column("run", sa.Integer, nullable=False),
        sa.Column("slot", sa.Integer, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("mood", sa.String(128), nullable=False),
        sa.Column("camera", sa.String(128), nullable=False),
        sa.Column("brief", sa.JSON, nullable=False),
        sa.Column("master_version_id", sa.String(36), sa.ForeignKey("master_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turnaround_version_id", sa.String(36), sa.ForeignKey("turnaround_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_concepts_project_id", "concepts", ["project_id"])
    op.create_table(
        "enhancement_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concept_id", sa.String(36), sa.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("master_version_id", sa.String(36), sa.ForeignKey("master_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turnaround_version_id", sa.String(36), sa.ForeignKey("turnaround_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_enhancement_versions_project_id", "enhancement_versions", ["project_id"])
    op.create_index("ix_enhancement_versions_concept_id", "enhancement_versions", ["concept_id"])


def downgrade():
    op.drop_table("enhancement_versions")
    op.drop_table("concepts")
