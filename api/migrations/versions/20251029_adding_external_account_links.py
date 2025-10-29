"""add external_account_links table for external user mapping

Revision ID: 20251029_add_external_links
Revises: 
Create Date: 2025-10-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251029_add_external_links"
down_revision = "ae662b25d9bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_account_links",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("external_source", sa.String(length=64), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("account_id", sa.UUID(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("external_source", "external_user_id", name="uq_external_source_user"),
    )
    op.create_index(
        "ix_external_links_source_user",
        "external_account_links",
        ["external_source", "external_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_links_source_user", table_name="external_account_links")
    op.drop_table("external_account_links")


