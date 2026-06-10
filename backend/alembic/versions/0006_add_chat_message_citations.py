"""add chat message citations

Revision ID: 0006_add_chat_message_citations
Revises: 0005_add_chunk_embeddings
Create Date: 2026-06-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_add_chat_message_citations"
down_revision: Union[str, None] = "0005_add_chunk_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("citations", sa.Text(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "citations")
