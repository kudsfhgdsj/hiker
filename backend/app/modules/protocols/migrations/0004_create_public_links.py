"""create tour_public_link

Revision ID: protocols_0004
Revises: protocols_0003
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "protocols_0004"
down_revision = "protocols_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tour_public_link",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hide_exact_start", sa.Boolean(), nullable=False),
        sa.Column("strip_photo_gps", sa.Boolean(), nullable=False),
        sa.Column("show_health_data", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["user_account.id"],
            name=op.f("fk_tour_public_link_created_by_user_account"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tour_id"],
            ["tour.id"],
            name=op.f("fk_tour_public_link_tour_id_tour"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tour_public_link")),
        sa.UniqueConstraint("token", name=op.f("uq_tour_public_link_token")),
    )
    op.create_index(op.f("ix_tour_public_link_tour_id"), "tour_public_link", ["tour_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tour_public_link_tour_id"), table_name="tour_public_link")
    op.drop_table("tour_public_link")
