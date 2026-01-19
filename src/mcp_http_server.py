"""
MCP HTTP Server for Paper RAG Pipeline.
AWS AgentCore compatible MCP server with PostgreSQL + pgvector backend.
Uses FastMCP with Streamable HTTP transport.
"""

import base64
import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.routing import Route

# Import existing components
from src.document_processor import DocumentProcessor
from src.metadata_extractor import MetadataExtractor
from src.embeddings import EmbeddingGenerator
from src.pg_vector_store import PGVectorStore
from src.bibliography import BibliographyManager, BibliographyEntry
from src.services.s3_service import S3Service
from src.core.settings import get_settings
from src.core.database import init_db
from src.utils import (
    compute_file_hash,
    compute_hash_from_bytes,
)


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Global instances (initialized on first use)
_initialized: bool = False
_doc_processor: Optional[DocumentProcessor] = None
_metadata_extractor: Optional[MetadataExtractor] = None
_embedding_generator: Optional[EmbeddingGenerator] = None
_vector_store: Optional[PGVectorStore] = None
_bibliography_manager: Optional[BibliographyManager] = None
_s3_service: Optional[S3Service] = None


async def initialize_components():
    """Initialize all pipeline components asynchronously."""
    global \
        _initialized, \
        _doc_processor, \
        _metadata_extractor, \
        _embedding_generator, \
        _vector_store, \
        _bibliography_manager, \
        _s3_service

    if _initialized:
        return

    settings = get_settings()

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize document processor
    if _doc_processor is None:
        _doc_processor = DocumentProcessor(
            max_chunk_tokens=settings.max_chunk_tokens,
            chunk_overlap=settings.chunk_overlap,
            embedding_model=settings.embedding_model,
        )
        logger.info("Document processor initialized")

    # Initialize metadata extractor
    if _metadata_extractor is None:
        _metadata_extractor = MetadataExtractor(
            crossref_email=settings.crossref_email
        )
        logger.info("Metadata extractor initialized")

    # Initialize embedding generator
    if _embedding_generator is None:
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not found in environment")

        _embedding_generator = EmbeddingGenerator(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
            dimensions=settings.vector_dimension,
            batch_size=settings.batch_size,
        )
        logger.info("Embedding generator initialized")

    # Initialize PostgreSQL vector store
    if _vector_store is None:
        _vector_store = PGVectorStore(
            vector_dimension=settings.vector_dimension
        )
        logger.info("PostgreSQL vector store initialized")

    # Initialize bibliography manager
    if _bibliography_manager is None:
        _bibliography_manager = BibliographyManager()
        logger.info("Bibliography manager initialized")

    # Initialize S3 service
    if _s3_service is None:
        _s3_service = S3Service()
        logger.info("S3 service initialized")

    _initialized = True
    logger.info("All components initialized successfully")


# Create FastMCP server with stateless HTTP
mcp = FastMCP("paper-rag", stateless_http=True)


@mcp.tool()
async def search_papers(
    query: str,
    n_results: int = 5,
    filter_section: Optional[str] = None,
    min_year: Optional[int] = None,
    output_format: str = "text",
) -> str:
    """
    Search the paper database for relevant content using semantic search.

    Args:
        query: Search query string
        n_results: Number of results to return (1-20, default: 5)
        filter_section: Filter by section type (Methods, Results, Discussion, Introduction)
        min_year: Only papers from this year onwards
        output_format: 'text' for human-readable (default), 'json' for structured data

    Returns:
        Search results formatted as text or JSON
    """
    await initialize_components()

    logger.info(f"Searching for: {query}")

    # Generate query embedding
    query_embedding = _embedding_generator.generate_embedding(query)

    # Search vector store
    results = await _vector_store.search(
        query_vector=query_embedding.embedding,
        n_results=n_results,
        filter_section=filter_section,
        min_year=min_year,
    )

    # Handle no results
    if not results:
        if output_format == "json":
            return json.dumps({"results": [], "query": query, "count": 0})
        return "No results found for your query."

    # JSON format for programmatic access
    if output_format == "json":
        json_results = []
        for result in results:
            authors_list = [
                a.strip() for a in result["authors"].split(",") if a.strip()
            ]
            doi = None
            if result.get("url") and "doi.org/" in result["url"]:
                doi = result["url"].split("doi.org/")[-1]

            json_results.append(
                {
                    "title": result["title"],
                    "authors": authors_list,
                    "year": result["year"],
                    "journal": result.get("journal"),
                    "doi": doi,
                    "url": result.get("url"),
                    "bibtex_key": result["bibtex_key"],
                    "text": result.get("text", ""),
                    "relevance_score": result.get("_distance", 0.5),
                    "section": result.get("section_title"),
                    "page": result.get("page_number"),
                }
            )

        return json.dumps(
            {"results": json_results, "query": query, "count": len(json_results)}
        )

    # Text format (default)
    output_lines = [f"Found {len(results)} relevant papers:\n"]

    for i, result in enumerate(results, 1):
        authors_list = result["authors"].split(",")
        authors_str = ", ".join(authors_list[:3])
        if len(authors_list) > 3:
            authors_str += " et al."

        output_lines.append(f"**[{result['bibtex_key']}]** {result['title']}")
        output_lines.append(f"Authors: {authors_str} ({result['year']})")

        if result["journal"]:
            output_lines.append(f"Journal: {result['journal']}")

        if result["url"]:
            output_lines.append(f"URL: {result['url']}")

        output_lines.append(
            f"\n**Relevant excerpt** (Section: {result['section_title']}, "
            f"Page {result['page_number'] or 'N/A'}):"
        )

        output_lines.append(result["text"])
        output_lines.append("\n---\n")

    return "\n".join(output_lines)


@mcp.tool()
async def add_paper_from_file(
    file_path: str, custom_tags: Optional[list[str]] = None
) -> str:
    """
    Add a PDF paper to the database from a file path.

    Args:
        file_path: Path to the PDF file
        custom_tags: Optional list of tags to associate with the paper

    Returns:
        Status message with paper details
    """
    await initialize_components()

    if custom_tags is None:
        custom_tags = []

    pdf_path = Path(file_path)
    logger.info(f"Adding paper from: {pdf_path}")

    if not pdf_path.exists():
        return f"Error: File not found: {pdf_path}"

    # Check for duplicates
    pdf_hash = compute_file_hash(pdf_path)
    if await _vector_store.check_duplicate(pdf_hash):
        return f"Paper already exists in database (duplicate PDF detected): {pdf_path.name}"

    # Process PDF
    doc, chunks = _doc_processor.process_pdf(pdf_path)

    # Extract text from first pages for metadata
    first_pages_text = _doc_processor.extract_text_from_first_pages(pdf_path)

    # Extract metadata
    existing_keys = await _vector_store.get_all_bibtex_keys()
    metadata = _metadata_extractor.extract_metadata(
        pdf_path, first_pages_text=first_pages_text, existing_keys=existing_keys
    )

    # Generate embeddings
    chunk_texts = [chunk.text for chunk in chunks]
    embedding_results = _embedding_generator.generate_embeddings_batch(chunk_texts)
    embeddings = [result.embedding for result in embedding_results]

    # Upload PDF to S3
    try:
        s3_key = await _s3_service.upload_pdf_from_file(
            file_path=pdf_path,
            bibtex_key=metadata.bibtex_key,
        )
        logger.info(f"Uploaded PDF to S3: {s3_key}")
    except Exception as e:
        logger.error(f"Failed to upload PDF to S3: {e}")
        return f"Error: Failed to upload PDF to S3: {str(e)}"

    # Add to vector store
    num_chunks = await _vector_store.add_paper(
        metadata=metadata,
        chunks=chunks,
        embeddings=embeddings,
        s3_key=s3_key,
        pdf_hash=pdf_hash,
        tags=custom_tags,
    )

    # Get embedding stats
    stats = _embedding_generator.get_embedding_stats(embedding_results)

    output = f"""
Successfully added paper to database!

**Title:** {metadata.title}
**Authors:** {", ".join(metadata.authors)}
**Year:** {metadata.year}
**BibTeX Key:** {metadata.bibtex_key}
**DOI:** {metadata.doi or "N/A"}
**URL:** {metadata.url or "N/A"}
**Extraction Method:** {metadata.extraction_method.value}

**Indexed:** {num_chunks} chunks
**Tokens Processed:** {stats["total_tokens"]}
**Estimated Cost:** ${stats["estimated_cost_usd"]:.4f}
**PDF Storage:** S3 ({s3_key})

The paper is now searchable in your database.
"""

    return output


@mcp.tool()
async def add_paper_from_upload(
    pdf_data: str, filename: str, custom_tags: Optional[list[str]] = None
) -> str:
    """
    Add a PDF paper to the database from base64-encoded data.

    This tool accepts PDF content directly uploaded, enabling PDF uploads
    to the MCP server without requiring files to exist on the server filesystem.

    Args:
        pdf_data: Base64-encoded PDF file content
        filename: Original filename of the PDF (for logging and metadata fallback)
        custom_tags: Optional list of tags to associate with the paper

    Returns:
        Status message with paper details
    """
    await initialize_components()

    if custom_tags is None:
        custom_tags = []

    logger.info(f"Adding paper from upload: {filename}")

    # Step 1: Decode base64 data
    try:
        pdf_bytes = base64.b64decode(pdf_data)
    except Exception as e:
        logger.error(f"Failed to decode base64 PDF data: {e}")
        return f"Error: Invalid base64 data - {str(e)}"

    # Step 2: Validate PDF magic bytes
    if not pdf_bytes.startswith(b"%PDF"):
        return "Error: Invalid PDF file - data does not start with PDF magic bytes"

    # Step 3: Compute hash for duplicate detection
    pdf_hash = compute_hash_from_bytes(pdf_bytes)

    if await _vector_store.check_duplicate(pdf_hash):
        return f"Paper already exists in database (duplicate PDF detected): {filename}"

    # Step 4: Write to temporary file for processing
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".pdf",
            delete=False,
        ) as temp_file:
            temp_file.write(pdf_bytes)
            temp_path = Path(temp_file.name)

        logger.info(f"Created temporary file: {temp_path}")

        # Step 5: Process PDF
        doc, chunks = _doc_processor.process_pdf(temp_path)

        # Step 6: Extract text from first pages for metadata
        first_pages_text = _doc_processor.extract_text_from_first_pages(temp_path)

        # Step 7: Extract metadata
        existing_keys = await _vector_store.get_all_bibtex_keys()
        metadata = _metadata_extractor.extract_metadata(
            temp_path, first_pages_text=first_pages_text, existing_keys=existing_keys
        )

        # Step 8: Generate embeddings
        chunk_texts = [chunk.text for chunk in chunks]
        embedding_results = _embedding_generator.generate_embeddings_batch(chunk_texts)
        embeddings = [result.embedding for result in embedding_results]

        # Step 9: Upload PDF to S3
        try:
            s3_key = await _s3_service.upload_pdf_from_bytes(
                pdf_bytes=pdf_bytes,
                bibtex_key=metadata.bibtex_key,
            )
            logger.info(f"Uploaded PDF to S3: {s3_key}")
        except Exception as e:
            logger.error(f"Failed to upload PDF to S3: {e}")
            return f"Error: Failed to upload PDF to S3: {str(e)}"

        # Step 10: Add to vector store
        num_chunks = await _vector_store.add_paper(
            metadata=metadata,
            chunks=chunks,
            embeddings=embeddings,
            s3_key=s3_key,
            pdf_hash=pdf_hash,
            tags=custom_tags,
        )

        # Step 11: Get embedding stats
        stats = _embedding_generator.get_embedding_stats(embedding_results)

        output = f"""
Successfully added paper to database!

**Title:** {metadata.title}
**Authors:** {", ".join(metadata.authors)}
**Year:** {metadata.year}
**BibTeX Key:** {metadata.bibtex_key}
**DOI:** {metadata.doi or "N/A"}
**URL:** {metadata.url or "N/A"}
**Extraction Method:** {metadata.extraction_method.value}
**Original Filename:** {filename}

**Indexed:** {num_chunks} chunks
**Tokens Processed:** {stats["total_tokens"]}
**Estimated Cost:** ${stats["estimated_cost_usd"]:.4f}
**PDF Storage:** S3 ({s3_key})

The paper is now searchable in your database.
"""

        return output

    except Exception as e:
        logger.error(f"Error processing uploaded PDF: {e}", exc_info=True)
        return f"Error processing PDF: {str(e)}"

    finally:
        # Clean up temporary file
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
                logger.info(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file: {e}")


@mcp.tool()
async def add_papers_from_folder_upload(
    pdf_files: list[dict], custom_tags: Optional[list[str]] = None
) -> str:
    """
    Add multiple PDF papers to the database from base64-encoded data.

    Use this for batch uploading PDFs. The client should read all PDFs,
    encode them as base64, and send them in a single request.

    Args:
        pdf_files: List of dicts, each with 'filename' (str) and 'pdf_data' (str, base64-encoded)
        custom_tags: Optional list of tags to apply to all papers

    Returns:
        Summary with processed/skipped/failed counts and details
    """
    await initialize_components()

    if custom_tags is None:
        custom_tags = []

    logger.info(f"Batch upload started: {len(pdf_files)} PDFs")

    # Initialize tracking
    processed = 0
    skipped = 0
    failed = 0
    total_cost = 0.0

    successful_papers = []
    skipped_papers = []
    failed_papers = []

    # Get existing BibTeX keys once for collision detection across batch
    existing_keys = await _vector_store.get_all_bibtex_keys()

    for pdf_item in pdf_files:
        filename = pdf_item.get("filename", "unknown.pdf")
        pdf_data = pdf_item.get("pdf_data", "")
        temp_path = None

        try:
            # Decode base64 data
            try:
                pdf_bytes = base64.b64decode(pdf_data)
            except Exception as e:
                logger.error(f"Failed to decode base64 for {filename}: {e}")
                failed_papers.append((filename, f"Invalid base64 data: {str(e)}"))
                failed += 1
                continue

            # Validate PDF magic bytes
            if not pdf_bytes.startswith(b"%PDF"):
                logger.warning(f"Invalid PDF magic bytes for {filename}")
                failed_papers.append((filename, "Invalid PDF file - not a valid PDF"))
                failed += 1
                continue

            # Compute hash for duplicate detection
            pdf_hash = compute_hash_from_bytes(pdf_bytes)

            if await _vector_store.check_duplicate(pdf_hash):
                logger.info(f"Skipping duplicate: {filename}")
                skipped_papers.append((filename, "already in database"))
                skipped += 1
                continue

            # Write to temporary file
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".pdf", delete=False
            ) as temp_file:
                temp_file.write(pdf_bytes)
                temp_path = Path(temp_file.name)

            logger.info(f"Processing: {filename}")

            # Process PDF
            doc, chunks = _doc_processor.process_pdf(temp_path)

            # Extract text from first pages for metadata
            first_pages_text = _doc_processor.extract_text_from_first_pages(temp_path)

            # Extract metadata
            metadata = _metadata_extractor.extract_metadata(
                temp_path,
                first_pages_text=first_pages_text,
                existing_keys=existing_keys,
            )

            # Add new key to existing_keys to prevent collisions within batch
            existing_keys.add(metadata.bibtex_key)

            # Generate embeddings
            chunk_texts = [chunk.text for chunk in chunks]
            embedding_results = _embedding_generator.generate_embeddings_batch(
                chunk_texts
            )
            embeddings = [result.embedding for result in embedding_results]

            # Track cost
            stats = _embedding_generator.get_embedding_stats(embedding_results)
            total_cost += stats["estimated_cost_usd"]

            # Upload PDF to S3
            try:
                s3_key = await _s3_service.upload_pdf_from_bytes(
                    pdf_bytes=pdf_bytes,
                    bibtex_key=metadata.bibtex_key,
                )
            except Exception as e:
                logger.error(f"Failed to upload PDF to S3 for {filename}: {e}")
                failed_papers.append((filename, f"S3 upload failed: {str(e)}"))
                failed += 1
                continue

            # Add to vector store
            await _vector_store.add_paper(
                metadata=metadata,
                chunks=chunks,
                embeddings=embeddings,
                s3_key=s3_key,
                pdf_hash=pdf_hash,
                tags=custom_tags,
            )

            # Track success
            successful_papers.append((metadata.bibtex_key, metadata.title))
            processed += 1
            logger.info(
                f"Successfully processed: {filename} -> [{metadata.bibtex_key}]"
            )

        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}", exc_info=True)
            failed_papers.append((filename, str(e)))
            failed += 1

        finally:
            # Clean up temporary file
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file for {filename}: {e}")

    # Build response
    output_lines = ["**Batch Upload Complete!**\n"]

    output_lines.append("**Summary:**")
    output_lines.append(f"- Processed: {processed} papers")
    output_lines.append(f"- Skipped (duplicates): {skipped} papers")
    output_lines.append(f"- Failed: {failed} papers")
    output_lines.append(f"- Total Embedding Cost: ${total_cost:.4f}\n")

    if successful_papers:
        output_lines.append("**Successfully Added:**")
        for i, (key, title) in enumerate(successful_papers, 1):
            display_title = title[:60] + "..." if len(title) > 60 else title
            output_lines.append(f'{i}. [{key}] "{display_title}"')
        output_lines.append("")

    if skipped_papers:
        output_lines.append("**Skipped (duplicates):**")
        for filename, reason in skipped_papers:
            output_lines.append(f"- {filename} ({reason})")
        output_lines.append("")

    if failed_papers:
        output_lines.append("**Failed:**")
        for filename, error in failed_papers:
            display_error = error[:80] + "..." if len(error) > 80 else error
            output_lines.append(f"- {filename}: {display_error}")

    return "\n".join(output_lines)


@mcp.tool()
async def generate_bibliography(
    bibtex_keys: list[str],
    output_path: str = "./references.bib",
    include_abstracts: bool = False,
) -> str:
    """
    Create a .bib file with specified papers.

    Args:
        bibtex_keys: List of BibTeX keys to include
        output_path: Where to save the file
        include_abstracts: Include abstract field in entries

    Returns:
        Status message with generation results
    """
    await initialize_components()

    logger.info(f"Generating bibliography with {len(bibtex_keys)} entries")

    # Retrieve papers from database
    entries = []
    missing_keys = []

    for key in bibtex_keys:
        paper = await _vector_store.get_paper_by_key(key)
        if paper:
            entry = BibliographyEntry(
                bibtex_key=paper["bibtex_key"],
                bibtex_entry=paper["bibtex_entry"],
                title=paper["title"],
                authors=paper["authors"],
                year=paper["year"],
            )
            entries.append(entry)
        else:
            missing_keys.append(key)

    # Generate bibliography file
    result = _bibliography_manager.generate_bibliography_file(
        entries=entries,
        output_path=Path(output_path),
        include_abstracts=include_abstracts,
    )

    output_lines = [
        f"Bibliography generated: {output_path}",
        f"\nIncluded: {result['success_count']} entries",
    ]

    if missing_keys:
        output_lines.append(f"\nMissing keys: {', '.join(missing_keys)}")

    if result["errors"]:
        output_lines.append(f"\nErrors: {', '.join(result['errors'])}")

    return "\n".join(output_lines)


@mcp.tool()
async def get_paper_details(bibtex_key: str) -> str:
    """
    Retrieve complete information about a specific paper.

    Args:
        bibtex_key: The BibTeX key of the paper

    Returns:
        Detailed paper information
    """
    await initialize_components()

    logger.info(f"Getting details for: {bibtex_key}")

    paper = await _vector_store.get_paper_by_key(bibtex_key)

    if not paper:
        return f"Paper not found: {bibtex_key}"

    # Get chunk count
    chunks = await _vector_store.get_paper_chunks(paper["id"])

    output = f"""
**Paper Details**

**Title:** {paper["title"]}
**Authors:** {", ".join(paper["authors"])}
**Year:** {paper["year"]}
**BibTeX Key:** {paper["bibtex_key"]}

**Publication Info:**
- Journal: {paper["journal"] or "N/A"}
- DOI: {paper["doi"] or "N/A"}
- URL: {paper["url"] or "N/A"}

**Database Info:**
- Chunks Indexed: {len(chunks)}
- Date Added: {paper["date_added"][:10]}
- Extraction Method: {paper["extraction_method"]}
- Storage: S3 ({paper["s3_key"]})

**BibTeX Entry:**
```bibtex
{paper["bibtex_entry"]}
```
"""

    return output


@mcp.tool()
async def get_paper_pdf(bibtex_key: str) -> str:
    """
    Retrieve the PDF file for a specific paper as base64-encoded data.

    Args:
        bibtex_key: The BibTeX key of the paper

    Returns:
        Base64-encoded PDF file content as a string
    """
    await initialize_components()

    logger.info(f"Getting PDF for: {bibtex_key}")

    # First check if paper exists
    paper = await _vector_store.get_paper_by_key(bibtex_key)

    if not paper:
        return f"Error: Paper not found: {bibtex_key}"

    try:
        # Download PDF from S3
        pdf_bytes = await _s3_service.download_pdf(paper["s3_key"])

        # Encode to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
        logger.info(
            f"Successfully retrieved PDF for {bibtex_key} ({len(pdf_bytes)} bytes)"
        )

        return pdf_base64

    except Exception as e:
        logger.error(f"Error retrieving PDF for {bibtex_key}: {e}", exc_info=True)
        return f"Error: Failed to retrieve PDF: {str(e)}"


@mcp.tool()
async def database_stats() -> str:
    """
    Get statistics about the paper database.

    Returns:
        Database statistics including paper count, year distribution, etc.
    """
    await initialize_components()

    logger.info("Getting database statistics")

    stats = await _vector_store.get_statistics()

    output = f"""
**Database Statistics**

**Papers:** {stats["total_papers"]}
**Chunks:** {stats["total_chunks"]}
**Average Publication Year:** {stats["average_year"]}
**Backend:** {stats["database_type"]}

**Papers by Year:**
"""

    # Sort years
    sorted_years = sorted(stats["year_distribution"].items(), reverse=True)
    for year, count in sorted_years[:10]:
        output += f"\n  {year}: {count} papers"

    if len(sorted_years) > 10:
        output += f"\n  ... and {len(sorted_years) - 10} more years"

    return output


@mcp.tool()
async def list_recent_papers(n: int = 10) -> str:
    """
    Show recently added papers.

    Args:
        n: Number of papers to show (default: 10)

    Returns:
        List of recently added papers
    """
    await initialize_components()

    logger.info(f"Listing {n} recent papers")

    papers = await _vector_store.list_recent_papers(n)

    if not papers:
        return "No papers in database."

    output_lines = [f"**Recently Added Papers** (showing {len(papers)}):\n"]

    for i, paper in enumerate(papers, 1):
        authors_str = ", ".join(paper["authors"][:2])
        if len(paper["authors"]) > 2:
            authors_str += " et al."

        output_lines.append(f"{i}. **[{paper['bibtex_key']}]** {paper['title']}")
        output_lines.append(f"   {authors_str} ({paper['year']})")
        output_lines.append(f"   Added: {paper['date_added'][:10]}\n")

    return "\n".join(output_lines)


@mcp.tool()
async def delete_paper(bibtex_key: str, delete_s3: bool = True) -> str:
    """
    Delete a paper from the database and optionally remove from S3.

    Args:
        bibtex_key: The BibTeX key of the paper to delete
        delete_s3: Whether to delete the PDF from S3 (default: true)

    Returns:
        Status message with deletion results
    """
    await initialize_components()

    logger.info(f"Deleting paper: {bibtex_key} (delete_s3={delete_s3})")

    # First check if paper exists and get its details
    paper = await _vector_store.get_paper_by_key(bibtex_key)

    if not paper:
        return f"Error: Paper not found in database: {bibtex_key}"

    # Delete from database
    try:
        deleted_count = await _vector_store.delete_paper(bibtex_key)
        logger.info(f"Deleted {deleted_count} chunks for paper {bibtex_key}")
    except Exception as e:
        logger.error(f"Error deleting paper from database: {e}", exc_info=True)
        return f"Error deleting paper from database: {str(e)}"

    output_lines = [
        f"Successfully deleted paper from database: {bibtex_key}",
        f"- Title: {paper['title']}",
        f"- Authors: {', '.join(paper['authors'])}",
        f"- Deleted {deleted_count} chunks",
    ]

    # Delete from S3 if requested
    if delete_s3:
        try:
            await _s3_service.delete_pdf(paper["s3_key"])
            output_lines.append(f"\nDeleted PDF from S3: {paper['s3_key']}")
            logger.info(f"Deleted PDF from S3: {paper['s3_key']}")
        except Exception as e:
            logger.error(f"Error deleting PDF from S3: {e}", exc_info=True)
            output_lines.append(f"\nWarning: Failed to delete PDF from S3: {e}")
    else:
        output_lines.append("\n- PDF retained in S3 (delete_s3=False)")

    return "\n".join(output_lines)


def create_app():
    """
    Create and return the Starlette app with MCP server and health endpoints.

    Use this for local testing with uvicorn:
        uvicorn src.mcp_http_server:create_app --factory --host 0.0.0.0 --port 8000

    Or with run_http_server():
        python -c "from src.mcp_http_server import run_http_server; run_http_server()"
    """
    # Get the underlying Starlette app from FastMCP
    starlette_app = mcp.streamable_http_app()

    # Add health check endpoints
    async def health(_request):
        """Health check endpoint."""
        return JSONResponse({"status": "ok", "service": "paper-rag"})

    starlette_app.routes.append(Route("/health", health, methods=["GET"]))
    starlette_app.routes.append(Route("/ping", health, methods=["GET"]))

    return starlette_app


def run_http_server(host: str = "0.0.0.0", port: int = 8000):
    """
    Run the MCP HTTP server with custom health endpoints.

    For local testing only. For AWS AgentCore deployment, use:
        agentcore configure -e src/mcp_http_server.py --protocol MCP
        agentcore launch
    """
    import uvicorn

    logger.info(f"Starting MCP HTTP server on {host}:{port}")
    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    # AWS AgentCore compatible entry point
    # Uses mcp.run() which AgentCore expects
    # Serves on 0.0.0.0:8000 at /mcp endpoint
    mcp.run(transport="streamable-http")
