"""add chunk embeddings

Revision ID: 0005_add_chunk_embeddings
Revises: 0004_add_document_chunks
Create Date: 2026-06-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_add_chunk_embeddings"
down_revision: Union[str, None] = "0004_add_document_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("vector_dimension", sa.Integer(), nullable=False),
        sa.Column("vector", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chunk_embeddings_chunk_id"), "chunk_embeddings", ["chunk_id"])
    op.create_index(op.f("ix_chunk_embeddings_id"), "chunk_embeddings", ["id"])
    op.create_index(op.f("ix_chunk_embeddings_model_name"), "chunk_embeddings", ["model_name"])


def downgrade() -> None:
    op.drop_index(op.f("ix_chunk_embeddings_model_name"), table_name="chunk_embeddings")
    op.drop_index(op.f("ix_chunk_embeddings_id"), table_name="chunk_embeddings")
    op.drop_index(op.f("ix_chunk_embeddings_chunk_id"), table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
