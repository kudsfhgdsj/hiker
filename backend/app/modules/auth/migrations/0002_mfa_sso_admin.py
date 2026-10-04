"""second factor, single sign-on, password reset by an admin

Revision ID: auth_0002
Revises: auth_0001
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "auth_0002"
down_revision = "auth_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_account") as batch_op:
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column(
                "must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(sa.Column("totp_secret", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("totp_pending_secret", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("totp_last_counter", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("oidc_issuer", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("oidc_subject", sa.String(length=255), nullable=True))
        batch_op.create_index("ix_user_account_oidc", ["oidc_issuer", "oidc_subject"], unique=True)
    with op.batch_alter_table("refresh_token") as batch_op:
        batch_op.add_column(
            sa.Column("auth_method", sa.String(length=8), nullable=False, server_default="pwd")
        )
    op.create_table(
        "recovery_code",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_account.id"],
            name=op.f("fk_recovery_code_user_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recovery_code")),
    )
    op.create_index(op.f("ix_recovery_code_user_id"), "recovery_code", ["user_id"])
    op.create_table(
        "oidc_login",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("state_hash", name=op.f("pk_oidc_login")),
    )


def downgrade() -> None:
    op.drop_table("oidc_login")
    op.drop_index(op.f("ix_recovery_code_user_id"), table_name="recovery_code")
    op.drop_table("recovery_code")
    with op.batch_alter_table("refresh_token") as batch_op:
        batch_op.drop_column("auth_method")
    with op.batch_alter_table("user_account") as batch_op:
        batch_op.drop_index("ix_user_account_oidc")
        for column in (
            "oidc_subject",
            "oidc_issuer",
            "totp_last_counter",
            "totp_enabled_at",
            "totp_pending_secret",
            "totp_secret",
            "must_change_password",
            "last_login_at",
        ):
            batch_op.drop_column(column)
