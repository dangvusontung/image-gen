"""Move shared catalog archive state into the database."""
from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table(
        "concept_catalog_states",
        sa.Column("slot", sa.Integer(), primary_key=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("replacement_slot", sa.Integer(), nullable=True),
    )
    from app.concept_defaults import get_catalog
    catalog = get_catalog()
    op.bulk_insert(table, [dict(slot=row.slot, archived=row.slot in catalog.retired_slots,
                               replacement_slot=catalog.retired_slots.get(row.slot)) for row in catalog.concepts])


def downgrade():
    op.drop_table("concept_catalog_states")
