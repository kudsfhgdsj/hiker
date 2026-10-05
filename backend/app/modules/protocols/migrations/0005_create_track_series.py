"""create track_series

Revision ID: protocols_0005
Revises: protocols_0004
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "protocols_0005"
down_revision = "protocols_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_series",
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("point_count", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tour_id"], ["tour.id"], name=op.f("fk_track_series_tour_id_tour"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("tour_id", name=op.f("pk_track_series")),
    )


def downgrade() -> None:
    op.drop_table("track_series")
