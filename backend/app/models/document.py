from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    corpus_id: Mapped[int] = mapped_column(ForeignKey("corpora.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_preview: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    corpus = relationship("Corpus", back_populates="documents")
