"""places along the track

Revision ID: protocols_0008
Revises: protocols_0007
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "protocols_0008"
down_revision = "protocols_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tour_waypoint") as batch_op:
        batch_op.add_column(
            sa.Column("kind", sa.String(length=12), nullable=False, server_default="custom")
        )
        batch_op.add_column(
            sa.Column("source", sa.String(length=8), nullable=False, server_default="manual")
        )
        batch_op.add_column(sa.Column("osm_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("reached_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("tour_peak") as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(length=8), nullable=False, server_default="manual")
        )
    # The defaults were only needed to fill existing rows.
    with op.batch_alter_table("tour_waypoint") as batch_op:
        batch_op.alter_column("kind", server_default=None)
        batch_op.alter_column("source", server_default=None)
    with op.batch_alter_table("tour_peak") as batch_op:
        batch_op.alter_column("source", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("tour_peak") as batch_op:
        batch_op.drop_column("source")
    with op.batch_alter_table("tour_waypoint") as batch_op:
        batch_op.drop_column("reached_at")
        batch_op.drop_column("osm_id")
        batch_op.drop_column("source")
        batch_op.drop_column("kind")
