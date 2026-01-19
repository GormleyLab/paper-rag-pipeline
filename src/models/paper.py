"""
SQLAlchemy models for papers and chunks with pgvector support.
"""

from typing import Optional, List
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class Paper(Base, UUIDMixin, TimestampMixin):
    """
    Paper model representing a research paper in the database.

    Stores paper-level metadata. Chunks are stored separately with
    a foreign key relationship.
    """

    __tablename__ = "papers"

    # Unique identifiers
    pdf_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    bibtex_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # BibTeX entry
    bibtex_entry: Mapped[str] = mapped_column(Text, nullable=False)

    # Paper metadata
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[str] = mapped_column(Text, nullable=False)  # Comma-separated
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    journal: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Storage
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)

    # Extraction info
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)

    # User-added metadata
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk",
        back_populates="paper",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        Index("idx_papers_bibtex_key", "bibtex_key"),
        Index("idx_papers_year", "year"),
        Index("idx_papers_created_at", "created_at", postgresql_using="btree"),
        {"schema": "paper_rag"},
    )

    def __repr__(self) -> str:
        return f"<Paper(bibtex_key='{self.bibtex_key}', title='{self.title[:50]}...')>"


class Chunk(Base, UUIDMixin):
    """
    Chunk model representing a text chunk from a paper with its embedding.

    Each chunk belongs to a paper and contains:
    - The text content
    - A 3072-dimensional embedding vector (text-embedding-3-large)
    - Positional and structural metadata
    """

    __tablename__ = "chunks"

    # Foreign key to paper
    paper_id: Mapped[UUID] = mapped_column(
        ForeignKey("paper_rag.papers.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Chunk content
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Embedding vector (3072 dimensions for text-embedding-3-large)
    embedding: Mapped[list] = mapped_column(Vector(3072), nullable=False)

    # Chunk metadata
    section_title: Mapped[str] = mapped_column(String(500), nullable=False)
    section_hierarchy: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    paper: Mapped["Paper"] = relationship("Paper", back_populates="chunks")

    # Indexes
    __table_args__ = (
        Index("idx_chunks_paper_id", "paper_id"),
        Index(
            "idx_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"schema": "paper_rag"},
    )

    def __repr__(self) -> str:
        return f"<Chunk(paper_id='{self.paper_id}', chunk_index={self.chunk_index})>"
