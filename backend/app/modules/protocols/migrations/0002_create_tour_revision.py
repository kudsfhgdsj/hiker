"""create tour_revision

Revision ID: protocols_0002
Revises: protocols_0001
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "protocols_0002"
down_revision = "protocols_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tour_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("change_summary", sa.String(length=500), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("diff", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["user_account.id"],
            name=op.f("fk_tour_revision_author_user_id_user_account"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tour_id"],
            ["tour.id"],
            name=op.f("fk_tour_revision_tour_id_tour"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tour_revision")),
        sa.UniqueConstraint("tour_id", "version", name=op.f("uq_tour_revision_tour_id_version")),
    )
    op.create_index(op.f("ix_tour_revision_tour_id"), "tour_revision", ["tour_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tour_revision_tour_id"), table_name="tour_revision")
    op.drop_table("tour_revision")
