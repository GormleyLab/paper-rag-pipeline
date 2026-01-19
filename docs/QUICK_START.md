# Quick Start Guide

Get up and running with the Paper RAG Pipeline in 10 minutes.

## Prerequisites

- Python 3.10+
- PostgreSQL with pgvector extension
- AWS S3 bucket (or localstack for local development)
- OpenAI API key

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Set Up Environment

```bash
# Copy example file
cp .env.example .env

# Edit .env with your configuration:
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/paper_rag
# OPENAI_API_KEY=sk-your-key-here
# S3_BUCKET=paper-rag-pdfs
# AWS_REGION=us-east-1
# CROSSREF_EMAIL=your.email@edu (optional but recommended)
```

## 3. Run Database Migrations

```bash
alembic upgrade head
```

This creates the `paper_rag` schema with `papers` and `chunks` tables.

## 4. Initialize Database (Optional)

If you have existing PDFs to import:

```bash
python scripts/initial_setup.py /path/to/your/pdfs
```

Expected: ~2 minutes per paper, ~$0.015 per paper for embeddings.

## 5. Start the MCP Server

**For local development (with health endpoints):**
```bash
uvicorn src.mcp_http_server:create_app --factory --host 0.0.0.0 --port 8000
```

**For AWS AgentCore compatible mode:**
```bash
python src/mcp_http_server.py
```

The server starts on port 8000 at `/mcp` endpoint.

## 6. Test the Server

```bash
# Health check (only available with uvicorn method above)
curl http://localhost:8000/health
# Returns: {"status": "ok", "service": "paper-rag"}

# List MCP tools (works with both methods)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

## Using the MCP Tools

### Via MCP Client

Connect any MCP-compatible client to `http://localhost:8000/mcp`.

### Via curl (for testing)

```bash
# List tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Get database stats
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{"name":"database_stats","arguments":{}},
    "id":1
  }'

# Search papers
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{
      "name":"search_papers",
      "arguments":{"query":"machine learning","n_results":5}
    },
    "id":1
  }'
```

## Common Commands

### Search for papers
```json
{"name": "search_papers", "arguments": {"query": "neural networks", "n_results": 5}}
```

### Add a paper from file
```json
{"name": "add_paper_from_file", "arguments": {"file_path": "/path/to/paper.pdf"}}
```

### Add a paper from base64 data
```json
{"name": "add_paper_from_upload", "arguments": {"pdf_data": "base64...", "filename": "paper.pdf"}}
```

### Generate bibliography
```json
{"name": "generate_bibliography", "arguments": {"bibtex_keys": ["Smith2024", "Jones2023"]}}
```

### Get paper details
```json
{"name": "get_paper_details", "arguments": {"bibtex_key": "Smith2024"}}
```

### Database stats
```json
{"name": "database_stats", "arguments": {}}
```

## Troubleshooting

**Database connection failed?**
- Check DATABASE_URL in .env
- Verify PostgreSQL is running
- Ensure pgvector extension is installed: `CREATE EXTENSION vector;`

**S3 upload failed?**
- Check AWS credentials (or use IAM role)
- Verify S3_BUCKET exists
- Check AWS_REGION is correct

**OpenAI API Key Not Found?**
- Check OPENAI_API_KEY is set in .env

**Papers not processing?**
- Check logs in stdout
- Verify PDFs are not encrypted
- Ensure PDF paths are correct

## Next Steps

- Read [docs/setup.md](docs/setup.md) for detailed setup
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
- See [CLAUDE.md](CLAUDE.md) for developer documentation

---

**Need help?** Check the server logs for error messages.
