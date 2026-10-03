"""create gear tables

Revision ID: gear_0001
Revises:
Create Date: 2026-10-03
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "gear_0001"
down_revision = None
branch_labels = ("gear",)
depends_on = ("auth_0001", "core_0001")

# Standard list of gear types (owner_id NULL = visible to everyone, edited by admins).
STANDARD_TYPES = [
    "Rucksack",
    "Zelt & Biwak",
    "Schlafen",
    "Bekleidung",
    "Schuhe",
    "Kochen & Trinken",
    "Navigation & Elektronik",
    "Klettern & Hochtour",
    "Wintersport",
    "Sicherheit & Erste Hilfe",
    "Hygiene",
    "Sonstiges",
]
_TYPE_NAMESPACE = uuid.UUID("6f1d3c0a-5b7e-4a52-9d0e-2c8a4f6b1e90")


def upgrade() -> None:
    op.create_table(
        "gear_list",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user_account.id"],
            name=op.f("fk_gear_list_owner_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gear_list")),
    )
    op.create_index(op.f("ix_gear_list_owner_id"), "gear_list", ["owner_id"])

    gear_type = op.create_table(
        "gear_type",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user_account.id"],
            name=op.f("fk_gear_type_owner_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gear_type")),
    )
    op.create_index(op.f("ix_gear_type_owner_id"), "gear_type", ["owner_id"])
    now = datetime.now(UTC)
    op.bulk_insert(
        gear_type,
        [
            {
                "id": uuid.uuid5(_TYPE_NAMESPACE, name),
                "owner_id": None,
                "name": name,
                "sort_order": (position + 1) * 10,
                "created_at": now,
                "updated_at": now,
            }
            for position, name in enumerate(STANDARD_TYPES)
        ],
    )

    op.create_table(
        "gear_catalog_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand", sa.String(length=100), nullable=True),
        sa.Column("type_id", sa.Uuid(), nullable=True),
        sa.Column("nominal_weight_g", sa.Integer(), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("image_file_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["user_account.id"],
            name=op.f("fk_gear_catalog_item_created_by_user_account"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["image_file_id"],
            ["file_object.id"],
            name=op.f("fk_gear_catalog_item_image_file_id_file_object"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["type_id"],
            ["gear_type.id"],
            name=op.f("fk_gear_catalog_item_type_id_gear_type"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gear_catalog_item")),
    )
    op.create_index(op.f("ix_gear_catalog_item_status"), "gear_catalog_item", ["status"])

    op.create_table(
        "gear_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_id", sa.Uuid(), nullable=True),
        sa.Column("type_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand", sa.String(length=100), nullable=True),
        sa.Column("weight_g", sa.Integer(), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("image_file_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("size", sa.String(length=50), nullable=True),
        sa.Column("color", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["catalog_id"],
            ["gear_catalog_item.id"],
            name=op.f("fk_gear_item_catalog_id_gear_catalog_item"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["image_file_id"],
            ["file_object.id"],
            name=op.f("fk_gear_item_image_file_id_file_object"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user_account.id"],
            name=op.f("fk_gear_item_owner_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["type_id"],
            ["gear_type.id"],
            name=op.f("fk_gear_item_type_id_gear_type"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gear_item")),
    )
    op.create_index(op.f("ix_gear_item_owner_id"), "gear_item", ["owner_id"])

    op.create_table(
        "gear_list_item",
        sa.Column("list_id", sa.Uuid(), nullable=False),
        sa.Column("gear_item_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["gear_item_id"],
            ["gear_item.id"],
            name=op.f("fk_gear_list_item_gear_item_id_gear_item"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["list_id"],
            ["gear_list.id"],
            name=op.f("fk_gear_list_item_list_id_gear_list"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("list_id", "gear_item_id", name=op.f("pk_gear_list_item")),
    )


def downgrade() -> None:
    op.drop_table("gear_list_item")
    op.drop_index(op.f("ix_gear_item_owner_id"), table_name="gear_item")

    op.drop_table("gear_item")
    op.drop_index(op.f("ix_gear_catalog_item_status"), table_name="gear_catalog_item")

    op.drop_table("gear_catalog_item")
    op.drop_index(op.f("ix_gear_type_owner_id"), table_name="gear_type")

    op.drop_table("gear_type")
    op.drop_index(op.f("ix_gear_list_owner_id"), table_name="gear_list")

    op.drop_table("gear_list")
