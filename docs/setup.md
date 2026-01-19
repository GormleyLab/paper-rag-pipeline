# Setup Guide - Paper RAG Pipeline

This guide walks you through setting up the Paper RAG Pipeline for AWS AgentCore deployment.

## Prerequisites

- Python 3.10 or higher
- PostgreSQL 15+ with pgvector extension
- AWS S3 bucket for PDF storage
- OpenAI API account with API key

## Step 1: Install Dependencies

```bash
cd paper-rag-pipeline
pip install -r requirements.txt
```

This installs all required packages including:
- SQLAlchemy + asyncpg (PostgreSQL)
- pgvector (vector operations)
- boto3 (AWS S3)
- Docling (PDF processing)
- OpenAI (embeddings)
- FastMCP (MCP server)

## Step 2: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your configuration:
   ```bash
   # Required
   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
   OPENAI_API_KEY=sk-your-actual-api-key-here
   S3_BUCKET=paper-rag-pdfs
   AWS_REGION=us-east-1

   # Optional but recommended
   CROSSREF_EMAIL=your.email@university.edu

   # Optional (if not using IAM role)
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   ```

## Step 3: Set Up PostgreSQL

### Install pgvector extension

```sql
-- Connect to your database
CREATE EXTENSION IF NOT EXISTS vector;
```

### For AWS RDS

1. Use PostgreSQL 15+ (pgvector is pre-installed)
2. Ensure your parameter group allows the extension
3. Run: `CREATE EXTENSION vector;`

### For Local Development

```bash
# macOS with Homebrew
brew install pgvector

# Or build from source
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make && make install
```

## Step 4: Run Database Migrations

```bash
alembic upgrade head
```

This creates:
- `paper_rag` schema
- `papers` table (paper metadata)
- `chunks` table (text chunks with embeddings)
- HNSW index for vector similarity search

## Step 5: Set Up S3 Bucket

### Create bucket (if needed)

```bash
aws s3 mb s3://paper-rag-pdfs --region us-east-1
```

### Recommended bucket policy

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:HeadObject"
            ],
            "Resource": "arn:aws:s3:::paper-rag-pdfs/*"
        }
    ]
}
```

## Step 6: Initialize Database (Optional)

If you have existing PDFs to import:

```bash
python scripts/initial_setup.py /path/to/your/pdfs
```

This will:
- Scan the directory for PDF files
- Extract text and metadata from each paper
- Generate embeddings using OpenAI API
- Upload PDFs to S3
- Store everything in PostgreSQL

**Expected time:** ~2 minutes per paper
**Expected cost:** ~$0.015 per paper for embeddings

## Step 7: Start the MCP Server

```bash
python src/mcp_http_server.py
```

The server starts on port 8000 with endpoints:
- `/mcp` - MCP protocol endpoint
- `/health` - Health check
- `/ping` - Simple ping

## Step 8: Verify Installation

1. Check health endpoint:
   ```bash
   curl http://localhost:8000/health
   ```

2. List available tools:
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
   ```

3. Test a search:
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc":"2.0",
       "method":"tools/call",
       "params":{"name":"database_stats","arguments":{}},
       "id":1
     }'
   ```

## Connecting MCP Clients

### Claude Desktop (via mcp-remote)

```json
{
  "mcpServers": {
    "paper-rag": {
      "command": "npx",
      "args": ["mcp-remote", "http://your-server:8000/mcp"]
    }
  }
}
```

### Direct HTTP

Any MCP-compatible client can connect to `http://your-server:8000/mcp`.

## Adding Papers

### Via MCP Tool (single paper)

```json
{
  "name": "add_paper_from_file",
  "arguments": {"file_path": "/path/to/paper.pdf"}
}
```

### Via Base64 Upload (for remote clients)

```json
{
  "name": "add_paper_from_upload",
  "arguments": {
    "pdf_data": "base64-encoded-pdf",
    "filename": "paper.pdf"
  }
}
```

### Batch Import

```bash
python scripts/initial_setup.py /path/to/pdf/folder
```

## Troubleshooting

### Database Connection Issues
- Verify DATABASE_URL format
- Check PostgreSQL is running
- Ensure pgvector extension is installed

### S3 Issues
- Verify credentials or IAM role
- Check bucket exists and region matches
- Verify bucket policy allows required operations

### OpenAI Issues
- Check API key is valid
- Monitor rate limits
- Reduce batch_size if hitting limits

See [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) for more details.

## Cost Management

**Embedding Costs:**
- Initial setup (1000 papers): ~$15
- Per paper: ~$0.015

**S3 Costs:**
- Storage: ~$0.023/GB/month
- Requests: minimal for typical usage

**Tips to reduce costs:**
- Process papers in batches
- Use smaller embedding model if accuracy permits
- Monitor usage in OpenAI dashboard

## Security Notes

- API keys stored in `.env` (never commit to git)
- Use IAM roles in production (not access keys)
- PDFs stored in S3 with server-side encryption
- Database should use SSL in production

## AWS AgentCore Deployment

The MCP server is compatible with AWS Bedrock AgentCore deployment.

### Prerequisites

1. Install the AgentCore toolkit:
   ```bash
   pip install bedrock-agentcore-starter-toolkit
   ```

2. Ensure you have AWS credentials configured with appropriate permissions.

3. Set up an IAM execution role for the AgentCore runtime.

### Deploy to AgentCore

1. **Configure the deployment:**
   ```bash
   agentcore configure -e src/mcp_http_server.py --protocol MCP
   ```

   During configuration, you'll be prompted for:
   - **Execution Role**: IAM role ARN with permissions for your resources
   - **ECR**: Press `enter` to auto-create
   - **Dependencies**: CLI auto-detects `requirements.txt`
   - **OAuth**: Configure if using authentication

2. **Set environment variables** for the runtime:
   - `DATABASE_URL` - PostgreSQL connection string
   - `OPENAI_API_KEY` - OpenAI API key
   - `S3_BUCKET` - S3 bucket name
   - `AWS_REGION` - AWS region

3. **Launch the deployment:**
   ```bash
   agentcore launch
   ```

   This will:
   - Build a Docker container
   - Push to Amazon ECR
   - Create the AgentCore runtime
   - Return the agent runtime ARN

### Connecting to Deployed Server

After deployment, use the ARN to connect:

```python
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

agent_arn = "arn:aws:bedrock-agentcore:us-west-2:123456789:runtime/paper-rag-xyz"
bearer_token = os.getenv('BEARER_TOKEN')

encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
mcp_url = f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

headers = {"authorization": f"Bearer {bearer_token}"}

async with streamablehttp_client(mcp_url, headers) as (read_stream, write_stream, _):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        tools = await session.list_tools()
        print(tools)
```

### Local Testing (Alternative)

For local testing with health endpoints:

```bash
# Option 1: Using uvicorn factory
uvicorn src.mcp_http_server:create_app --factory --host 0.0.0.0 --port 8000

# Option 2: Direct Python
python -c "from src.mcp_http_server import run_http_server; run_http_server()"

# Option 3: AgentCore-compatible (no health endpoints)
python src/mcp_http_server.py
```

## Next Steps

- Read [CLAUDE.md](../CLAUDE.md) for developer documentation
- Check [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) for common issues
- See the PRD for full feature documentation

---

**Happy researching!**
