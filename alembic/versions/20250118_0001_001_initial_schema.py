"""Initial schema with papers and chunks tables.

Revision ID: 001
Revises:
Create Date: 2025-01-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schema
    op.execute("CREATE SCHEMA IF NOT EXISTS paper_rag")

    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create papers table
    op.create_table(
        "papers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pdf_hash", sa.String(64), nullable=False),
        sa.Column("bibtex_key", sa.String(100), nullable=False),
        sa.Column("bibtex_entry", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("authors", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("journal", sa.String(500), nullable=True),
        sa.Column("doi", sa.String(200), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("extraction_method", sa.String(50), nullable=False),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pdf_hash"),
        sa.UniqueConstraint("bibtex_key"),
        schema="paper_rag",
    )

    # Create indexes for papers
    op.create_index(
        "idx_papers_bibtex_key",
        "papers",
        ["bibtex_key"],
        schema="paper_rag",
    )
    op.create_index(
        "idx_papers_year",
        "papers",
        ["year"],
        schema="paper_rag",
    )
    op.create_index(
        "idx_papers_created_at",
        "papers",
        ["created_at"],
        schema="paper_rag",
        postgresql_using="btree",
    )

    # Create chunks table
    op.create_table(
        "chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("paper_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(3072), nullable=False),
        sa.Column("section_title", sa.String(500), nullable=False),
        sa.Column("section_hierarchy", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("element_type", sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper_rag.papers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="paper_rag",
    )

    # Create indexes for chunks
    op.create_index(
        "idx_chunks_paper_id",
        "chunks",
        ["paper_id"],
        schema="paper_rag",
    )

    # Create HNSW index for vector similarity search
    op.execute(
        """
        CREATE INDEX idx_chunks_embedding ON paper_rag.chunks
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS paper_rag.idx_chunks_embedding")
    op.drop_index("idx_chunks_paper_id", table_name="chunks", schema="paper_rag")
    op.drop_index("idx_papers_created_at", table_name="papers", schema="paper_rag")
    op.drop_index("idx_papers_year", table_name="papers", schema="paper_rag")
    op.drop_index("idx_papers_bibtex_key", table_name="papers", schema="paper_rag")

    # Drop tables
    op.drop_table("chunks", schema="paper_rag")
    op.drop_table("papers", schema="paper_rag")

    # Note: We don't drop the schema or extension as they may be used by other applications
