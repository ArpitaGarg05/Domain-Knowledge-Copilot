"""add user password hash

Revision ID: 0007_add_user_password_hash
Revises: 0006_add_chat_message_citations
Create Date: 2026-06-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_add_user_password_hash"
down_revision: Union[str, None] = "0006_add_chat_message_citations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "password_hash")
