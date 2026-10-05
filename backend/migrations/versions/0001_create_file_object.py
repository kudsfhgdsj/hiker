"""create file_object

Revision ID: core_0001
Revises:
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "core_0001"
down_revision = None
branch_labels = ("core",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_object",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_object")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_file_object_storage_key")),
    )
    op.create_index(op.f("ix_file_object_owner_id"), "file_object", ["owner_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_file_object_owner_id"), table_name="file_object")
    op.drop_table("file_object")
