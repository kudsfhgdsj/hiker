"""create tour_weather

Revision ID: protocols_0007
Revises: protocols_0006
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "protocols_0007"
down_revision = "protocols_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tour_weather",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("sample_point", sa.String(length=8), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("apparent_temperature_c", sa.Float(), nullable=True),
        sa.Column("wind_speed_kmh", sa.Float(), nullable=True),
        sa.Column("wind_gusts_kmh", sa.Float(), nullable=True),
        sa.Column("precipitation_mm", sa.Float(), nullable=True),
        sa.Column("cloud_cover_pct", sa.Float(), nullable=True),
        sa.Column("freezing_level_m", sa.Float(), nullable=True),
        sa.Column("weather_code", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tour_id"], ["tour.id"], name=op.f("fk_tour_weather_tour_id_tour"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tour_weather")),
        sa.UniqueConstraint(
            "tour_id", "sample_point", name=op.f("uq_tour_weather_tour_id_sample_point")
        ),
    )
    op.create_index(op.f("ix_tour_weather_tour_id"), "tour_weather", ["tour_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tour_weather_tour_id"), table_name="tour_weather")
    op.drop_table("tour_weather")
