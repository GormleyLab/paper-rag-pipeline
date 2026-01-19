"""
PostgreSQL vector store module using pgvector for storing and querying paper chunks.
Replaces the LanceDB implementation for AWS AgentCore deployment.
"""

import json
import logging
from collections import Counter
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_session
from src.models.paper import Paper, Chunk
from src.metadata_extractor import PaperMetadata
from src.document_processor import DocumentChunk

logger = logging.getLogger(__name__)


class PGVectorStore:
    """
    Vector database for storing and querying paper chunks using PostgreSQL + pgvector.
    Provides an interface compatible with the original LanceDB VectorStore.
    """

    def __init__(self, vector_dimension: int = 3072):
        """
        Initialize the vector store.

        Args:
            vector_dimension: Dimension of embedding vectors (3072 for text-embedding-3-large)
        """
        self.vector_dimension = vector_dimension
        logger.info(f"PGVectorStore initialized with dimension={vector_dimension}")

    async def add_paper(
        self,
        metadata: PaperMetadata,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        s3_key: str,
        pdf_hash: str,
        tags: Optional[list[str]] = None,
    ) -> int:
        """
        Add a paper and its chunks to the vector store.

        Args:
            metadata: Paper metadata
            chunks: List of document chunks
            embeddings: List of embedding vectors (one per chunk)
            s3_key: S3 key where the PDF is stored
            pdf_hash: SHA256 hash of the PDF
            tags: Optional list of tags

        Returns:
            Number of chunks added

        Raises:
            ValueError: If chunks and embeddings lengths don't match
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunks count ({len(chunks)}) doesn't match embeddings count ({len(embeddings)})"
            )

        logger.info(f"Adding paper '{metadata.bibtex_key}' with {len(chunks)} chunks")

        tags_str = ",".join(tags) if tags else None
        authors_str = ",".join(metadata.authors)

        async with get_async_session() as session:
            # Create paper record
            paper = Paper(
                id=uuid4(),
                pdf_hash=pdf_hash,
                bibtex_key=metadata.bibtex_key,
                bibtex_entry=metadata.bibtex_entry,
                title=metadata.title,
                authors=authors_str,
                year=metadata.year,
                journal=metadata.journal,
                doi=metadata.doi,
                url=metadata.url,
                s3_key=s3_key,
                extraction_method=metadata.extraction_method.value,
                tags=tags_str,
                notes=None,
            )
            session.add(paper)
            await session.flush()  # Get the paper ID

            # Create chunk records
            for chunk, embedding in zip(chunks, embeddings):
                section_hierarchy_str = json.dumps(chunk.section_hierarchy)

                chunk_record = Chunk(
                    id=uuid4(),
                    paper_id=paper.id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    embedding=embedding,
                    section_title=chunk.section_title,
                    section_hierarchy=section_hierarchy_str,
                    page_number=chunk.page_number,
                    element_type=chunk.element_type,
                )
                session.add(chunk_record)

            # Commit happens automatically via context manager

        logger.info(f"Successfully added {len(chunks)} chunks for paper '{metadata.bibtex_key}'")
        return len(chunks)

    async def search(
        self,
        query_vector: list[float],
        n_results: int = 5,
        filter_section: Optional[str] = None,
        min_year: Optional[int] = None,
        filter_tags: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Search for similar chunks using vector similarity.

        Args:
            query_vector: Query embedding vector
            n_results: Number of results to return
            filter_section: Filter by section title (e.g., "Methods", "Results")
            min_year: Only include papers from this year onwards
            filter_tags: Filter by tags

        Returns:
            List of search results with metadata
        """
        async with get_async_session() as session:
            # Build the query with cosine distance
            # Lower distance = more similar
            query = (
                select(
                    Chunk,
                    Paper,
                    Chunk.embedding.cosine_distance(query_vector).label("distance"),
                )
                .join(Paper, Chunk.paper_id == Paper.id)
                .order_by("distance")
            )

            # Apply filters
            conditions = []

            if min_year:
                conditions.append(Paper.year >= min_year)

            if filter_section:
                conditions.append(
                    func.lower(Chunk.section_title).contains(filter_section.lower())
                )

            if conditions:
                query = query.where(and_(*conditions))

            # Get more results for post-filtering
            query = query.limit(n_results * 3 if filter_tags else n_results)

            result = await session.execute(query)
            rows = result.all()

            # Process results
            filtered_results = []
            for chunk, paper, distance in rows:
                # Tags filter (post-query since it requires string parsing)
                if filter_tags:
                    result_tags = set(paper.tags.split(",")) if paper.tags else set()
                    if not any(tag in result_tags for tag in filter_tags):
                        continue

                filtered_results.append({
                    "text": chunk.text,
                    "bibtex_key": paper.bibtex_key,
                    "bibtex_entry": paper.bibtex_entry,
                    "title": paper.title,
                    "authors": paper.authors,
                    "year": paper.year,
                    "journal": paper.journal,
                    "doi": paper.doi,
                    "url": paper.url,
                    "s3_key": paper.s3_key,
                    "pdf_hash": paper.pdf_hash,
                    "date_added": paper.created_at.isoformat(),
                    "chunk_index": chunk.chunk_index,
                    "section_title": chunk.section_title,
                    "section_hierarchy": chunk.section_hierarchy,
                    "page_number": chunk.page_number,
                    "element_type": chunk.element_type,
                    "tags": paper.tags or "",
                    "extraction_method": paper.extraction_method,
                    "_distance": float(distance),
                })

                if len(filtered_results) >= n_results:
                    break

        logger.info(f"Search returned {len(filtered_results)} results")
        return filtered_results

    async def get_paper_by_key(self, bibtex_key: str) -> Optional[dict]:
        """
        Get paper metadata by BibTeX key.

        Args:
            bibtex_key: BibTeX citation key

        Returns:
            Paper metadata dict or None if not found
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(Paper).where(Paper.bibtex_key == bibtex_key)
            )
            paper = result.scalar_one_or_none()

            if paper:
                return {
                    "id": str(paper.id),
                    "bibtex_key": paper.bibtex_key,
                    "bibtex_entry": paper.bibtex_entry,
                    "title": paper.title,
                    "authors": paper.authors.split(","),
                    "year": paper.year,
                    "journal": paper.journal,
                    "doi": paper.doi,
                    "url": paper.url,
                    "s3_key": paper.s3_key,
                    "pdf_hash": paper.pdf_hash,
                    "date_added": paper.created_at.isoformat(),
                    "extraction_method": paper.extraction_method,
                    "tags": paper.tags,
                    "notes": paper.notes,
                }

        return None

    async def get_paper_chunks(self, paper_id: str) -> list[dict]:
        """
        Get all chunks for a specific paper.

        Args:
            paper_id: Paper UUID as string

        Returns:
            List of chunk records
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(Chunk)
                .where(Chunk.paper_id == UUID(paper_id))
                .order_by(Chunk.chunk_index)
            )
            chunks = result.scalars().all()

            return [
                {
                    "id": str(chunk.id),
                    "paper_id": str(chunk.paper_id),
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "section_title": chunk.section_title,
                    "section_hierarchy": chunk.section_hierarchy,
                    "page_number": chunk.page_number,
                    "element_type": chunk.element_type,
                }
                for chunk in chunks
            ]

    async def check_duplicate(self, pdf_hash: str) -> bool:
        """
        Check if a PDF has already been indexed.

        Args:
            pdf_hash: SHA256 hash of the PDF

        Returns:
            True if duplicate exists, False otherwise
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(func.count()).select_from(Paper).where(Paper.pdf_hash == pdf_hash)
            )
            count = result.scalar()
            return count > 0

    async def get_all_bibtex_keys(self) -> set[str]:
        """
        Get all BibTeX keys currently in the database.

        Returns:
            Set of BibTeX keys
        """
        async with get_async_session() as session:
            result = await session.execute(select(Paper.bibtex_key))
            keys = {row[0] for row in result.all()}
            return keys

    async def delete_paper(self, bibtex_key: str) -> int:
        """
        Delete all chunks for a paper.

        Args:
            bibtex_key: BibTeX key of the paper to delete

        Returns:
            Number of chunks deleted
        """
        async with get_async_session() as session:
            # First get the paper to count chunks
            paper_result = await session.execute(
                select(Paper).where(Paper.bibtex_key == bibtex_key)
            )
            paper = paper_result.scalar_one_or_none()

            if not paper:
                return 0

            # Count chunks
            count_result = await session.execute(
                select(func.count()).select_from(Chunk).where(Chunk.paper_id == paper.id)
            )
            chunk_count = count_result.scalar()

            # Delete paper (chunks will be cascade deleted)
            await session.execute(
                delete(Paper).where(Paper.bibtex_key == bibtex_key)
            )

        logger.info(f"Deleted {chunk_count} chunks for paper '{bibtex_key}'")
        return chunk_count

    async def get_statistics(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dictionary with database stats
        """
        async with get_async_session() as session:
            # Count papers
            paper_count_result = await session.execute(
                select(func.count()).select_from(Paper)
            )
            total_papers = paper_count_result.scalar()

            # Count chunks
            chunk_count_result = await session.execute(
                select(func.count()).select_from(Chunk)
            )
            total_chunks = chunk_count_result.scalar()

            # Get year distribution
            years_result = await session.execute(select(Paper.year))
            years = [row[0] for row in years_result.all()]
            avg_year = sum(years) / len(years) if years else 0
            year_distribution = dict(Counter(years))

        return {
            "total_papers": total_papers,
            "total_chunks": total_chunks,
            "average_year": int(avg_year) if avg_year else None,
            "year_distribution": year_distribution,
            "database_type": "PostgreSQL + pgvector",
        }

    async def list_recent_papers(self, n: int = 10) -> list[dict]:
        """
        List recently added papers.

        Args:
            n: Number of papers to return

        Returns:
            List of recent papers with metadata
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(Paper)
                .order_by(Paper.created_at.desc())
                .limit(n)
            )
            papers = result.scalars().all()

            return [
                {
                    "bibtex_key": paper.bibtex_key,
                    "title": paper.title,
                    "authors": paper.authors.split(","),
                    "year": paper.year,
                    "date_added": paper.created_at.isoformat(),
                    "extraction_method": paper.extraction_method,
                }
                for paper in papers
            ]

    async def update_paper_metadata(
        self,
        bibtex_key: str,
        updated_metadata: dict,
    ) -> bool:
        """
        Update metadata for a paper.

        Args:
            bibtex_key: BibTeX key of the paper to update
            updated_metadata: Dictionary of fields to update

        Returns:
            True if update was successful, False if paper not found
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(Paper).where(Paper.bibtex_key == bibtex_key)
            )
            paper = result.scalar_one_or_none()

            if not paper:
                return False

            # Update allowed fields
            allowed_fields = {"tags", "notes", "title", "authors", "year", "journal", "doi", "url"}
            for field, value in updated_metadata.items():
                if field in allowed_fields and hasattr(paper, field):
                    setattr(paper, field, value)

            paper.updated_at = datetime.utcnow()

        logger.info(f"Updated metadata for paper '{bibtex_key}'")
        return True
