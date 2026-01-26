# Quick Start Guide

Get up and running with the Paper RAG Pipeline.

## Prerequisites

- Python 3.10+
- PostgreSQL 15+ with pgvector extension
- AWS S3 bucket
- OpenAI API key

**If using AWS RDS in a private subnet**: You'll need a bastion host for local development. See [setup.md](setup.md#bastion-host-setup-for-local-development) for detailed instructions.

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Set Up Environment

```bash
# Copy example file
cp .env.example .env

# Edit .env with your configuration
```

**For local development with RDS via SSH tunnel:**
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:15432/paper_rag
```

**For AWS deployment (direct RDS access):**
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@your-rds-endpoint:5432/paper_rag
```

**Other required variables:**
```bash
OPENAI_API_KEY=sk-your-key-here
S3_BUCKET=paper-rag-pdfs
AWS_REGION=us-east-1
CROSSREF_EMAIL=your.email@edu  # optional but recommended
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

# For long imports (prevents Mac sleep):
caffeinate -i python scripts/initial_setup.py /path/to/your/pdfs
```

- **Time:** ~30-60 seconds per paper
- **Cost:** ~$0.015 per paper for embeddings
- **Resumable:** Re-run the same command if interrupted; already-processed papers are skipped

## 5. Start the MCP Server

**For local development:**
```bash
python -m src.mcp_http_server
```

**For local development with API key authentication:**
```bash
PAPERRAG_API_KEY=test-key python -m src.mcp_http_server
```

The server starts on port 8080 (configurable via PORT env var) at `/mcp` endpoint.

**For AWS App Runner deployment:** See [setup.md](setup.md#aws-app-runner-deployment-recommended).

## 6. Test the Server

```bash
# Health check (no auth required)
curl http://localhost:8080/health
# Returns: {"status": "ok", "service": "paper-rag"}

# List MCP tools (no auth if PAPERRAG_API_KEY not set)
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# With API key authentication enabled
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

## Using the MCP Tools

### Network Access Note

**Local development:** The MCP server runs on `localhost:8080` and is only accessible locally. This is sufficient for testing via curl.

**External clients (Claude Desktop, etc.):** Connect to the deployed App Runner service.

### Connect to Deployed Service (App Runner)

**Production URL**: `https://m76rjhx9i3.us-east-1.awsapprunner.com`

```bash
# Get your API key (save to .env as PAPERRAG_API_KEY)
aws secretsmanager get-secret-value --secret-id paperrag/api-key --query SecretString --output text --region us-east-1

# Test the deployed service
curl -X POST https://m76rjhx9i3.us-east-1.awsapprunner.com/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $PAPERRAG_API_KEY" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"database_stats","arguments":{}},"id":1}'
```

Python MCP client configuration:
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

### Via curl (for testing)

```bash
# List tools
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'

# Get database stats
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{"name":"database_stats","arguments":{}},
    "id":1
  }'

# Search papers
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
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

**SSH tunnel connection refused (localhost:15432)?**
- Check if tunnel is running: `ps aux | grep ssh | grep 15432`
- Restart tunnel with keepalive: see [setup.md](setup.md#bastion-host-setup-for-local-development)
- Make sure bastion EC2 instance is running

**Tunnel drops overnight?**
- Use `ServerAliveInterval=60` option in SSH command
- Use `caffeinate -i` to prevent Mac sleep

**S3 upload failed?**
- Check AWS credentials (or use IAM role)
- Verify S3_BUCKET exists
- Check AWS_REGION is correct

**OpenAI API Key Not Found?**
- Check OPENAI_API_KEY is set in .env

**Papers not processing / script hangs?**
- Some PDFs cause metadata extraction to hang
- System has 60-second timeout and falls back to alternative methods
- Re-run the script; it will skip already-processed papers

## Next Steps

- Read [docs/setup.md](docs/setup.md) for detailed setup
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
- See [CLAUDE.md](CLAUDE.md) for developer documentation

---

**Need help?** Check the server logs for error messages.
