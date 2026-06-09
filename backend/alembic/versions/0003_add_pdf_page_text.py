"""add pdf page text

Revision ID: 0003_add_pdf_page_text
Revises: 0002_add_document_upload_metadata
Create Date: 2026-06-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_add_pdf_page_text"
down_revision: Union[str, None] = "0002_add_document_upload_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "document_pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_pages_document_id"), "document_pages", ["document_id"])
    op.create_index(op.f("ix_document_pages_id"), "document_pages", ["id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_document_pages_id"), table_name="document_pages")
    op.drop_index(op.f("ix_document_pages_document_id"), table_name="document_pages")
    op.drop_table("document_pages")
    op.drop_column("documents", "page_count")
