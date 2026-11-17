"""Recoverable generated-image trash, retaining job accounting after purge."""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assets", sa.Column("trashed", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("generation_jobs", sa.Column("purged", sa.Boolean(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("generation_jobs", "purged")
    op.drop_column("assets", "trashed")
