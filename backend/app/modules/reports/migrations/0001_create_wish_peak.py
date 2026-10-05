"""create wish_peak

Revision ID: reports_0001
Revises:
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op

revision = "reports_0001"
down_revision = None
branch_labels = ("reports",)
depends_on = "auth_0001"


def upgrade() -> None:
    op.create_table(
        "wish_peak",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("elevation_m", sa.Integer(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user_account.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wish_peak_owner_id", "wish_peak", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_wish_peak_owner_id", table_name="wish_peak")
    op.drop_table("wish_peak")
