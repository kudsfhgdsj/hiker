"""create food_item

Revision ID: nutrition_0001
Revises:
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "nutrition_0001"
down_revision = None
branch_labels = ("nutrition",)
depends_on = "auth_0001"


def upgrade() -> None:
    op.create_table(
        "food_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("catalog_id", sa.Uuid(), nullable=True),
        sa.Column("proposed_by", sa.Uuid(), nullable=True),
        sa.Column("barcode", sa.String(length=14), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand", sa.String(length=100), nullable=True),
        sa.Column("kcal_per_100g", sa.Float(), nullable=True),
        sa.Column("protein_g", sa.Float(), nullable=True),
        sa.Column("carbs_g", sa.Float(), nullable=True),
        sa.Column("fat_g", sa.Float(), nullable=True),
        sa.Column("sugar_g", sa.Float(), nullable=True),
        sa.Column("salt_g", sa.Float(), nullable=True),
        sa.Column("serving_size_g", sa.Float(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("source_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["catalog_id"],
            ["food_item.id"],
            name=op.f("fk_food_item_catalog_id_food_item"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user_account.id"],
            name=op.f("fk_food_item_owner_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["proposed_by"],
            ["user_account.id"],
            name=op.f("fk_food_item_proposed_by_user_account"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_food_item")),
    )
    op.create_index(op.f("ix_food_item_barcode"), "food_item", ["barcode"])
    op.create_index(op.f("ix_food_item_owner_id"), "food_item", ["owner_id"])
    op.create_index(op.f("ix_food_item_visibility"), "food_item", ["visibility"])


def downgrade() -> None:
    op.drop_index(op.f("ix_food_item_visibility"), table_name="food_item")
    op.drop_index(op.f("ix_food_item_owner_id"), table_name="food_item")
    op.drop_index(op.f("ix_food_item_barcode"), table_name="food_item")

    op.drop_table("food_item")
