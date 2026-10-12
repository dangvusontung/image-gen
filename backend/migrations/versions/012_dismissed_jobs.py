"""Keep removed failed jobs for accounting while hiding them from the UI."""
from alembic import op
import sqlalchemy as sa
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("generation_jobs", sa.Column("dismissed", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column("generation_jobs", "dismissed")
