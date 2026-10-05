"""create gear tags

Revision ID: gear_0003
Revises: gear_0002
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "gear_0003"
down_revision = "gear_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gear_tag",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user_account.id"],
            name=op.f("fk_gear_tag_owner_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gear_tag")),
    )
    op.create_index(op.f("ix_gear_tag_owner_id"), "gear_tag", ["owner_id"])
    op.create_table(
        "gear_item_tag",
        sa.Column("gear_item_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["gear_item_id"],
            ["gear_item.id"],
            name=op.f("fk_gear_item_tag_gear_item_id_gear_item"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["gear_tag.id"],
            name=op.f("fk_gear_item_tag_tag_id_gear_tag"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("gear_item_id", "tag_id", name=op.f("pk_gear_item_tag")),
    )
    op.create_index(op.f("ix_gear_item_tag_tag_id"), "gear_item_tag", ["tag_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_gear_item_tag_tag_id"), table_name="gear_item_tag")
    op.drop_table("gear_item_tag")
    op.drop_index(op.f("ix_gear_tag_owner_id"), table_name="gear_tag")
    op.drop_table("gear_tag")
