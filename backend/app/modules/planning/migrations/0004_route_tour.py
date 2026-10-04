"""tours started from a route

Revision ID: planning_0004
Revises: planning_0003
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op

revision = "planning_0004"
down_revision = "planning_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "route_tour",
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("route_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["tour_id"], ["tour.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_id"], ["planned_route.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tour_id"),
    )
    op.create_index("ix_route_tour_route_id", "route_tour", ["route_id"])


def downgrade() -> None:
    op.drop_index("ix_route_tour_route_id", table_name="route_tour")
    op.drop_table("route_tour")
