"""store purchase price as float

Revision ID: gear_0002
Revises: gear_0001
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "gear_0002"
down_revision = "gear_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("gear_item") as batch_op:
        batch_op.alter_column(
            "purchase_price",
            existing_type=sa.Numeric(precision=10, scale=2),
            type_=sa.Float(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("gear_item") as batch_op:
        batch_op.alter_column(
            "purchase_price",
            existing_type=sa.Float(),
            type_=sa.Numeric(precision=10, scale=2),
            existing_nullable=True,
        )
