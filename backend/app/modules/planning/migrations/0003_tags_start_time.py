"""tags and start time instead of the planned date

Revision ID: planning_0003
Revises: planning_0002
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "planning_0003"
down_revision = "planning_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("planned_route") as batch:
        batch.add_column(sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("start_time", sa.DateTime(timezone=True), nullable=True))
        batch.drop_column("planned_date")
    with op.batch_alter_table("planned_route") as batch:
        batch.alter_column("tags", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("planned_route") as batch:
        batch.add_column(sa.Column("planned_date", sa.Date(), nullable=True))
        batch.drop_column("start_time")
        batch.drop_column("tags")
