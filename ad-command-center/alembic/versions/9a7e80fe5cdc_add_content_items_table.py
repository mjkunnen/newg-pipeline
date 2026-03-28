"""add_content_items_table

Revision ID: 9a7e80fe5cdc
Revises: 
Create Date: 2026-03-28 03:22:37.132783

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a7e80fe5cdc'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("content_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="discovered"),
        sa.Column("creative_url", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("ad_copy", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_id", "source", name="uq_content_id_source"),
    )
    op.create_index("ix_content_items_status", "content_items", ["status"])
    op.create_index("ix_content_items_source", "content_items", ["source"])


def downgrade() -> None:
    op.drop_index("ix_content_items_source", table_name="content_items")
    op.drop_index("ix_content_items_status", table_name="content_items")
    op.drop_table("content_items")
