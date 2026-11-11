"""Approve a character concept before creating sticker expressions."""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sticker_packs", sa.Column("concept_brief", sa.Text(), nullable=False, server_default=""))
    op.add_column("sticker_packs", sa.Column("approved_concept_id", sa.String(36), nullable=True))


def downgrade():
    op.drop_column("sticker_packs", "approved_concept_id")
    op.drop_column("sticker_packs", "concept_brief")
