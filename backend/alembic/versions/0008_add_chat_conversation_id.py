"""add chat conversation id

Revision ID: 0008_add_chat_conversation_id
Revises: 0007_add_user_password_hash
Create Date: 2026-06-19 00:00:00.000000
"""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "0008_add_chat_conversation_id"
down_revision: Union[str, None] = "0007_add_user_password_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("conversation_id", sa.String(length=64), nullable=True),
    )

    chat_messages = sa.table(
        "chat_messages",
        sa.column("id", sa.Integer()),
        sa.column("corpus_id", sa.Integer()),
        sa.column("user_id", sa.Integer()),
        sa.column("role", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("conversation_id", sa.String()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(
            chat_messages.c.id,
            chat_messages.c.corpus_id,
            chat_messages.c.user_id,
            chat_messages.c.role,
        ).order_by(
            chat_messages.c.user_id,
            chat_messages.c.corpus_id,
            chat_messages.c.created_at,
            chat_messages.c.id,
        )
    )
    active_conversations: dict[tuple[object, object], str] = {}
    for row in rows:
        owner_key = (row.user_id, row.corpus_id)
        if row.role == "user" or owner_key not in active_conversations:
            active_conversations[owner_key] = uuid4().hex
        connection.execute(
            chat_messages.update()
            .where(chat_messages.c.id == row.id)
            .values(conversation_id=active_conversations[owner_key])
        )

    op.create_index(
        op.f("ix_chat_messages_conversation_id"),
        "chat_messages",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_chat_messages_conversation_id"),
        table_name="chat_messages",
    )
    op.drop_column("chat_messages", "conversation_id")
