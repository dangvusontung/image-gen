"""Generation jobs, generated assets, per-project provider/model.

Revision ID: 002
Revises: 001
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("settings", sa.JSON, nullable=False),
        sa.Column("reference_asset_ids", sa.JSON, nullable=False),
        sa.Column("meta", sa.JSON, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("provider_request_id", sa.String(255), nullable=True),
        sa.Column("polling_url", sa.String(1024), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("output_asset_ids", sa.JSON, nullable=False),
        sa.Column("estimated_cost_usd", sa.Float, nullable=True),
        sa.Column("actual_cost_usd", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_generation_jobs_project_id", "generation_jobs", ["project_id"])
    op.create_index("ix_generation_jobs_status_next", "generation_jobs", ["status", "next_attempt_at"])

    with op.batch_alter_table("assets") as batch:
        batch.add_column(sa.Column("job_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_assets_job_id", "generation_jobs", ["job_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_assets_job_id", ["job_id"])

    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("provider", sa.String(32), nullable=False, server_default="mock"))
        batch.add_column(sa.Column("model", sa.String(128), nullable=False, server_default="mock-v1"))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("model")
        batch.drop_column("provider")
    with op.batch_alter_table("assets") as batch:
        batch.drop_index("ix_assets_job_id")
        batch.drop_constraint("fk_assets_job_id", type_="foreignkey")
        batch.drop_column("job_id")
    op.drop_index("ix_generation_jobs_status_next", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_project_id", table_name="generation_jobs")
    op.drop_table("generation_jobs")
