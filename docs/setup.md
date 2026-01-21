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

### For AWS RDS (Private Subnet)

If your RDS instance is in a **private subnet** (recommended for security), you cannot connect directly from your local machine. You'll need to set up a bastion host for local development. See [Bastion Host Setup](#bastion-host-setup-for-local-development) below.

If your RDS is in a public subnet (not recommended), you can connect directly:

1. **Connect to your RDS instance** using `psql`:
   ```bash
   psql -h YOUR_RDS_ENDPOINT -U YOUR_USERNAME -d postgres
   ```

2. **Enable the pgvector extension**:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

3. **Create the schema and database**:
   ```sql
   CREATE DATABASE paper_rag;
   \c paper_rag
   CREATE SCHEMA IF NOT EXISTS paper_rag;
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

4. Type `\q` to exit psql.

**Important - pgvector Dimension Limit**: AWS RDS pgvector (v0.7.x) limits HNSW/IVFFlat indexes to **2000 dimensions**. This project uses **1536 dimensions** (text-embedding-3-large with reduced dimensions) to stay under this limit while maintaining high embedding quality.

### For Local Development

1. **Install PostgreSQL and pgvector**:
   ```bash
   # macOS with Homebrew
   brew install postgresql@15 pgvector

   # Start PostgreSQL
   brew services start postgresql@15
   ```

2. **Connect to PostgreSQL**:
   ```bash
   psql -U postgres
   ```

3. **Create database and enable extension**:
   ```sql
   CREATE DATABASE paper_rag;
   \c paper_rag
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

4. Type `\q` to exit psql.

### Bastion Host Setup (for Local Development with Private RDS)

If your RDS is in a private subnet, you need an EC2 bastion host to create an SSH tunnel for local development.

#### 1. Create EC2 Key Pair
1. EC2 Console → Key Pairs → Create key pair
2. Name: `your-bastion-key`, Type: RSA, Format: `.pem`
3. Move to SSH directory: `mv ~/Downloads/your-bastion-key.pem ~/.ssh/ && chmod 400 ~/.ssh/your-bastion-key.pem`

#### 2. Create Bastion Security Group
1. EC2 Console → Security Groups → Create
2. Name: `bastion-sg`, VPC: your VPC
3. Inbound: SSH (22) from My IP

#### 3. Update RDS Security Group
1. Find your RDS security group
2. Add inbound rule: PostgreSQL (5432) from `bastion-sg`

#### 4. Launch Bastion Instance
1. EC2 Console → Launch instance
2. AMI: Amazon Linux 2023, Type: t2.micro
3. Key pair: `your-bastion-key`
4. Network: Your VPC, **public subnet**, auto-assign public IP: Yes
5. Security group: `bastion-sg`

#### 5. Create SSH Tunnel
```bash
# Basic tunnel (may drop on idle)
ssh -i ~/.ssh/your-bastion-key.pem \
    -L 15432:YOUR_RDS_ENDPOINT:5432 \
    ec2-user@BASTION_PUBLIC_IP -N -f

# Recommended: with keepalive (prevents idle disconnection)
ssh -i ~/.ssh/your-bastion-key.pem \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    -L 15432:YOUR_RDS_ENDPOINT:5432 \
    ec2-user@BASTION_PUBLIC_IP -N -f
```

**Note**: Using port 15432 avoids conflicts with local PostgreSQL on 5432.

#### 6. Configure .env for Local Development
```bash
# For local development (via SSH tunnel)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:15432/paper_rag

# For AWS deployment (direct RDS access from within VPC)
# DATABASE_URL=postgresql+asyncpg://user:password@YOUR_RDS_ENDPOINT:5432/paper_rag
```

See [bastion-cleanup.md](bastion-cleanup.md) for cleanup instructions when done.

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

**Expected time:** ~30-60 seconds per paper (varies by PDF complexity)
**Expected cost:** ~$0.015 per paper for embeddings

### Long-Running Imports

For large PDF collections, the import can take hours. To prevent issues:

```bash
# macOS: Prevent sleep during import
caffeinate -i python scripts/initial_setup.py /path/to/your/pdfs
```

**The script is resumable**: If interrupted, re-run the same command. Already-processed papers are detected by PDF hash and skipped automatically.

**Problematic PDFs**: Some PDFs may cause the metadata extraction to hang. The system has a 60-second timeout and will fall back to alternative extraction methods.

## Step 7: Start the MCP Server

```bash
python -m src.mcp_http_server
```

**Note:** Run this from the project root directory. The `-m` flag runs the server as a module, which is required for Python to resolve the internal imports correctly.

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
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
   ```

3. Test a search:
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{
       "jsonrpc":"2.0",
       "method":"tools/call",
       "params":{"name":"database_stats","arguments":{}},
       "id":1
     }'
   ```

## Connecting MCP Clients

### Important: Network Architecture Considerations

The MCP server needs network access to both RDS and S3. Where you run the server determines how clients can connect:

| Server Location | RDS Access | Client Access |
|-----------------|------------|---------------|
| **Local (with SSH tunnel)** | Via tunnel to private RDS | localhost:8000 only |
| **AWS (EC2/ECS/AgentCore)** | Direct to private RDS | Public endpoint possible |

**For local development**: Run the MCP server locally with an SSH tunnel to RDS. Only local clients (curl, local scripts) can connect to `localhost:8000`.

**For external access (Claude Desktop, remote clients)**: Deploy the MCP server to AWS where it can access RDS directly. See [AWS AgentCore Deployment](#aws-agentcore-deployment).

### Claude Desktop (requires deployed server)

Claude Desktop cannot connect to a local MCP server that uses a private RDS. You must deploy the server to AWS first, then configure:

```json
{
  "mcpServers": {
    "paper-rag": {
      "command": "npx",
      "args": ["mcp-remote", "https://your-deployed-server/mcp"]
    }
  }
}
```

### Local Development (localhost only)

For local testing with the SSH tunnel active:

```bash
# Test from command line
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

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

### SSH Tunnel Issues

**Connection refused on localhost:15432:**
- Check if tunnel is running: `ps aux | grep ssh | grep 15432`
- Restart the tunnel (see [Bastion Host Setup](#bastion-host-setup-for-local-development))

**Tunnel drops after idle period:**
- Use `ServerAliveInterval=60` option (see tunnel command above)
- For overnight runs, use `caffeinate -i` (macOS) to prevent sleep

**Wrong DATABASE_URL:**
- Local development: use `localhost:15432` (via tunnel)
- AWS deployment: use direct RDS endpoint

### S3 Issues
- Verify credentials or IAM role
- Check bucket exists and region matches
- Verify bucket policy allows required operations

### OpenAI Issues
- Check API key is valid
- Monitor rate limits
- Reduce batch_size if hitting limits

### PDF Processing Hangs
The `pdf2bib` library can hang on certain PDFs when fetching metadata. The system has a 60-second timeout and will fall back to other extraction methods automatically.

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
python -m src.mcp_http_server
```

## Next Steps

- Read [CLAUDE.md](../CLAUDE.md) for developer documentation
- Check [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) for common issues
- See the PRD for full feature documentation

---

**Happy researching!**
