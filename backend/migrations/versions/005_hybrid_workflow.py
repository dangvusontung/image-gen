"""Persist opt-in hybrid generation policy.

Revision ID: 005
Revises: 004
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("workflow_mode", sa.String(32), nullable=False, server_default="manual"))


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("workflow_mode")
