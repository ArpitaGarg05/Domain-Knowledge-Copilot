"""add comparison question evidence

Revision ID: 0011_add_comparison_question_evidence
Revises: 0010_add_comparison_questions
Create Date: 2026-06-27 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_add_comparison_question_evidence"
down_revision: Union[str, None] = "0010_add_comparison_questions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE comparison_questions "
                "ADD COLUMN IF NOT EXISTS evidence TEXT"
            )
        )
        return

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {
        column["name"] for column in inspector.get_columns("comparison_questions")
    }
    if "evidence" in columns:
        return
    op.add_column(
        "comparison_questions",
        sa.Column("evidence", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE comparison_questions "
                "DROP COLUMN IF EXISTS evidence"
            )
        )
        return

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {
        column["name"] for column in inspector.get_columns("comparison_questions")
    }
    if "evidence" not in columns:
        return
    op.drop_column("comparison_questions", "evidence")
