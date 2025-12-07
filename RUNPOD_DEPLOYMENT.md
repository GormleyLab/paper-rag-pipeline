# RunPod Deployment Guide

Deploy the Paper RAG Pipeline as a remote MCP HTTP server on RunPod Serverless.

## Overview

This deployment provides:
- **Remote MCP access** via HTTP (Streamable HTTP transport)
- **GPU acceleration** for fast PDF processing
- **Persistent storage** via RunPod Network Volumes
- **API key authentication** for secure remote access
- **Scale-to-zero** to minimize costs when not in use

## Prerequisites

- RunPod account with funds
- Docker Hub account (or other container registry)
- OpenAI API key
- Docker installed locally (for building images)

---

## Step 1: Build and Push Docker Image

### Build the image locally

```bash
cd /path/to/paper-rag-pipeline

# Build the GPU-enabled image for AMD64 platform (required for RunPod)
# Use --platform flag when building on ARM Macs to avoid platform mismatch warnings
docker build --platform linux/amd64 -t your-dockerhub-username/paper-rag:latest .

# Test locally (optional)
docker run --rm -it \
  -e OPENAI_API_KEY=sk-your-key \
  -e MCP_API_KEY=your-secret-key \
  -p 8080:8080 \
  your-dockerhub-username/paper-rag:latest
```

### Push to Docker Hub

```bash
docker login
docker push your-dockerhub-username/paper-rag:latest
```

---

## Step 2: Create RunPod Network Volume

Network Volumes provide persistent storage that survives serverless worker scaling.

1. Go to [RunPod Console](https://www.runpod.io/console/serverless)
2. Navigate to **Storage** → **Network Volumes**
3. Click **Create Network Volume**
4. Configure:
   - **Name**: `paper-rag-data`
   - **Size**: 20 GB minimum (adjust based on expected PDF count)
   - **Region**: Choose region closest to you (must match endpoint region)
5. Click **Create**

### Volume Structure

The server will automatically create this directory structure:

```
/runpod-volume/
├── data/
│   ├── lancedb/       # Vector database (embeddings + metadata)
│   ├── pdfs/          # PDF copies (named by citation key)
│   ├── bibs/          # BibTeX files
│   └── logs/          # Application logs
└── cache/
    └── huggingface/   # Model cache
```

---

## Step 3: Create Serverless Endpoint

1. Go to [RunPod Console](https://www.runpod.io/console/serverless)
2. Click **New Endpoint**
3. Configure:

### Basic Settings

| Setting | Value |
|---------|-------|
| **Endpoint Name** | `paper-rag-mcp` |
| **Container Image** | `your-dockerhub-username/paper-rag:latest` |
| **Container Start Command** | Leave empty (uses Dockerfile CMD) |

### GPU Configuration

| Setting | Value |
|---------|-------|
| **GPU Type** | RTX 3090 (24GB) or RTX 4090 (24GB) |
| **GPU Count** | 1 |

### Scaling Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| **Min Workers** | 0 | Scale to zero when idle |
| **Max Workers** | 3 | Adjust based on expected load |
| **Idle Timeout** | 60 seconds | Time before scaling down |
| **FlashBoot** | Enabled | Faster cold starts |

### Environment Variables

Click **Add Environment Variable** for each:

| Variable | Value | Required |
|----------|-------|----------|
| `OPENAI_API_KEY` | `sk-your-openai-key` | Yes |
| `MCP_API_KEY` | `your-secret-api-key` | Yes |
| `CROSSREF_EMAIL` | `your.email@example.com` | Recommended |
| `START_HTTP_SERVER` | `true` | Yes |
| `CONFIG_PATH` | `/app/config/config-runpod.yaml` | No (default) |
| `MCP_CLIENT_ID` | `paper-rag-client` | No (defaults to `paper-rag-client`) |

> **Security Note**: Use RunPod's **Secrets** feature for sensitive values like API keys.
>
> **OAuth Note**: `MCP_CLIENT_ID` is used for OAuth 2.0 authentication with Claude Desktop's custom connector UI. If not set, it defaults to `paper-rag-client`. The `MCP_API_KEY` serves as both the OAuth client secret and the access token.

### Network Volume

1. Expand **Advanced** section
2. Under **Network Volume**, select `paper-rag-data`
3. Mount path: `/runpod-volume`

### Create Endpoint

Click **Create Endpoint** and wait for deployment.

---

## Step 4: Get Endpoint URL

After deployment:

1. Go to your endpoint dashboard
2. Find the **Endpoint ID** (e.g., `abc123xyz`)
3. Your endpoint URL will be: `https://api.runpod.ai/v2/abc123xyz`

---

## Step 5: Configure Claude Desktop

You have two options to connect Claude Desktop to your remote MCP server:

### Option 1: Custom Connector UI (Recommended)

This method uses Claude Desktop's built-in custom connector UI with OAuth 2.0 authentication.

1. **In Claude Desktop**, go to **Settings → Connectors → Add custom connector**
2. **Enter the following:**
   - **Name**: `paper-rag-remote`
   - **URL**: `https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/mcp`
   - **OAuth Client ID**: `paper-rag-client` (or your custom `MCP_CLIENT_ID` if set)
   - **OAuth Client Secret**: Your `MCP_API_KEY` value

3. **Click "Add"**

Claude Desktop will automatically handle the OAuth 2.0 flow to authenticate and connect to your server.

**Note:** If you set a custom `MCP_CLIENT_ID` environment variable in RunPod, use that value instead of `paper-rag-client`.

### Option 2: JSON Config File (Alternative)

This method uses `mcp-remote` as a bridge and requires editing the config file directly.

#### Install mcp-remote

Claude Desktop needs `mcp-remote` to connect to remote MCP servers:

```bash
npm install -g mcp-remote
```

#### Configure Claude Desktop

Edit the Claude Desktop configuration file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the following configuration:

```json
{
  "mcpServers": {
    "paper-rag-remote": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/mcp",
        "--header",
        "Authorization: Bearer YOUR_MCP_API_KEY"
      ]
    }
  }
}
```

**Replace:**
- `YOUR_ENDPOINT_ID` with your actual RunPod endpoint ID
- `YOUR_MCP_API_KEY` with the API key you set in environment variables

#### Restart Claude Desktop

Quit and reopen Claude Desktop for changes to take effect.

---

## Step 6: Test the Connection

In Claude Desktop, try these commands:

```
Show me the database statistics
```

```
Search my papers for "machine learning"
```

```
List recent papers
```

If successful, you'll see results from your remote database!

---

## Adding Papers Remotely

### Option 1: Upload Single PDF via Claude Desktop (Recommended)

Use the `add_paper_from_upload` tool to upload a PDF directly from your local machine:

```
Add this paper to my database: [attach PDF file]
```

Claude Desktop will encode the PDF as base64 and send it to the remote server. The tool accepts:
- `pdf_data`: Base64-encoded PDF content
- `filename`: Original filename
- `custom_tags`: Optional tags to categorize the paper

### Option 2: Batch Upload from Local Folder

Use the `add_papers_from_folder_upload` tool to upload multiple PDFs at once:

```
Add all PDFs from my research folder to the database
```

The client reads all PDFs from the local folder, encodes them as base64, and sends them in a single request. Parameters:
- `pdf_files`: List of objects with `filename` and `pdf_data` (base64)
- `custom_tags`: Optional tags applied to all papers

**Response includes:**
- Summary: processed/skipped/failed counts
- List of successfully added papers with BibTeX keys
- List of skipped duplicates
- List of failures with error messages
- Total embedding cost

**Example batch upload response:**
```
**Batch Upload Complete!**

**Summary:**
- Processed: 8 papers
- Skipped (duplicates): 2 papers
- Failed: 1 paper
- Total Embedding Cost: $0.1234

**Successfully Added:**
1. [Smith2024] "Machine Learning in Healthcare"
2. [Jones2023] "Deep Learning Approaches"
...
```

### Option 3: Direct API Call with Base64 Data

Upload a PDF programmatically:

```bash
# Encode PDF to base64
PDF_BASE64=$(base64 -i paper.pdf)

# Call the upload tool
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/mcp" \
  -H "Authorization: Bearer YOUR_MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "add_paper_from_upload",
      "arguments": {
        "pdf_data": "'"$PDF_BASE64"'",
        "filename": "paper.pdf",
        "custom_tags": ["research", "2024"]
      }
    },
    "id": 1
  }'
```

### Option 4: Server-Side File Path

If the PDF already exists on the RunPod volume:

```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/mcp" \
  -H "Authorization: Bearer YOUR_MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "add_paper_from_file",
      "arguments": {
        "file_path": "/runpod-volume/pdfs/incoming/paper.pdf"
      }
    },
    "id": 1
  }'
```

### Option 5: Upload to Network Volume First

1. Create a RunPod Pod with the same Network Volume attached
2. Upload PDFs via SSH/SFTP to `/runpod-volume/pdfs/incoming/`
3. Use the `add_paper_from_file` tool to process them

---

## Custom Client Integration

### Python Client Example

```python
import httpx
import base64
from pathlib import Path

class PaperRAGClient:
    def __init__(self, endpoint_id: str, api_key: str):
        self.base_url = f"https://api.runpod.ai/v2/{endpoint_id}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _call_tool(self, name: str, arguments: dict, timeout: float = 60.0):
        """Call an MCP tool."""
        response = httpx.post(
            f"{self.base_url}/mcp",
            headers=self.headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
                "id": 1
            },
            timeout=timeout
        )
        return response.json()

    def search_papers(self, query: str, n_results: int = 5):
        """Search papers using semantic search."""
        return self._call_tool("search_papers", {
            "query": query,
            "n_results": n_results,
            "output_format": "json"
        })

    def get_stats(self):
        """Get database statistics."""
        return self._call_tool("database_stats", {}, timeout=30.0)

    def upload_pdf(self, pdf_path: Path, tags: list[str] = None):
        """Upload a single PDF from local machine."""
        pdf_data = base64.b64encode(pdf_path.read_bytes()).decode('utf-8')
        return self._call_tool("add_paper_from_upload", {
            "pdf_data": pdf_data,
            "filename": pdf_path.name,
            "custom_tags": tags or []
        }, timeout=300.0)

    def upload_folder(self, folder_path: Path, tags: list[str] = None, recursive: bool = False):
        """Upload all PDFs from a local folder."""
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = []

        for pdf_path in folder_path.glob(pattern):
            pdf_data = base64.b64encode(pdf_path.read_bytes()).decode('utf-8')
            pdf_files.append({
                "filename": pdf_path.name,
                "pdf_data": pdf_data
            })

        if not pdf_files:
            return {"error": "No PDF files found in folder"}

        return self._call_tool("add_papers_from_folder_upload", {
            "pdf_files": pdf_files,
            "custom_tags": tags or []
        }, timeout=600.0)  # Longer timeout for batch


# Usage examples
client = PaperRAGClient("YOUR_ENDPOINT_ID", "YOUR_MCP_API_KEY")

# Search papers
results = client.search_papers("neural networks")
print(results)

# Upload single PDF
result = client.upload_pdf(Path("paper.pdf"), tags=["research"])
print(result)

# Upload all PDFs from a folder
result = client.upload_folder(Path("./papers"), tags=["batch-2024"])
print(result)
```

---

## Monitoring & Troubleshooting

### Check Endpoint Logs

1. Go to RunPod Console → Serverless → Your Endpoint
2. Click **Logs** tab
3. View real-time logs from workers

### Common Issues

#### Cold Start Timeout
**Symptom**: First request times out
**Solution**:
- Enable FlashBoot
- Set `Min Workers: 1` for always-on (increases cost)
- Increase client timeout to 60+ seconds

#### Authentication Failed
**Symptom**: 401 Unauthorized errors
**Solution**:
- Verify `MCP_API_KEY` environment variable is set
- Check Bearer token format in client

#### Database Not Persisting
**Symptom**: Data disappears after scaling
**Solution**:
- Verify Network Volume is attached
- Check mount path is `/runpod-volume`
- Verify config uses `/runpod-volume/data/` paths

#### Out of Memory
**Symptom**: Workers crash during PDF processing
**Solution**:
- Use a GPU with more VRAM (RTX 4090)
- Process smaller PDFs
- Increase worker memory allocation

### Health Check

Test the server is running:

```bash
curl "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/health" \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY"
```

---

## Cost Optimization

### Estimated Costs

| Usage Pattern | Monthly Cost |
|---------------|--------------|
| Occasional (10 req/day) | $5-10 |
| Moderate (100 req/day) | $20-40 |
| With 1 active worker | +$200-350 |

### Tips to Reduce Costs

1. **Scale to zero**: Set `Min Workers: 0`
2. **Use RTX 3090**: Cheaper than RTX 4090, sufficient for most PDFs
3. **Batch operations**: Add multiple papers in one session
4. **Cache models**: Pre-cached in Docker image (already done)

---

## Security Best Practices

1. **Rotate API keys** periodically
2. **Use RunPod Secrets** for sensitive environment variables
3. **Monitor usage** for unexpected activity
4. **Restrict network access** if possible (VPN, IP allowlist)

---

## Updating the Deployment

### Update Docker Image

```bash
# Build new version (use --platform for ARM Macs)
docker build --platform linux/amd64 -t your-dockerhub-username/paper-rag:v2 .
docker push your-dockerhub-username/paper-rag:v2

# Update endpoint in RunPod Console
# Change image to: your-dockerhub-username/paper-rag:v2
```

### Update Configuration

1. Modify `config/config-runpod.yaml`
2. Rebuild and push Docker image
3. Restart workers in RunPod Console

---

## Support

- **RunPod Documentation**: https://docs.runpod.io
- **MCP Protocol Spec**: https://modelcontextprotocol.io
- **Project Issues**: Check `data/logs/` on the Network Volume

---

## Quick Reference

| Item | Value |
|------|-------|
| **Docker Image** | `your-dockerhub-username/paper-rag:latest` |
| **Endpoint URL** | `https://api.runpod.ai/v2/ENDPOINT_ID` |
| **MCP Endpoint** | `https://api.runpod.ai/v2/ENDPOINT_ID/mcp` |
| **Health Check** | `https://api.runpod.ai/v2/ENDPOINT_ID/health` |
| **Config File** | `/app/config/config-runpod.yaml` |
| **Data Path** | `/runpod-volume/data/` |
| **GPU** | RTX 3090 or RTX 4090 |
