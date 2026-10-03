"""create tour tables

Revision ID: protocols_0001
Revises:
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "protocols_0001"
down_revision = None
branch_labels = ("protocols",)
depends_on = ("gear_0001", "nutrition_0001")


def upgrade() -> None:
    op.create_table(
        "tour",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("pack_weight_start_g", sa.Integer(), nullable=True),
        sa.Column("calories_burned", sa.Float(), nullable=True),
        sa.Column("calories_burned_source", sa.String(length=10), nullable=True),
        sa.Column("start_lat", sa.Float(), nullable=True),
        sa.Column("start_lon", sa.Float(), nullable=True),
        sa.Column("start_name", sa.String(length=200), nullable=True),
        sa.Column("end_lat", sa.Float(), nullable=True),
        sa.Column("end_lon", sa.Float(), nullable=True),
        sa.Column("end_name", sa.String(length=200), nullable=True),
        sa.Column("points_source", sa.String(length=8), nullable=True),
        sa.Column("gpx_file_id", sa.Uuid(), nullable=True),
        sa.Column("track_source", sa.String(length=8), nullable=False),
        sa.Column("track_stats", sa.JSON(), nullable=True),
        sa.Column("cover_photo_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["gpx_file_id"],
            ["file_object.id"],
            name=op.f("fk_tour_gpx_file_id_file_object"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user_account.id"],
            name=op.f("fk_tour_owner_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tour")),
    )
    op.create_index(op.f("ix_tour_owner_id"), "tour", ["owner_id"])

    op.create_table(
        "tour_food_entry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("food_item_id", sa.Uuid(), nullable=True),
        sa.Column("added_by", sa.Uuid(), nullable=True),
        sa.Column("name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("kcal_per_100g_snapshot", sa.Float(), nullable=True),
        sa.Column("amount_g", sa.Float(), nullable=False),
        sa.Column("kcal_snapshot", sa.Float(), nullable=True),
        sa.Column("carried", sa.Boolean(), nullable=False),
        sa.Column("eaten", sa.Boolean(), nullable=False),
        sa.Column("eaten_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["user_account.id"],
            name=op.f("fk_tour_food_entry_added_by_user_account"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["food_item_id"],
            ["food_item.id"],
            name=op.f("fk_tour_food_entry_food_item_id_food_item"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tour_id"],
            ["tour.id"],
            name=op.f("fk_tour_food_entry_tour_id_tour"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tour_food_entry")),
    )
    op.create_index(op.f("ix_tour_food_entry_tour_id"), "tour_food_entry", ["tour_id"])

    op.create_table(
        "tour_peak",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("elevation_m", sa.Integer(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("reached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tour_id"], ["tour.id"], name=op.f("fk_tour_peak_tour_id_tour"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tour_peak")),
    )
    op.create_index(op.f("ix_tour_peak_tour_id"), "tour_peak", ["tour_id"])

    op.create_table(
        "tour_share",
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tour_id"], ["tour.id"], name=op.f("fk_tour_share_tour_id_tour"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_account.id"],
            name=op.f("fk_tour_share_user_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tour_id", "user_id", name=op.f("pk_tour_share")),
    )
    op.create_index(op.f("ix_tour_share_user_id"), "tour_share", ["user_id"])

    op.create_table(
        "tour_waypoint",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("track_distance_m", sa.Float(), nullable=True),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tour_id"], ["tour.id"], name=op.f("fk_tour_waypoint_tour_id_tour"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tour_waypoint")),
    )
    op.create_index(op.f("ix_tour_waypoint_tour_id"), "tour_waypoint", ["tour_id"])

    op.create_table(
        "tour_gear",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("gear_item_id", sa.Uuid(), nullable=True),
        sa.Column("added_by", sa.Uuid(), nullable=True),
        sa.Column("name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("brand_snapshot", sa.String(length=100), nullable=True),
        sa.Column("weight_g_snapshot", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("carried", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["user_account.id"],
            name=op.f("fk_tour_gear_added_by_user_account"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["gear_item_id"],
            ["gear_item.id"],
            name=op.f("fk_tour_gear_gear_item_id_gear_item"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tour_id"], ["tour.id"], name=op.f("fk_tour_gear_tour_id_tour"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tour_gear")),
        sa.UniqueConstraint(
            "tour_id", "gear_item_id", name=op.f("uq_tour_gear_tour_id_gear_item_id")
        ),
    )
    op.create_index(op.f("ix_tour_gear_tour_id"), "tour_gear", ["tour_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tour_gear_tour_id"), table_name="tour_gear")

    op.drop_table("tour_gear")
    op.drop_index(op.f("ix_tour_waypoint_tour_id"), table_name="tour_waypoint")

    op.drop_table("tour_waypoint")
    op.drop_index(op.f("ix_tour_share_user_id"), table_name="tour_share")

    op.drop_table("tour_share")
    op.drop_index(op.f("ix_tour_peak_tour_id"), table_name="tour_peak")

    op.drop_table("tour_peak")
    op.drop_index(op.f("ix_tour_food_entry_tour_id"), table_name="tour_food_entry")

    op.drop_table("tour_food_entry")
    op.drop_index(op.f("ix_tour_owner_id"), table_name="tour")

    op.drop_table("tour")
