"""
MCP HTTP Server for Academic RAG Pipeline.
Provides MCP tools over HTTP for remote access (RunPod deployment).
Uses FastMCP with Streamable HTTP transport.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Any
import yaml

from mcp.server.fastmcp import FastMCP

# Import existing components
from src.document_processor import DocumentProcessor
from src.metadata_extractor import MetadataExtractor
from src.embeddings import EmbeddingGenerator
from src.vector_store import VectorStore
from src.bibliography import BibliographyManager, BibliographyEntry
from src.utils import setup_logger, compute_file_hash, save_bibtex_file, copy_pdf_to_database


# Set up logging - use stdout for container compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Global instances (initialized on first use)
_config: Optional[dict] = None
_doc_processor: Optional[DocumentProcessor] = None
_metadata_extractor: Optional[MetadataExtractor] = None
_embedding_generator: Optional[EmbeddingGenerator] = None
_vector_store: Optional[VectorStore] = None
_bibliography_manager: Optional[BibliographyManager] = None


def load_config() -> dict:
    """Load configuration from config.yaml and environment variables."""
    global _config

    if _config is not None:
        return _config

    # Determine project root
    # In container: /app
    # Local: parent of src directory
    if os.path.exists('/app/config'):
        project_root = Path('/app')
    else:
        project_root = Path(__file__).parent.parent.resolve()

    # Get config path from environment or use default
    # RunPod uses config-runpod.yaml by default
    default_config = 'config/config-runpod.yaml' if os.path.exists('/runpod-volume') else 'config/config.yaml'
    config_path = os.getenv('CONFIG_PATH', default_config)
    config_file = Path(config_path)

    # If config path is relative, resolve it from project root
    if not config_file.is_absolute():
        config_file = project_root / config_file

    if not config_file.exists():
        logger.error(f"Config file not found: {config_file}")
        raise FileNotFoundError(f"Config file not found: {config_file}")

    with open(config_file, 'r') as f:
        _config = yaml.safe_load(f)

    # Resolve relative paths in config to project root (only if not absolute)
    for path_key in ['lancedb_path', 'pdf_library_path', 'default_bib_output', 'pdfs_path', 'bibs_output_path']:
        if path_key in _config and _config[path_key]:
            path_value = Path(_config[path_key])
            if not path_value.is_absolute():
                _config[path_key] = str(project_root / path_value)

    # Override with environment variables
    _config['openai_api_key'] = os.getenv('OPENAI_API_KEY', _config.get('openai_api_key', ''))
    _config['crossref_email'] = os.getenv('CROSSREF_EMAIL', _config.get('crossref_email', ''))

    logger.info(f"Configuration loaded successfully from {config_file}")
    logger.info(f"Project root: {project_root}")
    logger.info(f"LanceDB path: {_config.get('lancedb_path')}")
    return _config


def initialize_components():
    """Initialize all pipeline components."""
    global _doc_processor, _metadata_extractor, _embedding_generator, _vector_store, _bibliography_manager

    cfg = load_config()

    # Initialize document processor
    if _doc_processor is None:
        _doc_processor = DocumentProcessor(
            max_chunk_tokens=cfg.get('max_chunk_tokens', 1000),
            chunk_overlap=cfg.get('chunk_overlap', 150),
            embedding_model=cfg.get('embedding_model', 'text-embedding-3-large')
        )
        logger.info("Document processor initialized")

    # Initialize metadata extractor
    if _metadata_extractor is None:
        _metadata_extractor = MetadataExtractor(
            crossref_email=cfg.get('crossref_email')
        )
        logger.info("Metadata extractor initialized")

    # Initialize embedding generator
    if _embedding_generator is None:
        api_key = cfg.get('openai_api_key')
        if not api_key:
            raise ValueError("OpenAI API key not found in config or environment")

        _embedding_generator = EmbeddingGenerator(
            api_key=api_key,
            model=cfg.get('embedding_model', 'text-embedding-3-large'),
            dimensions=cfg.get('vector_dimension', 3072),
            batch_size=cfg.get('batch_size', 100)
        )
        logger.info("Embedding generator initialized")

    # Initialize vector store
    if _vector_store is None:
        db_path = Path(cfg.get('lancedb_path', 'data/lancedb'))
        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        _vector_store = VectorStore(
            db_path=db_path,
            vector_dimension=cfg.get('vector_dimension', 3072)
        )
        _vector_store.initialize_table()
        logger.info(f"Vector store initialized at {db_path}")

    # Initialize bibliography manager
    if _bibliography_manager is None:
        _bibliography_manager = BibliographyManager()
        logger.info("Bibliography manager initialized")

    logger.info("All components initialized successfully")


# Create FastMCP server with stateless HTTP (required for serverless)
mcp = FastMCP(
    "academic-rag",
    stateless_http=True
)


@mcp.tool()
async def search_papers(
    query: str,
    n_results: int = 5,
    filter_section: Optional[str] = None,
    min_year: Optional[int] = None,
    output_format: str = "text"
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
    initialize_components()

    logger.info(f"Searching for: {query}")

    # Generate query embedding
    query_embedding = _embedding_generator.generate_embedding(query)

    # Search vector store
    results = _vector_store.search(
        query_vector=query_embedding.embedding,
        n_results=n_results,
        filter_section=filter_section,
        min_year=min_year
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
            authors_list = [a.strip() for a in result['authors'].split(',') if a.strip()]
            doi = None
            if result.get('url') and 'doi.org/' in result['url']:
                doi = result['url'].split('doi.org/')[-1]

            json_results.append({
                "title": result['title'],
                "authors": authors_list,
                "year": result['year'],
                "journal": result.get('journal'),
                "doi": doi,
                "url": result.get('url'),
                "bibtex_key": result['bibtex_key'],
                "abstract": result.get('text', '')[:500],
                "relevance_score": result.get('_distance', 0.5),
                "section": result.get('section_title'),
                "page": result.get('page_number')
            })

        return json.dumps({
            "results": json_results,
            "query": query,
            "count": len(json_results)
        })

    # Text format (default)
    output_lines = [f"Found {len(results)} relevant papers:\n"]

    for i, result in enumerate(results, 1):
        authors_list = result['authors'].split(',')
        authors_str = ", ".join(authors_list[:3])
        if len(authors_list) > 3:
            authors_str += " et al."

        output_lines.append(f"**[{result['bibtex_key']}]** {result['title']}")
        output_lines.append(f"Authors: {authors_str} ({result['year']})")

        if result['journal']:
            output_lines.append(f"Journal: {result['journal']}")

        if result['url']:
            output_lines.append(f"URL: {result['url']}")

        output_lines.append(
            f"\n**Relevant excerpt** (Section: {result['section_title']}, "
            f"Page {result['page_number'] or 'N/A'}):"
        )

        output_lines.append(result['text'])
        output_lines.append("\n---\n")

    return "\n".join(output_lines)


@mcp.tool()
async def add_paper_from_file(
    file_path: str,
    custom_tags: Optional[list[str]] = None
) -> str:
    """
    Add a PDF paper to the database from a file path.

    Args:
        file_path: Path to the PDF file
        custom_tags: Optional list of tags to associate with the paper

    Returns:
        Status message with paper details
    """
    initialize_components()

    if custom_tags is None:
        custom_tags = []

    pdf_path = Path(file_path)
    logger.info(f"Adding paper from: {pdf_path}")

    if not pdf_path.exists():
        return f"Error: File not found: {pdf_path}"

    # Check for duplicates
    pdf_hash = compute_file_hash(pdf_path)
    if _vector_store.check_duplicate(pdf_hash):
        return f"Paper already exists in database (duplicate PDF detected): {pdf_path.name}"

    # Process PDF
    doc, chunks = _doc_processor.process_pdf(pdf_path)

    # Extract text from first pages for metadata
    first_pages_text = _doc_processor.extract_text_from_first_pages(pdf_path)

    # Extract metadata
    existing_keys = _vector_store.get_all_bibtex_keys()
    metadata = _metadata_extractor.extract_metadata(
        pdf_path,
        first_pages_text=first_pages_text,
        existing_keys=existing_keys
    )

    # Generate embeddings
    chunk_texts = [chunk.text for chunk in chunks]
    embedding_results = _embedding_generator.generate_embeddings_batch(chunk_texts)
    embeddings = [result.embedding for result in embedding_results]

    # Copy PDF to database storage
    cfg = load_config()
    pdfs_dir = Path(cfg.get('pdfs_path', 'data/pdfs'))
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    try:
        copied_pdf_path = copy_pdf_to_database(
            source_pdf=pdf_path,
            bibtex_key=metadata.bibtex_key,
            output_dir=pdfs_dir
        )
        logger.info(f"Copied PDF to database: {copied_pdf_path}")
        pdf_copied = True
    except Exception as e:
        logger.warning(f"Failed to copy PDF: {e}")
        copied_pdf_path = pdf_path
        pdf_copied = False

    # Add to vector store
    num_chunks = _vector_store.add_paper(
        metadata=metadata,
        chunks=chunks,
        embeddings=embeddings,
        pdf_path=copied_pdf_path,
        pdf_hash=pdf_hash,
        tags=custom_tags
    )

    # Save individual BibTeX file
    bibs_dir = Path(cfg.get('bibs_output_path', 'data/bibs'))
    bibs_dir.mkdir(parents=True, exist_ok=True)

    try:
        bib_file_path = save_bibtex_file(
            bibtex_entry=metadata.bibtex_entry,
            bibtex_key=metadata.bibtex_key,
            output_dir=bibs_dir
        )
        logger.info(f"Saved BibTeX file: {bib_file_path}")
        bib_saved = True
    except Exception as e:
        logger.warning(f"Failed to save BibTeX file: {e}")
        bib_saved = False

    # Get embedding stats
    stats = _embedding_generator.get_embedding_stats(embedding_results)

    output = f"""
Successfully added paper to database!

**Title:** {metadata.title}
**Authors:** {', '.join(metadata.authors)}
**Year:** {metadata.year}
**BibTeX Key:** {metadata.bibtex_key}
**DOI:** {metadata.doi or 'N/A'}
**URL:** {metadata.url or 'N/A'}
**Extraction Method:** {metadata.extraction_method.value}

**Indexed:** {num_chunks} chunks
**Tokens Processed:** {stats['total_tokens']}
**Estimated Cost:** ${stats['estimated_cost_usd']:.4f}
{'**PDF File:** Copied to ' + str(pdfs_dir / (metadata.bibtex_key + '.pdf')) if pdf_copied else '**PDF File:** Failed to copy (using original path)'}
{'**BibTeX File:** Saved to ' + str(bibs_dir / (metadata.bibtex_key + '.bib')) if bib_saved else '**BibTeX File:** Failed to save'}

The paper is now searchable in your database.
"""

    return output


@mcp.tool()
async def generate_bibliography(
    bibtex_keys: list[str],
    output_path: str = "./references.bib",
    include_abstracts: bool = False
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
    initialize_components()

    logger.info(f"Generating bibliography with {len(bibtex_keys)} entries")

    # Retrieve papers from database
    entries = []
    missing_keys = []

    for key in bibtex_keys:
        paper = _vector_store.get_paper_by_key(key)
        if paper:
            entry = BibliographyEntry(
                bibtex_key=paper['bibtex_key'],
                bibtex_entry=paper['bibtex_entry'],
                title=paper['title'],
                authors=paper['authors'],
                year=paper['year']
            )
            entries.append(entry)
        else:
            missing_keys.append(key)

    # Generate bibliography file
    result = _bibliography_manager.generate_bibliography_file(
        entries=entries,
        output_path=Path(output_path),
        include_abstracts=include_abstracts
    )

    output_lines = [
        f"Bibliography generated: {output_path}",
        f"\nIncluded: {result['success_count']} entries"
    ]

    if missing_keys:
        output_lines.append(f"\nMissing keys: {', '.join(missing_keys)}")

    if result['errors']:
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
    initialize_components()

    logger.info(f"Getting details for: {bibtex_key}")

    paper = _vector_store.get_paper_by_key(bibtex_key)

    if not paper:
        return f"Paper not found: {bibtex_key}"

    # Get chunk count
    paper_id = paper['pdf_hash'][:16]
    chunks = _vector_store.get_paper_chunks(paper_id)

    output = f"""
**Paper Details**

**Title:** {paper['title']}
**Authors:** {', '.join(paper['authors'])}
**Year:** {paper['year']}
**BibTeX Key:** {paper['bibtex_key']}

**Publication Info:**
- Journal: {paper['journal'] or 'N/A'}
- DOI: {paper['doi'] or 'N/A'}
- URL: {paper['url'] or 'N/A'}

**Database Info:**
- Chunks Indexed: {len(chunks)}
- Date Added: {paper['date_added']}
- Extraction Method: {paper['extraction_method']}
- PDF Path: {paper['pdf_path']}

**BibTeX Entry:**
```bibtex
{paper['bibtex_entry']}
```
"""

    return output


@mcp.tool()
async def database_stats() -> str:
    """
    Get statistics about the paper database.

    Returns:
        Database statistics including paper count, year distribution, etc.
    """
    initialize_components()

    logger.info("Getting database statistics")

    stats = _vector_store.get_statistics()

    output = f"""
**Database Statistics**

**Papers:** {stats['total_papers']}
**Chunks:** {stats['total_chunks']}
**Average Publication Year:** {stats['average_year']}

**Papers by Year:**
"""

    # Sort years
    sorted_years = sorted(stats['year_distribution'].items(), reverse=True)
    for year, count in sorted_years[:10]:
        output += f"\n  {year}: {count} papers"

    if len(sorted_years) > 10:
        output += f"\n  ... and {len(sorted_years) - 10} more years"

    output += f"\n\n**Database Path:** {stats['database_path']}"

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
    initialize_components()

    logger.info(f"Listing {n} recent papers")

    papers = _vector_store.list_recent_papers(n)

    if not papers:
        return "No papers in database."

    output_lines = [f"**Recently Added Papers** (showing {len(papers)}):\n"]

    for i, paper in enumerate(papers, 1):
        authors_str = ", ".join(paper['authors'][:2])
        if len(paper['authors']) > 2:
            authors_str += " et al."

        output_lines.append(
            f"{i}. **[{paper['bibtex_key']}]** {paper['title']}"
        )
        output_lines.append(f"   {authors_str} ({paper['year']})")
        output_lines.append(f"   Added: {paper['date_added'][:10]}\n")

    return "\n".join(output_lines)


@mcp.tool()
async def delete_paper(
    bibtex_key: str,
    delete_files: bool = True
) -> str:
    """
    Delete a paper from the database and optionally remove associated files.

    Args:
        bibtex_key: The BibTeX key of the paper to delete
        delete_files: Whether to delete associated PDF and .bib files (default: true)

    Returns:
        Status message with deletion results
    """
    initialize_components()

    logger.info(f"Deleting paper: {bibtex_key} (delete_files={delete_files})")

    # First check if paper exists and get its details
    paper = _vector_store.get_paper_by_key(bibtex_key)

    if not paper:
        return f"Error: Paper not found in database: {bibtex_key}"

    # Delete from database
    try:
        deleted_count = _vector_store.delete_paper(bibtex_key)
        logger.info(f"Deleted {deleted_count} chunks for paper {bibtex_key}")
    except Exception as e:
        logger.error(f"Error deleting paper from database: {e}", exc_info=True)
        return f"Error deleting paper from database: {str(e)}"

    output_lines = [
        f"Successfully deleted paper from database: {bibtex_key}",
        f"- Title: {paper['title']}",
        f"- Authors: {', '.join(paper['authors'])}",
        f"- Deleted {deleted_count} chunks"
    ]

    # Delete associated files if requested
    if delete_files:
        cfg = load_config()
        files_deleted = []
        files_not_found = []

        # Delete PDF file
        pdfs_dir = Path(cfg.get('pdfs_path', 'data/pdfs'))
        pdf_path = pdfs_dir / f"{bibtex_key}.pdf"

        if pdf_path.exists():
            try:
                pdf_path.unlink()
                files_deleted.append(f"PDF: {pdf_path}")
                logger.info(f"Deleted PDF file: {pdf_path}")
            except Exception as e:
                logger.error(f"Error deleting PDF file: {e}", exc_info=True)
                output_lines.append(f"- Warning: Failed to delete PDF file: {e}")
        else:
            files_not_found.append(f"PDF: {pdf_path}")

        # Delete BibTeX file
        bibs_dir = Path(cfg.get('bibs_output_path', 'data/bibs'))
        bib_path = bibs_dir / f"{bibtex_key}.bib"

        if bib_path.exists():
            try:
                bib_path.unlink()
                files_deleted.append(f".bib: {bib_path}")
                logger.info(f"Deleted BibTeX file: {bib_path}")
            except Exception as e:
                logger.error(f"Error deleting BibTeX file: {e}", exc_info=True)
                output_lines.append(f"- Warning: Failed to delete BibTeX file: {e}")
        else:
            files_not_found.append(f".bib: {bib_path}")

        if files_deleted:
            output_lines.append(f"\nDeleted files:")
            for file_desc in files_deleted:
                output_lines.append(f"  - {file_desc}")

        if files_not_found:
            output_lines.append(f"\nFiles not found (already deleted or never created):")
            for file_desc in files_not_found:
                output_lines.append(f"  - {file_desc}")
    else:
        output_lines.append("\n- Associated files were not deleted (delete_files=False)")

    return "\n".join(output_lines)


def create_app():
    """Create and return the Starlette app with MCP server and auth middleware."""
    from src.auth import BearerAuthMiddleware

    # Get the underlying Starlette app from FastMCP
    app = mcp.streamable_http_app()

    # Add authentication middleware
    app.add_middleware(BearerAuthMiddleware)

    return app


def run_http_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the MCP HTTP server."""
    import uvicorn

    logger.info(f"Starting MCP HTTP server on {host}:{port}")

    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    # For local testing
    run_http_server()
