"""create contact and tour_partner

Revision ID: protocols_0003
Revises: protocols_0002
Create Date: 2026-10-03
"""

import sqlalchemy as sa
from alembic import op

revision = "protocols_0003"
down_revision = "protocols_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("linked_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["linked_user_id"],
            ["user_account.id"],
            name=op.f("fk_contact_linked_user_id_user_account"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user_account.id"],
            name=op.f("fk_contact_owner_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact")),
    )
    op.create_index(op.f("ix_contact_owner_id"), "contact", ["owner_id"])
    op.create_table(
        "tour_partner",
        sa.Column("tour_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("added_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["user_account.id"],
            name=op.f("fk_tour_partner_added_by_user_account"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contact.id"],
            name=op.f("fk_tour_partner_contact_id_contact"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tour_id"], ["tour.id"], name=op.f("fk_tour_partner_tour_id_tour"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("tour_id", "contact_id", name=op.f("pk_tour_partner")),
    )
    op.create_index(op.f("ix_tour_partner_contact_id"), "tour_partner", ["contact_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tour_partner_contact_id"), table_name="tour_partner")
    op.drop_table("tour_partner")
    op.drop_index(op.f("ix_contact_owner_id"), table_name="contact")
    op.drop_table("contact")
