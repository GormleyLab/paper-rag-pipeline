# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Paper RAG Pipeline - A RAG system for academic research paper management designed for AWS AgentCore deployment. Combines Docling (PDF processing), PostgreSQL + pgvector (vector storage), OpenAI embeddings, AWS S3 (PDF storage), and MCP (Model Context Protocol) to provide intelligent paper search and citation management.

**Architecture**: PostgreSQL + pgvector for vector storage, S3 for PDF storage, MCP over HTTP for tool access.

**Output Structure**: For each processed PDF, the system:
- Stores vector embeddings in PostgreSQL with pgvector
- Uploads PDF to S3 (key format: `pdfs/{bibtex_key}.pdf`)
- Generates BibTeX entry stored in the database

## Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with required variables (see Environment Variables section)

# Run database migrations
alembic upgrade head

# Initialize database with PDFs (optional)
python scripts/initial_setup.py /path/to/pdf/folder

# Run the MCP HTTP server
python src/mcp_http_server.py
```

## Environment Variables

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
OPENAI_API_KEY=sk-...
S3_BUCKET=paper-rag-pdfs
AWS_REGION=us-east-1

# Optional
CROSSREF_EMAIL=your@email.com  # Recommended for CrossRef API
AWS_ACCESS_KEY_ID=...          # If not using IAM role
AWS_SECRET_ACCESS_KEY=...      # If not using IAM role
```

## Architecture Overview

### Data Flow Pipeline

1. **PDF Ingestion** → `DocumentProcessor` (Docling) → Markdown + Chunks
2. **Metadata Extraction** → `MetadataExtractor` → pdf2bib/DOI → CrossRef API → BibTeX
3. **Embedding Generation** → `EmbeddingGenerator` (OpenAI) → 3072-dim vectors (batched)
4. **Storage** → `PGVectorStore` (PostgreSQL + pgvector) + `S3Service` (PDF storage)
5. **Query** → User question → Embedding → Vector similarity search → Results

### Component Responsibilities

**`src/mcp_http_server.py`** - MCP HTTP server (main entry point)
- FastMCP with streamable HTTP transport (port 8000)
- Implements 10 async tool handlers for MCP clients
- Lazy initialization of all components
- Health check endpoints at `/health` and `/ping`

**`src/core/settings.py`** - Configuration management
- Pydantic Settings for environment variable loading
- Type-safe configuration with validation
- Settings cached via `get_settings()`

**`src/core/database.py`** - Database connection management
- Async SQLAlchemy engine with asyncpg
- Session management via async context manager
- Database initialization (schema + pgvector extension)

**`src/models/paper.py`** - SQLAlchemy models
- `Paper` - Paper metadata (bibtex_key, title, authors, year, s3_key, etc.)
- `Chunk` - Text chunks with pgvector embedding (3072-dim)
- Cascade delete: deleting a paper removes all its chunks

**`src/pg_vector_store.py`** - PostgreSQL vector operations
- Normalized schema (papers + chunks tables)
- Cosine similarity search with pgvector
- HNSW index for fast vector search
- All operations are async

**`src/services/s3_service.py`** - AWS S3 operations
- PDF upload/download
- Pre-signed URL generation
- Organized as `pdfs/{bibtex_key}.pdf`

**`src/document_processor.py`** - PDF processing
- Uses Docling's `DocumentConverter` for PDF parsing
- `HybridChunker` for semantic chunking (respects token limits)
- Creates `DocumentChunk` dataclass instances with metadata

**`src/metadata_extractor.py`** - Citation metadata
- Strategy pattern for metadata extraction (tries in order):
  1. **pdf2bib** → Extracts DOI/arXiv/PMID directly from PDF
  2. DOI → CrossRef API
  3. arXiv ID → arXiv API
  4. PDF metadata (PyMuPDF)
  5. Document text parsing (fallback)
- Handles BibTeX key collision with letter suffixes

**`src/embeddings.py`** - OpenAI integration
- Batch processing with retry logic
- Cost estimation: $0.00013 per 1K tokens for text-embedding-3-large
- Returns `EmbeddingResult` with token count and cost tracking

**`src/bibliography.py`** - BibTeX management
- Uses `pybtex` library for parsing/generation
- Supports citation styles: inline, APA, MLA

### Database Schema

```sql
-- Schema: paper_rag

CREATE TABLE paper_rag.papers (
    id UUID PRIMARY KEY,
    pdf_hash VARCHAR(64) UNIQUE NOT NULL,
    bibtex_key VARCHAR(100) UNIQUE NOT NULL,
    bibtex_entry TEXT NOT NULL,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,  -- Comma-separated
    year INTEGER NOT NULL,
    journal VARCHAR(500),
    doi VARCHAR(200),
    url VARCHAR(500),
    s3_key VARCHAR(500) NOT NULL,
    extraction_method VARCHAR(50) NOT NULL,
    tags TEXT,              -- Comma-separated
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE paper_rag.chunks (
    id UUID PRIMARY KEY,
    paper_id UUID REFERENCES paper_rag.papers(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding vector(3072) NOT NULL,
    section_title VARCHAR(500) NOT NULL,
    section_hierarchy TEXT NOT NULL,  -- JSON string
    page_number INTEGER,
    element_type VARCHAR(50) NOT NULL
);

-- Indexes
CREATE INDEX idx_papers_bibtex_key ON paper_rag.papers(bibtex_key);
CREATE INDEX idx_papers_year ON paper_rag.papers(year);
CREATE INDEX idx_chunks_paper_id ON paper_rag.chunks(paper_id);
CREATE INDEX idx_chunks_embedding ON paper_rag.chunks USING hnsw (embedding vector_cosine_ops);
```

### MCP Tools (10 implemented)

Each tool is an async function in `mcp_http_server.py`:

**Core Tools:**
1. `search_papers` - Semantic search with optional filters (section, year)
2. `add_paper_from_file` - Add paper from local file path → S3
3. `generate_bibliography` - Create .bib file from paper keys
4. `get_paper_details` - Fetch paper metadata by BibTeX key
5. `database_stats` - Database statistics (paper count, year distribution)
6. `list_recent_papers` - Sort by `created_at` field
7. `delete_paper` - Remove paper and optionally delete from S3

**Upload Tools (for Jiminy/remote clients):**
8. `add_paper_from_upload` - Add paper from base64-encoded PDF
9. `add_papers_from_folder_upload` - Batch upload multiple PDFs

**PDF Retrieval:**
10. `get_paper_pdf` - Download PDF from S3 as base64

### Key Dataclasses

```python
# src/document_processor.py
DocumentChunk(text, chunk_index, section_title, section_hierarchy, page_number, element_type, source_document)

# src/metadata_extractor.py
PaperMetadata(title, authors, year, bibtex_key, bibtex_entry, journal, volume, pages, doi, url, abstract, publisher, extraction_method)

# src/embeddings.py
EmbeddingResult(embedding: list[float], token_count: int, model: str)
```

## Common Development Tasks

### Adding a New MCP Tool

1. Add `@mcp.tool()` decorated async function in `src/mcp_http_server.py`
2. Call `await initialize_components()` at start
3. Use `_vector_store`, `_s3_service`, etc. for operations
4. Return string result

### Modifying the Database Schema

1. Update SQLAlchemy models in `src/models/paper.py`
2. Create new Alembic migration: `alembic revision --autogenerate -m "description"`
3. Review and adjust generated migration
4. Apply: `alembic upgrade head`

### Adding New Metadata Sources

1. Add new method to `MetadataExtractor` class
2. Add new `ExtractionMethod` enum value
3. Call new method in `extract_metadata()` strategy chain
4. Return `PaperMetadata` with appropriate `extraction_method`

## Logging

Logs written to stdout (for container compatibility):
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Log level configured via `LOG_LEVEL` env var or settings

All logs are written to stdout for cloud/container compatibility.

## Error Handling Patterns

**Graceful degradation in metadata extraction**: Tries pdf2bib first, then text-based DOI → CrossRef, then arXiv, then PDF metadata, then parsing. Always returns some `PaperMetadata`.

**Retry logic**: Embeddings and API calls use exponential backoff.

**Duplicate detection**: Papers checked by PDF hash (SHA256) before processing. Skipped silently with log entry.

**Database transactions**: All vector store operations wrapped in async sessions with automatic rollback on error.

## Important Implementation Notes

### PostgreSQL + pgvector
- HNSW index for fast approximate nearest neighbor search
- Cosine similarity via `vector_cosine_ops`
- Async operations throughout
- Schema isolation in `paper_rag` schema

### S3 Storage
- PDFs stored as `pdfs/{bibtex_key}.pdf`
- Pre-signed URLs available for direct access
- Automatic deletion when paper is removed (configurable)

### Docling Chunking
- Chunker uses tokenizer name (string), not actual tokenizer object
- `HybridChunker` balances semantic boundaries with token limits
- Chunk metadata depends on Docling's document structure

### BibTeX Key Collisions
- System auto-appends letters: `Smith2024` → `Smith2024a` → `Smith2024b`
- Pass `existing_keys` set to `generate_bibtex_key()` to avoid collisions

### OpenAI Embedding Costs
- text-embedding-3-large: $0.00013 per 1K tokens
- Typical paper (20 pages): ~10-15 chunks, ~$0.015 total
- Cost tracked in `EmbeddingResult.token_count` and logged

## Development Workflow

1. Make code changes in `src/`
2. Run migrations if schema changed: `alembic upgrade head`
3. Test MCP tools via HTTP client or MCP inspector
4. Check logs for debugging
5. API keys in `.env` (never commit)

## Project Structure

```
paper-rag-pipeline/
├── src/
│   ├── core/
│   │   ├── database.py       # Async SQLAlchemy setup
│   │   └── settings.py       # Pydantic settings
│   ├── models/
│   │   ├── base.py          # SQLAlchemy base
│   │   └── paper.py         # Paper and Chunk models
│   ├── services/
│   │   └── s3_service.py    # S3 operations
│   ├── mcp_http_server.py   # Main MCP server
│   ├── pg_vector_store.py   # PostgreSQL vector operations
│   ├── document_processor.py # PDF processing
│   ├── metadata_extractor.py # Metadata extraction
│   ├── embeddings.py        # OpenAI embeddings
│   ├── bibliography.py      # BibTeX management
│   └── utils.py             # Utilities
├── alembic/
│   ├── env.py
│   └── versions/            # Migration files
├── config/
│   └── config.yaml          # Configuration
├── scripts/
│   └── initial_setup.py     # Batch PDF import
├── requirements.txt
└── alembic.ini
```

## Future Enhancements (Planned)

**Phase 2**: `add_paper_from_url`, `verify_citation`, `update_bibtex`, `import_bibtex_file` tools

**Phase 3**: Citation graph - extract references, build network, analyze co-citations
