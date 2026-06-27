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
    op.add_column(
        "comparison_questions",
        sa.Column("evidence", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("comparison_questions", "evidence")
