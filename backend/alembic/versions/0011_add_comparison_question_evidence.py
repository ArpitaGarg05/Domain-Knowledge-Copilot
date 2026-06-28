"""add comparison question evidence

Revision ID: 0011_add_comparison_question_evidence
Revises: 0010_add_comparison_questions
Create Date: 2026-06-27 00:00:00.000000
"""

from typing import Sequence, Union

revision: str = "0011_add_comparison_question_evidence"
down_revision: Union[str, None] = "0010_add_comparison_questions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally no-op.
    #
    # Evidence for comparison Q&A is derived from the already persisted
    # referenced_sections payload. Keeping this revision lets databases advance
    # past 0010 without requiring startup DDL on comparison_questions, which can
    # block production PostgreSQL boots if another session holds a table lock.
    pass


def downgrade() -> None:
    pass
