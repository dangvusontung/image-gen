"""Reusable per-step provider/model presets shared across projects.

Revision ID: 011
Revises: 010
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    # A failed first run of this revision may have left the table behind.
    op.execute("DROP TABLE IF EXISTS presets")
    op.create_table(
        "presets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    # SQLite cannot ALTER in a foreign key, so the column is added in batch (copy-and-move) mode.
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("preset_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_projects_preset", "presets", ["preset_id"], ["id"], ondelete="SET NULL")


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("preset_id")
    op.drop_table("presets")
