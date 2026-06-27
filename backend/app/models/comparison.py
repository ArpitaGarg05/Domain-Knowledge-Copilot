from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="comparisons")
    documents = relationship(
        "ComparisonDocument",
        back_populates="comparison",
        cascade="all, delete-orphan",
    )
    result = relationship(
        "ComparisonResult",
        back_populates="comparison",
        cascade="all, delete-orphan",
        uselist=False,
    )
    questions = relationship(
        "ComparisonQuestion",
        back_populates="comparison",
        cascade="all, delete-orphan",
        order_by="ComparisonQuestion.created_at",
    )


class ComparisonDocument(Base):
    __tablename__ = "comparison_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    comparison_id: Mapped[int] = mapped_column(
        ForeignKey("comparisons.id"),
        index=True,
    )
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)

    comparison = relationship("Comparison", back_populates="documents")
    document = relationship("Document", back_populates="comparison_links")


class ComparisonResult(Base):
    __tablename__ = "comparison_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    comparison_id: Mapped[int] = mapped_column(
        ForeignKey("comparisons.id"),
        unique=True,
        index=True,
    )
    overall_summary: Mapped[str] = mapped_column(Text, default="")
    comparison_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    comparison = relationship("Comparison", back_populates="result")


class ComparisonQuestion(Base):
    __tablename__ = "comparison_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    comparison_id: Mapped[int] = mapped_column(
        ForeignKey("comparisons.id"),
        index=True,
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    supporting_documents: Mapped[str] = mapped_column(Text, default="[]")
    referenced_sections: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[str] = mapped_column(String(50), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    comparison = relationship("Comparison", back_populates="questions")
