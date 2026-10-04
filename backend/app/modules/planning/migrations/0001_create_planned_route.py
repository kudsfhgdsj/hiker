"""create planned_route

Revision ID: planning_0001
Revises:
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "planning_0001"
down_revision = None
branch_labels = ("planning",)
depends_on = "auth_0001"


def upgrade() -> None:
    op.create_table(
        "planned_route",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("profile", sa.String(length=20), nullable=False),
        sa.Column("max_difficulty", sa.Integer(), nullable=False),
        sa.Column("via_ferrata", sa.Boolean(), nullable=False),
        sa.Column("waypoints", sa.JSON(), nullable=False),
        sa.Column("series", sa.JSON(), nullable=False),
        sa.Column("engine", sa.String(length=30), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("ascent_m", sa.Float(), nullable=True),
        sa.Column("descent_m", sa.Float(), nullable=True),
        sa.Column("min_elevation_m", sa.Float(), nullable=True),
        sa.Column("max_elevation_m", sa.Float(), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user_account.id"],
            name=op.f("fk_planned_route_owner_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planned_route")),
    )
    op.create_index(op.f("ix_planned_route_owner_id"), "planned_route", ["owner_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_planned_route_owner_id"), table_name="planned_route")
    op.drop_table("planned_route")
