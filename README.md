# Paper RAG Pipeline for Research & Citation Management

A RAG (Retrieval Augmented Generation) system designed for academic research paper management. Combines advanced document processing (Docling), vector search (PostgreSQL + pgvector), AWS S3 storage, and AI assistance via MCP (Model Context Protocol) to enable intelligent citation management, contextual paper retrieval, and automated bibliography generation.

**Deployment Options:**
- **AWS App Runner** (Recommended): Simple static API key authentication, ~$5-15/month
- **AWS AgentCore**: SigV4/Cognito authentication for Bedrock integration

**Production URL**: `https://m76rjhx9i3.us-east-1.awsapprunner.com` (requires API key)

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
   # For local development
   python -m src.mcp_http_server

   # For App Runner deployment (uses PORT env var, default 8080)
   # Set PAPERRAG_API_KEY to enable authentication
   PAPERRAG_API_KEY=your-key python -m src.mcp_http_server
   ```

## Environment Variables

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
OPENAI_API_KEY=sk-your-openai-key
S3_BUCKET=paper-rag-pdfs
AWS_REGION=us-east-1

# For App Runner deployment
PAPERRAG_API_KEY=your-api-key  # Enables Bearer token authentication

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

## Connecting to Deployed Service

### Python MCP Client

```python
import os

mcp_servers = [
    {
        "type": "url",
        "url": "https://m76rjhx9i3.us-east-1.awsapprunner.com/mcp",
        "name": "paper-rag",
        "authorization_token": os.environ.get("PAPERRAG_API_KEY"),
    }
]
```

### curl (testing)

```bash
# Set your API key (from AWS Secrets Manager or .env)
export PAPERRAG_API_KEY="your-api-key"

# Test database stats
curl -X POST https://m76rjhx9i3.us-east-1.awsapprunner.com/mcp \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $PAPERRAG_API_KEY" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"database_stats","arguments":{}},"id":1}'
```

### Get API Key

```bash
aws secretsmanager get-secret-value \
    --secret-id paperrag/api-key \
    --query SecretString --output text \
    --region us-east-1
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

### Current (v2.1 - App Runner)
- PostgreSQL + pgvector vector storage
- AWS S3 PDF storage
- MCP HTTP server with API key authentication
- 10 MCP tools
- Async operations throughout
- AWS App Runner deployment (recommended)
- AWS AgentCore deployment (alternative)

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
- [AGENTS.md](AGENTS.md) - Developer and coding-agent instructions (`CLAUDE.md` only imports it). Check the agent configuration with `python -m unittest discover -s scripts -p test_sync_agent_config.py` and `python scripts/sync_agent_config.py --check`

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

**Version:** 2.1 (App Runner + API Key Auth)
**Status:** Production Ready
