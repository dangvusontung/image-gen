"""Separate sticker packs backed by the shared project, asset and job core."""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sticker_packs",
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("publisher", sa.String(128), nullable=False),
        sa.Column("style", sa.String(32), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("sticker_packs")
