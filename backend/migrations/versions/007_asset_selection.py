"""Let a project use only some of its source photos.

Revision ID: 007
Revises: 006
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    # Existing photos were all in use, so they stay selected.
    op.add_column("assets", sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    with op.batch_alter_table("assets") as batch:
        batch.drop_column("selected")
