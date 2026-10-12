"""Remember which reference leads each generation step.

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("step_leads", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("step_leads")
