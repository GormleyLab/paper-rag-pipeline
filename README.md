# Academic RAG Pipeline for Research & Citation Management

A locally-hosted, privacy-focused RAG (Retrieval Augmented Generation) system designed to transform how researchers interact with their paper libraries during grant writing and academic writing. By combining advanced document processing (Docling), vector search (LanceDB), and AI assistance (Claude via MCP), this tool enables intelligent citation management, contextual paper retrieval, and automated bibliography generation for LaTeX documents.

## Features

- **Intelligent Paper Search**: Semantic search through your PDF library using natural language queries
- **Automated Citation Management**: Extract DOI metadata and generate BibTeX entries automatically
- **Claude Desktop Integration**: Natural language interface via Model Context Protocol (MCP)
- **Local & Private**: All processing happens locally, only embeddings API calls to OpenAI
- **LaTeX Ready**: Generate publication-ready `.bib` files for your manuscripts
- **URL Linking**: Maintain links to online versions (DOI, arXiv, PubMed) for easy access

## Quick Start

### Prerequisites

- Python 3.10+
- Claude Desktop app
- OpenAI API key (for embeddings)
- Local library of research papers (PDFs)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd academic-rag-pipeline
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

4. **Update configuration**
   ```bash
   # Edit config/config.yaml with your PDF library path
   ```

5. **Initialize the database**
   ```bash
   python scripts/initial_setup.py
   ```

6. **Configure Claude Desktop**
   - Add the MCP server configuration to Claude Desktop
   - Location (macOS): `~/Library/Application Support/Claude/claude_desktop_config.json`
   - See [docs/setup.md](docs/setup.md) for detailed instructions

## Project Structure

```
academic-rag-pipeline/
├── src/                            # Source code
│   ├── mcp_server.py              # MCP server implementation
│   ├── document_processor.py      # Docling PDF processing pipeline
│   ├── metadata_extractor.py      # Citation metadata extraction
│   ├── vector_store.py            # LanceDB operations
│   ├── embeddings.py              # OpenAI embedding generation
│   ├── bibliography.py            # BibTeX management
│   └── utils.py                   # Helper functions
├── config/                        # Configuration files
│   ├── config.yaml                # Main configuration
│   └── claude_desktop_config.json # MCP server config (example)
├── data/                          # Data directory
│   ├── lancedb/                   # Vector database
│   ├── pdfs/                      # PDF library
│   └── logs/                      # Application logs
├── scripts/                       # Utility scripts
│   ├── initial_setup.py           # Initialize database
│   └── maintenance.py             # Database maintenance
├── tests/                         # Test suite
├── docs/                          # Documentation
├── .env.example                   # Environment variables template
├── requirements.txt               # Python dependencies
├── PRD.md                         # Product Requirements Document
└── README.md                      # This file
```

## Usage

### via Claude Desktop

Once configured, interact with your paper library through Claude Desktop:

**Search for papers:**
```
Find papers about machine learning in drug delivery from the last 3 years
```

**Add a paper:**
```
[Drag PDF into chat]
Add this paper to my database
```

**Generate bibliography:**
```
Generate a .bib file with Smith2024, Jones2023, Chen2022
```

**Get paper details:**
```
Show me information about the Wang2024 paper
```

### Available MCP Tools

- `search_papers` - Search the paper database
- `add_paper_from_file` - Add PDF via file path
- `add_paper_from_url` - Add paper via DOI/arXiv/URL
- `generate_bibliography` - Create .bib file
- `get_paper_details` - Retrieve paper metadata
- `verify_citation` - Review citation accuracy
- `update_bibtex` - Manually update metadata
- `import_bibtex_file` - Import existing .bib file
- `database_stats` - Get database statistics
- `list_recent_papers` - Show recently added papers

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Document Processing | Docling | Advanced PDF parsing with structure preservation |
| Vector Database | LanceDB | High-performance local vector storage |
| Embeddings | OpenAI text-embedding-3-large | Semantic search (3072 dimensions) |
| Chunking | Docling Hybrid Chunker | Semantic document chunking |
| AI Interface | Claude Desktop + MCP | Natural language interaction |
| Citation Metadata | CrossRef API | Authoritative bibliographic data |
| Bibliography Format | BibTeX | LaTeX-compatible citations |

## Development Roadmap

### Phase 1: MVP (v1.0) - Current
- Core PDF processing pipeline
- Metadata extraction (DOI, CrossRef)
- Vector search with LanceDB
- Basic MCP tools
- Claude Desktop integration

### Phase 2: Enhanced Features (v1.5)
- URL-based paper addition
- Citation verification tools
- Manual metadata overrides
- BibTeX file import

### Phase 3: Citation Graph (v2.0)
- Reference extraction
- Citation network analysis
- Foundational paper discovery
- Co-citation analysis

### Phase 4: Advanced Retrieval (v2.5)
- Section-aware retrieval
- Figure/table extraction
- Claim verification

## Documentation

- [Setup Guide](docs/setup.md) - Detailed installation instructions
- [Usage Guide](docs/usage.md) - Comprehensive usage examples
- [Troubleshooting](docs/troubleshooting.md) - Common issues and solutions
- [PRD](PRD.md) - Complete product requirements

## Privacy & Security

- All PDFs stored locally (no cloud upload)
- Vector database stored locally
- Only API calls: OpenAI embeddings, CrossRef metadata
- No paper content sent to external services
- API keys stored securely in environment variables

## Cost Estimates

**Operational Costs (per month):**
- Initial library (1000 papers): ~$15 one-time
- Ongoing queries: ~$5-10/month typical usage
- Adding papers: ~$0.01-0.02 per paper
- Total first year: ~$175-250 (API usage only)

## Contributing

This project is designed for academic researchers. Contributions, bug reports, and feature requests are welcome.

## License

[Add license information]

## Acknowledgments

Built for the Gormley Lab at Rutgers University for streamlining grant writing and literature management.

---

**Version:** 1.0
**Status:** In Development
**Author:** Adam (Associate Professor, Biomedical Engineering, Rutgers University)
