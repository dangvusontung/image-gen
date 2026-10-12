"""Persist provider model catalogues fetched from the provider's own API.

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "provider_catalogs",
        sa.Column("provider", sa.String(32), primary_key=True),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("provider_catalogs")
