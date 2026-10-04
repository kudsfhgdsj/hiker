"""pace of a route and saved paces

Revision ID: planning_0002
Revises: planning_0001
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "planning_0002"
down_revision = "planning_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("planned_route") as batch:
        batch.add_column(
            sa.Column("pace_preset", sa.String(length=10), nullable=False, server_default="dav")
        )
        batch.add_column(sa.Column("pace_name", sa.String(length=100), nullable=True))
        batch.add_column(
            sa.Column("pace_ascent_m_per_h", sa.Float(), nullable=False, server_default="300")
        )
        batch.add_column(
            sa.Column("pace_descent_m_per_h", sa.Float(), nullable=False, server_default="500")
        )
        batch.add_column(
            sa.Column("pace_distance_km_per_h", sa.Float(), nullable=False, server_default="4")
        )
    with op.batch_alter_table("planned_route") as batch:
        for column in (
            "pace_preset",
            "pace_ascent_m_per_h",
            "pace_descent_m_per_h",
            "pace_distance_km_per_h",
        ):
            batch.alter_column(column, server_default=None)
    op.create_table(
        "pace_profile",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("ascent_m_per_h", sa.Float(), nullable=False),
        sa.Column("descent_m_per_h", sa.Float(), nullable=False),
        sa.Column("distance_km_per_h", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user_account.id"],
            name=op.f("fk_pace_profile_owner_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pace_profile")),
    )
    op.create_index(op.f("ix_pace_profile_owner_id"), "pace_profile", ["owner_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_pace_profile_owner_id"), table_name="pace_profile")
    op.drop_table("pace_profile")
    with op.batch_alter_table("planned_route") as batch:
        for column in (
            "pace_distance_km_per_h",
            "pace_descent_m_per_h",
            "pace_ascent_m_per_h",
            "pace_name",
            "pace_preset",
        ):
            batch.drop_column(column)
