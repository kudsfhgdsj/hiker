"""create auth tables

Revision ID: auth_0001
Revises:
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "auth_0001"
down_revision = None
branch_labels = ("auth",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_account")),
        sa.UniqueConstraint("email", name=op.f("uq_user_account_email")),
    )
    op.create_table(
        "user_profile",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("sex", sa.String(length=16), nullable=True),
        sa.Column("max_heart_rate", sa.Integer(), nullable=True),
        sa.Column("resting_heart_rate", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_account.id"],
            name=op.f("fk_user_profile_user_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_profile")),
    )
    op.create_table(
        "refresh_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_account.id"],
            name=op.f("fk_refresh_token_user_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_token_token_hash")),
    )
    op.create_index(op.f("ix_refresh_token_user_id"), "refresh_token", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_token_user_id"), table_name="refresh_token")
    op.drop_table("refresh_token")
    op.drop_table("user_profile")
    op.drop_table("user_account")
