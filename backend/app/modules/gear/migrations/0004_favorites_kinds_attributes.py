"""favourite tag, kinds of gear types, attributes of items, prices in EUR

Revision ID: gear_0004
Revises: gear_0003
Create Date: 2026-10-04
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "gear_0004"
down_revision = "gear_0003"
branch_labels = None
depends_on = None

# Standard types with extra fields; an existing standard type of that name is reused.
SEEDED_TYPES = (("Rucksack", "backpack", 10), ("Schuhe", "shoes", 20))


def upgrade() -> None:
    op.add_column("gear_type", sa.Column("kind", sa.String(length=32), nullable=True))
    op.add_column("gear_tag", sa.Column("system", sa.String(length=32), nullable=True))
    op.add_column("gear_item", sa.Column("attributes", sa.JSON(), nullable=True))
    # Prices are always in EUR from now on.
    op.execute("UPDATE gear_item SET currency = 'EUR' WHERE purchase_price IS NOT NULL")
    op.execute("UPDATE gear_item SET currency = NULL WHERE purchase_price IS NULL")

    connection = op.get_bind()
    gear_type = sa.table(
        "gear_type",
        sa.column("id", sa.Uuid()),
        sa.column("owner_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("kind", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    for name, kind, sort_order in SEEDED_TYPES:
        existing = connection.execute(
            sa.select(gear_type.c.id).where(
                gear_type.c.owner_id.is_(None), sa.func.lower(gear_type.c.name) == name.lower()
            )
        ).scalar()
        if existing is not None:
            connection.execute(
                gear_type.update().where(gear_type.c.id == existing).values(kind=kind)
            )
        else:
            connection.execute(
                gear_type.insert().values(
                    id=uuid.uuid4(),
                    owner_id=None,
                    name=name,
                    kind=kind,
                    sort_order=sort_order,
                    created_at=now,
                    updated_at=now,
                )
            )


def downgrade() -> None:
    op.drop_column("gear_item", "attributes")
    op.drop_column("gear_tag", "system")
    op.drop_column("gear_type", "kind")
