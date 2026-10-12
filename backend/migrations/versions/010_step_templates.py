"""Per-step template image for art direction.

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("step_templates", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("step_templates")
