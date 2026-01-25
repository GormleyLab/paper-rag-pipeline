# Implementation Status - Paper RAG Pipeline

**Version:** 2.1.0 (AWS App Runner)
**Date:** January 2025
**Status:** Production Ready

---

## Summary

The Paper RAG Pipeline provides intelligent search and citation management through MCP over HTTP. Supports two deployment options:
- **AWS App Runner** (Recommended): Static API key authentication, simple deployment
- **AWS AgentCore**: SigV4/Cognito authentication for Bedrock integration

The system uses PostgreSQL + pgvector for vector storage and AWS S3 for PDF storage.

**Production URL**: `https://m76rjhx9i3.us-east-1.awsapprunner.com`
**API Key**: Store in `.env` as `PAPERRAG_API_KEY` (retrieve from AWS Secrets Manager: `paperrag/api-key`)

## Architecture

| Component | Technology | Status |
|-----------|-----------|--------|
| Vector Database | PostgreSQL + pgvector | Production |
| PDF Storage | AWS S3 | Production |
| MCP Server | FastMCP (HTTP) | Production |
| Embeddings | OpenAI text-embedding-3-large | Production |
| PDF Processing | Docling | Production |

## Implemented Components

### Core Modules

| Module | File | Status | Description |
|--------|------|--------|-------------|
| **Settings** | `src/core/settings.py` | Production | Pydantic settings with env vars |
| **Database** | `src/core/database.py` | Production | Async SQLAlchemy + asyncpg |
| **Models** | `src/models/paper.py` | Production | SQLAlchemy models with pgvector |
| **S3 Service** | `src/services/s3_service.py` | Production | AWS S3 operations |
| **Vector Store** | `src/pg_vector_store.py` | Production | PostgreSQL vector operations |
| **MCP Server** | `src/mcp_http_server.py` | Production | MCP HTTP server with 10 tools |
| **Document Processor** | `src/document_processor.py` | Production | Docling PDF processing |
| **Metadata Extractor** | `src/metadata_extractor.py` | Production | Citation metadata extraction |
| **Embeddings** | `src/embeddings.py` | Production | OpenAI embedding generation |
| **Bibliography** | `src/bibliography.py` | Production | BibTeX management |
| **Utils** | `src/utils.py` | Production | Helper functions |

### Database Migrations

| Migration | Status | Description |
|-----------|--------|-------------|
| `001_initial_schema.py` | Complete | Papers and chunks tables with pgvector |

---

## MCP Tools (10 Implemented)

### Core Tools
1. **search_papers** - Semantic search with filters (section, year, tags)
2. **add_paper_from_file** - Add PDF from local file path
3. **generate_bibliography** - Create .bib file from paper keys
4. **get_paper_details** - Retrieve paper metadata
5. **database_stats** - Database statistics
6. **list_recent_papers** - Show recent additions
7. **delete_paper** - Remove paper from database and S3

### Upload Tools (for remote clients)
8. **add_paper_from_upload** - Add paper from base64-encoded PDF
9. **add_papers_from_folder_upload** - Batch upload multiple PDFs

### PDF Retrieval
10. **get_paper_pdf** - Download PDF from S3 as base64

---

## Features

### Document Processing
- PDF to Markdown conversion using Docling
- Hybrid chunking with configurable token limits
- Section hierarchy preservation
- Element type detection (paragraph, table, figure, equation)

### Metadata Extraction
- pdf2bib integration (primary method)
- DOI extraction and CrossRef API
- arXiv API integration
- PDF metadata fallback
- Automatic BibTeX key generation with collision handling

### Vector Search
- PostgreSQL + pgvector with HNSW indexing
- 3072-dimensional embeddings (text-embedding-3-large)
- Cosine similarity search
- Section and year filtering
- Async operations throughout

### Storage
- PDFs stored in S3 (`pdfs/{bibtex_key}.pdf`)
- Pre-signed URL generation
- Automatic deletion with paper removal

### Bibliography Management
- BibTeX file generation
- Multiple citation styles (inline, APA, MLA)
- Citation key extraction from LaTeX

---

## Database Schema

```sql
-- paper_rag.papers
- id (UUID, PK)
- pdf_hash (VARCHAR, unique)
- bibtex_key (VARCHAR, unique)
- bibtex_entry (TEXT)
- title, authors, year, journal, doi, url
- s3_key (VARCHAR)
- extraction_method (VARCHAR)
- tags, notes (TEXT)
- created_at, updated_at (TIMESTAMPTZ)

-- paper_rag.chunks
- id (UUID, PK)
- paper_id (UUID, FK -> papers)
- chunk_index (INTEGER)
- text (TEXT)
- embedding (vector(3072))
- section_title, section_hierarchy, page_number, element_type
```

---

## Configuration

### Environment Variables
```bash
DATABASE_URL          # PostgreSQL connection string
OPENAI_API_KEY        # OpenAI API key
S3_BUCKET             # S3 bucket name
AWS_REGION            # AWS region
PAPERRAG_API_KEY      # API key for authentication (App Runner)
CROSSREF_EMAIL        # Optional, for CrossRef API
PORT                  # Server port (default: 8080)
```

### Server Settings
- Port: 8080 (configurable via PORT env var)
- Endpoints: `/mcp`, `/health`, `/ping`
- Transport: Streamable HTTP
- Authentication: Bearer token (when PAPERRAG_API_KEY is set)

---

## Performance

| Metric | Value |
|--------|-------|
| Search latency | <500ms typical |
| Paper processing | ~2 minutes/paper |
| Embedding cost | ~$0.015/paper |
| Vector dimensions | 3072 |
| Index type | HNSW (cosine) |

---

## Known Limitations

1. **PubMed Integration**: Placeholder only - full API integration pending
2. **Multi-language**: English only currently
3. **Figure/Table Extraction**: Basic detection only, not indexed separately

---

## Future Enhancements

### Phase 2: Enhanced Features
- [ ] `add_paper_from_url` (DOI/arXiv/URL support)
- [ ] `verify_citation` (metadata review)
- [ ] `update_bibtex` (manual overrides)
- [ ] `import_bibtex_file` (.bib file import)

### Phase 3: Citation Graph
- [ ] Reference extraction from papers
- [ ] Citation relationship storage
- [ ] Network analysis tools
- [ ] Foundational paper identification

---

## File Structure

```
paper-rag-pipeline/
├── src/
│   ├── core/
│   │   ├── database.py         # Async SQLAlchemy
│   │   └── settings.py         # Pydantic settings
│   ├── models/
│   │   ├── base.py             # SQLAlchemy base
│   │   └── paper.py            # Paper/Chunk models
│   ├── services/
│   │   └── s3_service.py       # S3 operations
│   ├── mcp_http_server.py      # MCP HTTP server
│   ├── pg_vector_store.py      # Vector operations
│   ├── document_processor.py   # PDF processing
│   ├── metadata_extractor.py   # Metadata extraction
│   ├── embeddings.py           # OpenAI embeddings
│   ├── bibliography.py         # BibTeX management
│   └── utils.py                # Utilities
├── alembic/
│   └── versions/               # Migrations
├── config/
│   └── config.yaml             # Configuration
├── scripts/
│   └── initial_setup.py        # Batch import
└── requirements.txt
```

---

## Deployment Checklist

### Local Development
1. [ ] Install dependencies: `pip install -r requirements.txt`
2. [ ] Configure `.env` with required variables
3. [ ] Set up PostgreSQL with pgvector
4. [ ] Create S3 bucket
5. [ ] Run migrations: `alembic upgrade head`
6. [ ] Start server: `python -m src.mcp_http_server`
7. [ ] Verify: `curl http://localhost:8080/health`
8. [ ] Test tools via MCP client

### AWS App Runner (Recommended)
1. [ ] Create ECR repository: `aws ecr create-repository --repository-name paperrag-apprunner`
2. [ ] Build and push Docker image (AMD64): `docker buildx build --platform linux/amd64 -f apprunner/Dockerfile --push .`
3. [ ] Create API key in Secrets Manager: `paperrag/api-key`
4. [ ] Create VPC Connector for RDS access
5. [ ] Create IAM roles (ECR access + instance role)
6. [ ] Create App Runner service with secrets configuration
7. [ ] Verify health: `curl https://SERVICE_URL/health`
8. [ ] Test authenticated request with API key

### AWS AgentCore (Alternative)
1. [ ] `agentcore configure -e src/mcp_http_server.py --protocol MCP`
2. [ ] Configure VPC subnets and security groups
3. [ ] `agentcore deploy --auto-update-on-conflict`

---

**Status Legend:**
- Production - Fully implemented and tested
- Complete - Implementation finished
- Pending - Planned for future release
