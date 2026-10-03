"""create tour_photo

Revision ID: protocols_0006
Revises: protocols_0005
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "protocols_0006"
down_revision = "protocols_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tour_photo",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=True),
        sa.Column("thumb_file_id", sa.Uuid(), nullable=True),
        sa.Column("added_by", sa.Uuid(), nullable=True),
        sa.Column("caption", sa.String(length=500), nullable=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exif_lat", sa.Float(), nullable=True),
        sa.Column("exif_lon", sa.Float(), nullable=True),
        sa.Column("exif_altitude", sa.Float(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("position_source", sa.String(length=10), nullable=False),
        sa.Column("track_distance_m", sa.Float(), nullable=True),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("waypoint_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["user_account.id"],
            name=op.f("fk_tour_photo_added_by_user_account"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["file_object.id"],
            name=op.f("fk_tour_photo_file_id_file_object"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["thumb_file_id"],
            ["file_object.id"],
            name=op.f("fk_tour_photo_thumb_file_id_file_object"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tour_id"], ["tour.id"], name=op.f("fk_tour_photo_tour_id_tour"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["waypoint_id"],
            ["tour_waypoint.id"],
            name=op.f("fk_tour_photo_waypoint_id_tour_waypoint"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tour_photo")),
    )
    op.create_index(op.f("ix_tour_photo_tour_id"), "tour_photo", ["tour_id"])
    with op.batch_alter_table("tour") as batch_op:
        batch_op.add_column(
            sa.Column("photo_time_offset_seconds", sa.Integer(), nullable=False, server_default="0")
        )
    # The default was only needed to fill existing rows.
    with op.batch_alter_table("tour") as batch_op:
        batch_op.alter_column("photo_time_offset_seconds", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("tour") as batch_op:
        batch_op.drop_column("photo_time_offset_seconds")
    op.drop_index(op.f("ix_tour_photo_tour_id"), table_name="tour_photo")
    op.drop_table("tour_photo")
