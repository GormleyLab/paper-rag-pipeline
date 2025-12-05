# RunPod Deployment Guide

Deploy the Academic RAG Pipeline as a remote MCP HTTP server on RunPod Serverless.

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
cd /path/to/academic-rag-pipeline

# Build the GPU-enabled image
docker build -t your-dockerhub-username/academic-rag:latest .

# Test locally (optional)
docker run --rm -it \
  -e OPENAI_API_KEY=sk-your-key \
  -e MCP_API_KEY=your-secret-key \
  -p 8080:8080 \
  your-dockerhub-username/academic-rag:latest
```

### Push to Docker Hub

```bash
docker login
docker push your-dockerhub-username/academic-rag:latest
```

---

## Step 2: Create RunPod Network Volume

Network Volumes provide persistent storage that survives serverless worker scaling.

1. Go to [RunPod Console](https://www.runpod.io/console/serverless)
2. Navigate to **Storage** → **Network Volumes**
3. Click **Create Network Volume**
4. Configure:
   - **Name**: `academic-rag-data`
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
| **Endpoint Name** | `academic-rag-mcp` |
| **Container Image** | `your-dockerhub-username/academic-rag:latest` |
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

> **Security Note**: Use RunPod's **Secrets** feature for sensitive values like API keys.

### Network Volume

1. Expand **Advanced** section
2. Under **Network Volume**, select `academic-rag-data`
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

### Install mcp-remote

Claude Desktop needs `mcp-remote` to connect to remote MCP servers:

```bash
npm install -g mcp-remote
```

### Configure Claude Desktop

Edit the Claude Desktop configuration file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the following configuration:

```json
{
  "mcpServers": {
    "academic-rag-remote": {
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

### Restart Claude Desktop

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

### Option 1: Via Claude Desktop

1. Upload a PDF file to a cloud storage (e.g., Google Drive, Dropbox)
2. Get a direct download URL
3. Download the PDF to the RunPod volume using the API

### Option 2: Direct API Call

Use the RunPod API to add papers:

```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run" \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "mode": "tool_call",
      "tool": "add_paper_from_file",
      "arguments": {
        "file_path": "/runpod-volume/pdfs/incoming/paper.pdf"
      }
    }
  }'
```

### Option 3: Upload to Network Volume

1. Create a RunPod Pod with the same Network Volume attached
2. Upload PDFs via SSH/SFTP
3. Use the MCP server to add them to the database

---

## Custom Client Integration

### Python Client Example

```python
import httpx

class AcademicRAGClient:
    def __init__(self, endpoint_id: str, api_key: str):
        self.base_url = f"https://api.runpod.ai/v2/{endpoint_id}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def search_papers(self, query: str, n_results: int = 5):
        """Search papers using semantic search."""
        response = httpx.post(
            f"{self.base_url}/mcp",
            headers=self.headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "search_papers",
                    "arguments": {
                        "query": query,
                        "n_results": n_results,
                        "output_format": "json"
                    }
                },
                "id": 1
            },
            timeout=60.0
        )
        return response.json()

    def get_stats(self):
        """Get database statistics."""
        response = httpx.post(
            f"{self.base_url}/mcp",
            headers=self.headers,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "database_stats",
                    "arguments": {}
                },
                "id": 1
            },
            timeout=30.0
        )
        return response.json()


# Usage
client = AcademicRAGClient("YOUR_ENDPOINT_ID", "YOUR_MCP_API_KEY")
results = client.search_papers("neural networks")
print(results)
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
# Build new version
docker build -t your-dockerhub-username/academic-rag:v2 .
docker push your-dockerhub-username/academic-rag:v2

# Update endpoint in RunPod Console
# Change image to: your-dockerhub-username/academic-rag:v2
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
| **Docker Image** | `your-dockerhub-username/academic-rag:latest` |
| **Endpoint URL** | `https://api.runpod.ai/v2/ENDPOINT_ID` |
| **MCP Endpoint** | `https://api.runpod.ai/v2/ENDPOINT_ID/mcp` |
| **Health Check** | `https://api.runpod.ai/v2/ENDPOINT_ID/health` |
| **Config File** | `/app/config/config-runpod.yaml` |
| **Data Path** | `/runpod-volume/data/` |
| **GPU** | RTX 3090 or RTX 4090 |
