"""Master versions, turnaround versions/views, approval events, prompt overrides.

Revision ID: 003
Revises: 002
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("approved_master_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("approved_turnaround_id", sa.String(36), nullable=True))

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("template_version", sa.Integer, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_prompt_templates_lookup", "prompt_templates", ["name", "project_id", "revision"])

    op.create_table(
        "master_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round", sa.Integer, nullable=False),
        sa.Column("variant", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_master_versions_project_id", "master_versions", ["project_id"])

    op.create_table(
        "turnaround_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("master_version_id", sa.String(36), sa.ForeignKey("master_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("forked_from_id", sa.String(36), sa.ForeignKey("turnaround_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_turnaround_versions_project_id", "turnaround_versions", ["project_id"])

    op.create_table(
        "turnaround_views",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("turnaround_version_id", sa.String(36), sa.ForeignKey("turnaround_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("angle", sa.String(16), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selected", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_turnaround_views_turnaround_version_id", "turnaround_views", ["turnaround_version_id"])

    op.create_table(
        "approval_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("previous_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_approval_events_project_id", "approval_events", ["project_id"])


def downgrade() -> None:
    op.drop_table("approval_events")
    op.drop_table("turnaround_views")
    op.drop_table("turnaround_versions")
    op.drop_table("master_versions")
    op.drop_index("ix_prompt_templates_lookup", table_name="prompt_templates")
    op.drop_table("prompt_templates")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("approved_turnaround_id")
        batch.drop_column("approved_master_id")
