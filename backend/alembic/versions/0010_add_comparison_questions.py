"""add comparison questions

Revision ID: 0010_add_comparison_questions
Revises: 0009_add_document_comparisons
Create Date: 2026-06-27 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_add_comparison_questions"
down_revision: Union[str, None] = "0009_add_document_comparisons"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comparison_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("comparison_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("supporting_documents", sa.Text(), nullable=False),
        sa.Column("referenced_sections", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["comparisons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_comparison_questions_comparison_id"),
        "comparison_questions",
        ["comparison_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_comparison_questions_id"),
        "comparison_questions",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_comparison_questions_id"), table_name="comparison_questions")
    op.drop_index(
        op.f("ix_comparison_questions_comparison_id"),
        table_name="comparison_questions",
    )
    op.drop_table("comparison_questions")
