"""add document upload metadata

Revision ID: 0002_add_document_upload_metadata
Revises: 0001_create_initial_tables
Create Date: 2026-06-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_document_upload_metadata"
down_revision: Union[str, None] = "0001_create_initial_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("filename", sa.String(length=255), nullable=True))
    op.add_column(
        "documents",
        sa.Column("uploaded_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.execute("UPDATE documents SET filename = title WHERE filename IS NULL")


def downgrade() -> None:
    op.drop_column("documents", "uploaded_at")
    op.drop_column("documents", "filename")
