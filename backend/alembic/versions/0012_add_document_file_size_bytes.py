"""add document file size bytes

Revision ID: 0012_add_document_file_size_bytes
Revises: 0011_add_comparison_question_evidence
Create Date: 2026-06-30 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_add_document_file_size_bytes"
down_revision: Union[str, None] = "0011_add_comparison_question_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "file_size_bytes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "file_size_bytes")
