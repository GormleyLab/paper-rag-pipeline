# Paper RAG Pipeline for Research & Citation Management

A RAG (Retrieval Augmented Generation) system designed for academic research paper management, built for AWS AgentCore deployment. Combines advanced document processing (Docling), vector search (PostgreSQL + pgvector), AWS S3 storage, and AI assistance via MCP (Model Context Protocol) to enable intelligent citation management, contextual paper retrieval, and automated bibliography generation.

## Features

- **Intelligent Paper Search**: Semantic search through your PDF library using natural language queries
- **Automated Citation Management**: Extract DOI metadata and generate BibTeX entries automatically
- **MCP Protocol Support**: Standard MCP over HTTP for integration with any MCP-compatible client
- **Scalable Architecture**: PostgreSQL + pgvector for vector storage, S3 for PDF storage
- **LaTeX Ready**: Generate publication-ready `.bib` files for your manuscripts
- **URL Linking**: Maintain links to online versions (DOI, arXiv, PubMed) for easy access

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL with pgvector extension
- AWS S3 bucket
- OpenAI API key (for embeddings)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd paper-rag-pipeline
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration (see Environment Variables below)
   ```

4. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

5. **Initialize the database (optional - for batch import)**
   ```bash
   python scripts/initial_setup.py /path/to/your/pdfs
   ```

6. **Start the MCP HTTP server**
   ```bash
   # For local development (with health endpoints)
   uvicorn src.mcp_http_server:create_app --factory --host 0.0.0.0 --port 8000

   # For AWS AgentCore deployment
   python src/mcp_http_server.py
   ```

## Environment Variables

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
OPENAI_API_KEY=sk-your-openai-key
S3_BUCKET=paper-rag-pdfs
AWS_REGION=us-east-1

# Optional
CROSSREF_EMAIL=your.email@university.edu
AWS_ACCESS_KEY_ID=...      # If not using IAM role
AWS_SECRET_ACCESS_KEY=...  # If not using IAM role
```

## Project Structure

```
paper-rag-pipeline/
├── src/
│   ├── core/                      # Database & settings
│   ├── models/                    # SQLAlchemy models
│   ├── services/                  # S3 service
│   ├── mcp_http_server.py         # MCP HTTP server (main entry)
│   ├── pg_vector_store.py         # PostgreSQL vector operations
│   ├── document_processor.py      # Docling PDF processing
│   ├── metadata_extractor.py      # Citation metadata extraction
│   ├── embeddings.py              # OpenAI embedding generation
│   ├── bibliography.py            # BibTeX management
│   └── utils.py                   # Helper functions
├── alembic/                       # Database migrations
├── config/                        # Configuration files
├── scripts/                       # Utility scripts
├── docs/                          # Documentation
└── requirements.txt               # Python dependencies
```

## Usage

### MCP Tools Available

The server exposes 10 MCP tools:

**Core Tools:**
- `search_papers` - Semantic search with filters (section, year)
- `add_paper_from_file` - Add PDF from local file path
- `generate_bibliography` - Create .bib file from paper keys
- `get_paper_details` - Retrieve paper metadata
- `database_stats` - Database statistics
- `list_recent_papers` - Show recent additions
- `delete_paper` - Remove paper from database

**Upload Tools:**
- `add_paper_from_upload` - Add paper from base64-encoded PDF
- `add_papers_from_folder_upload` - Batch upload multiple PDFs

**PDF Retrieval:**
- `get_paper_pdf` - Download PDF as base64

### Example Queries

**Search for papers:**
```
Find papers about machine learning in drug delivery from the last 3 years
```

**Add a paper:**
```
Add this paper to my database [with base64 PDF data]
```

**Generate bibliography:**
```
Generate a .bib file with Smith2024, Jones2023, Chen2022
```

**Get paper details:**
```
Show me information about the Wang2024 paper
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Document Processing | Docling | Advanced PDF parsing with structure preservation |
| Vector Database | PostgreSQL + pgvector | Scalable vector storage with HNSW indexing |
| PDF Storage | AWS S3 | Scalable object storage |
| Embeddings | OpenAI text-embedding-3-large | Semantic search (3072 dimensions) |
| Chunking | Docling Hybrid Chunker | Semantic document chunking |
| AI Interface | MCP over HTTP | Standard protocol for tool access |
| Citation Metadata | CrossRef API | Authoritative bibliographic data |
| Bibliography Format | BibTeX | LaTeX-compatible citations |

## Development Roadmap

### Current (AWS AgentCore)
- PostgreSQL + pgvector vector storage
- AWS S3 PDF storage
- MCP HTTP server
- 10 MCP tools
- Async operations throughout

### Phase 2: Enhanced Features
- URL-based paper addition
- Citation verification tools
- Manual metadata overrides
- BibTeX file import

### Phase 3: Citation Graph
- Reference extraction
- Citation network analysis
- Foundational paper discovery

## Documentation

- [Setup Guide](docs/setup.md) - Detailed installation instructions
- [Quick Start](QUICK_START.md) - Get running quickly
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [CLAUDE.md](CLAUDE.md) - Developer documentation

## Cost Estimates

**Operational Costs:**
- Initial library (1000 papers): ~$15 one-time (embeddings)
- Ongoing queries: ~$5-10/month typical usage
- Adding papers: ~$0.01-0.02 per paper
- S3 storage: ~$0.023/GB/month

## Contributing

This project is designed for academic researchers. Contributions, bug reports, and feature requests are welcome.

## License

[Add license information]

## Acknowledgments

Built for the Gormley Lab at Rutgers University for streamlining grant writing and literature management.

---

**Version:** 2.0 (AWS AgentCore)
**Status:** Production Ready
