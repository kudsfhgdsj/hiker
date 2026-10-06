"""tags of a tour

Revision ID: protocols_0009
Revises: protocols_0008
Create Date: 2026-10-06
"""

import sqlalchemy as sa
from alembic import op

revision = "protocols_0009"
down_revision = "protocols_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tour") as batch_op:
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("tour") as batch_op:
        batch_op.drop_column("tags")
