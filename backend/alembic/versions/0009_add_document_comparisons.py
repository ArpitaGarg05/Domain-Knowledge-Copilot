"""add document comparisons

Revision ID: 0009_add_document_comparisons
Revises: 0008_add_chat_conversation_id
Create Date: 2026-06-27 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_add_document_comparisons"
down_revision: Union[str, None] = "0008_add_chat_conversation_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comparisons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comparisons_id"), "comparisons", ["id"], unique=False)
    op.create_index(op.f("ix_comparisons_user_id"), "comparisons", ["user_id"], unique=False)

    op.create_table(
        "comparison_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comparison_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["comparisons.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_comparison_documents_comparison_id"),
        "comparison_documents",
        ["comparison_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_comparison_documents_document_id"),
        "comparison_documents",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_comparison_documents_id"),
        "comparison_documents",
        ["id"],
        unique=False,
    )

    op.create_table(
        "comparison_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comparison_id", sa.Integer(), nullable=False),
        sa.Column("overall_summary", sa.Text(), nullable=False),
        sa.Column("comparison_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["comparisons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_comparison_results_comparison_id"),
        "comparison_results",
        ["comparison_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_comparison_results_id"),
        "comparison_results",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_comparison_results_id"), table_name="comparison_results")
    op.drop_index(
        op.f("ix_comparison_results_comparison_id"),
        table_name="comparison_results",
    )
    op.drop_table("comparison_results")
    op.drop_index(op.f("ix_comparison_documents_id"), table_name="comparison_documents")
    op.drop_index(
        op.f("ix_comparison_documents_document_id"),
        table_name="comparison_documents",
    )
    op.drop_index(
        op.f("ix_comparison_documents_comparison_id"),
        table_name="comparison_documents",
    )
    op.drop_table("comparison_documents")
    op.drop_index(op.f("ix_comparisons_user_id"), table_name="comparisons")
    op.drop_index(op.f("ix_comparisons_id"), table_name="comparisons")
    op.drop_table("comparisons")
