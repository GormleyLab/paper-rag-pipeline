# Paper RAG Web Interface - Implementation Plan

This document outlines the plan for building a custom web interface for the Paper RAG Pipeline.
**Use this as reference when building the site in a separate repository.**

---

## Claude Code Prompt

Use this prompt to start building the web interface in a new repository:

```
Create a FastAPI web application called "paper-rag-web" that provides a web interface for managing academic papers stored on a remote RunPod MCP server.

Use the WEB_INTERFACE_PLAN.md file in this repository as the complete specification. It contains:
- Project structure
- Complete RunPod client implementation with MCP response parsing
- Authentication implementation
- All API endpoints
- UI page descriptions
- Environment variables
- Render deployment configuration
- Complete MCP tool signatures and response formats

Key requirements:
1. Use FastAPI with Jinja2 templates
2. Simple password authentication with secure session cookies
3. All paper operations go through the RunPodClient class which calls the MCP server
4. Use HTMX for interactive updates without full page reloads
5. Tailwind CSS for styling (via CDN is fine)
6. Mobile responsive design

Start by:
1. Creating the project structure
2. Implementing the RunPodClient from the plan
3. Setting up FastAPI with authentication
4. Building the home page with search
5. Adding upload functionality

The RunPod endpoint is already deployed and accepts Bearer token authentication at /mcp.
```

---

## Overview

### Why a Web Interface?
RunPod load-balanced endpoints require authentication at the proxy level, which blocks Claude Desktop's OAuth discovery flow. A custom web interface solves this by:
1. Handling user authentication separately (simple password)
2. Making authenticated requests to RunPod from the backend
3. Providing a user-friendly interface for all operations

### Architecture
```
User Browser → Web App (Railway/Render) → RunPod API (authenticated)
                    ↓
              Paper RAG MCP Server on RunPod
```

---

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: Jinja2 templates + HTMX (or simple HTML/JS)
- **Styling**: Tailwind CSS or Bootstrap
- **Authentication**: Simple password protection
- **Deployment**: Render

---

## Core Features

1. **PDF Upload** - Drag-and-drop or file picker to upload PDFs
2. **Batch Upload** - Upload multiple PDFs from a folder
3. **Search** - Semantic search across paper database
4. **Browse Papers** - List all papers with metadata
5. **Paper Details** - View full metadata, BibTeX entry
6. **Bibliography Export** - Generate .bib files from selected papers
7. **Delete Papers** - Remove papers from database
8. **Database Stats** - View paper count, year distribution

---

## API Endpoints (FastAPI)

### Authentication
```python
# Simple password auth using session cookies
POST /login          # Verify password, set session
GET  /logout         # Clear session
```

### Paper Operations
```python
GET  /api/search?q={query}&n={limit}    # Search papers
POST /api/upload                         # Upload single PDF (multipart)
POST /api/upload-batch                   # Upload multiple PDFs
GET  /api/papers                         # List recent papers
GET  /api/papers/{bibtex_key}           # Get paper details
DELETE /api/papers/{bibtex_key}         # Delete paper
GET  /api/stats                         # Database statistics
POST /api/bibliography                   # Generate .bib file
```

---

## Project Structure

```
paper-rag-web/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings from environment
│   ├── auth.py              # Password authentication
│   ├── runpod_client.py     # RunPod API client
│   └── routes/
│       ├── __init__.py
│       ├── pages.py         # HTML page routes
│       └── api.py           # JSON API routes
├── templates/
│   ├── base.html            # Base template with nav
│   ├── login.html           # Login page
│   ├── index.html           # Home/search page
│   ├── papers.html          # Paper list
│   ├── paper_detail.html    # Single paper view
│   ├── upload.html          # Upload page
│   └── components/
│       ├── search_bar.html
│       ├── paper_card.html
│       └── stats_widget.html
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
│       └── upload.js        # File upload handling
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## RunPod Client Implementation

```python
# app/runpod_client.py
import httpx
import base64
import json
from typing import Any

class MCPError(Exception):
    """Error from MCP server."""
    pass

class RunPodClient:
    def __init__(self, api_key: str, endpoint_url: str):
        self.api_key = api_key
        self.endpoint_url = endpoint_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _parse_response(self, response_json: dict) -> str:
        """
        Parse MCP JSON-RPC response and extract text content.

        MCP responses have this structure:
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {"type": "text", "text": "actual result here"}
                ]
            }
        }
        """
        if "error" in response_json:
            error = response_json["error"]
            raise MCPError(f"MCP Error {error.get('code', 'unknown')}: {error.get('message', 'Unknown error')}")

        result = response_json.get("result", {})
        content = result.get("content", [])

        if not content:
            return ""

        # Extract text from first content block
        first_block = content[0]
        if first_block.get("type") == "text":
            return first_block.get("text", "")

        return str(first_block)

    async def _call_tool(self, tool_name: str, arguments: dict, timeout: float = 120.0) -> str:
        """Call an MCP tool on the RunPod server."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.endpoint_url}/mcp",
                    headers=self.headers,
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": arguments},
                        "id": 1
                    },
                    timeout=timeout
                )
                response.raise_for_status()
                return self._parse_response(response.json())
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise MCPError("Authentication failed - check MCP_API_KEY")
                raise MCPError(f"HTTP error {e.response.status_code}: {e.response.text}")
            except httpx.TimeoutException:
                raise MCPError(f"Request timed out after {timeout}s")

    async def search_papers(
        self,
        query: str,
        n_results: int = 10,
        filter_section: str = None,  # Methods, Results, Discussion, Introduction
        min_year: int = None
    ) -> dict:
        """Search papers. Returns parsed JSON when output_format='json'."""
        args = {
            "query": query,
            "n_results": n_results,
            "output_format": "json"
        }
        if filter_section:
            args["filter_section"] = filter_section
        if min_year:
            args["min_year"] = min_year

        result = await self._call_tool("search_papers", args)
        return json.loads(result)  # Parse JSON response

    async def upload_pdf(self, file_bytes: bytes, filename: str, tags: list = None) -> str:
        """Upload a single PDF. Returns status message."""
        pdf_data = base64.b64encode(file_bytes).decode('utf-8')
        return await self._call_tool("add_paper_from_upload", {
            "pdf_data": pdf_data,
            "filename": filename,
            "custom_tags": tags or []
        }, timeout=300.0)

    async def upload_batch(self, files: list[tuple[str, bytes]], tags: list = None) -> str:
        """Upload multiple PDFs. Returns summary with success/failure counts."""
        pdf_files = [
            {"filename": name, "pdf_data": base64.b64encode(data).decode('utf-8')}
            for name, data in files
        ]
        return await self._call_tool("add_papers_from_folder_upload", {
            "pdf_files": pdf_files,
            "custom_tags": tags or []
        }, timeout=600.0)

    async def get_paper(self, bibtex_key: str) -> str:
        """Get paper details. Returns formatted text with metadata and BibTeX."""
        return await self._call_tool("get_paper_details", {
            "bibtex_key": bibtex_key
        })

    async def list_papers(self, n: int = 20) -> str:
        """List recent papers. Returns formatted text list."""
        return await self._call_tool("list_recent_papers", {"n": n})

    async def delete_paper(self, bibtex_key: str) -> str:
        """Delete a paper. Returns status message."""
        return await self._call_tool("delete_paper", {
            "bibtex_key": bibtex_key,
            "delete_files": True
        })

    async def get_stats(self) -> str:
        """Get database statistics. Returns formatted text."""
        return await self._call_tool("database_stats", {})

    async def generate_bibliography(self, keys: list[str]) -> str:
        """
        Generate bibliography for given keys.

        NOTE: This writes to server filesystem. For web download,
        you may need to fetch individual paper BibTeX entries instead
        using get_paper() and combine them client-side.
        """
        return await self._call_tool("generate_bibliography", {
            "bibtex_keys": keys,
            "output_path": "/tmp/references.bib"  # Server-side path
        })
```

---

## Authentication (Simple Password)

```python
# app/auth.py
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
import hashlib
import os

# Password hash stored in environment
PASSWORD_HASH = os.environ.get("APP_PASSWORD_HASH", "")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str) -> bool:
    return hash_password(password) == PASSWORD_HASH

async def require_auth(request: Request):
    """Dependency to require authentication."""
    session_token = request.cookies.get("session")
    if not session_token or session_token != PASSWORD_HASH:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True
```

---

## Environment Variables

```bash
# RunPod Configuration
MCP_API_KEY=your-mcp-api-key              # Same key configured on RunPod endpoint
RUNPOD_ENDPOINT_URL=https://9f6jgnmmeatk98.api.runpod.ai

# App Authentication
APP_PASSWORD_HASH=sha256-hash-of-your-password
APP_SECRET_KEY=random-secret-for-sessions  # Required for secure session cookies

# Optional
DEBUG=false
```

To generate password hash:
```python
import hashlib
print(hashlib.sha256("your-password".encode()).hexdigest())
```

To generate secret key:
```python
import secrets
print(secrets.token_hex(32))
```

---

## UI Pages

### 1. Login Page (`/login`)
- Simple password input
- "Remember me" option
- Redirect to home on success

### 2. Home/Search Page (`/`)
- Search bar at top
- Recent papers below
- Database stats sidebar

### 3. Search Results (`/search?q=...`)
- Query display
- Result cards with title, authors, year, excerpt
- Click to view details

### 4. Paper List (`/papers`)
- All papers sorted by date added
- Filter by year
- Pagination

### 5. Paper Detail (`/papers/{key}`)
- Full metadata display
- BibTeX entry (copyable)
- Delete button
- Link to PDF (if available)

### 6. Upload Page (`/upload`)
- Drag-and-drop zone
- File picker
- Optional tags input
- Progress indicator
- Batch upload support

### 7. Bibliography Generator (`/bibliography`)
- Checkbox list of papers
- Select all / deselect
- Generate and download .bib

---

## Deployment (Render)

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
```

### requirements.txt
```
fastapi>=0.100.0
uvicorn>=0.23.0
httpx>=0.24.0
python-multipart>=0.0.6
jinja2>=3.1.0
python-dotenv>=1.0.0
itsdangerous>=2.1.0    # For secure session cookies
```

### render.yaml (Blueprint)
```yaml
services:
  - type: web
    name: paper-rag-web
    runtime: docker
    repo: https://github.com/YOUR_USERNAME/paper-rag-web
    envVars:
      - key: MCP_API_KEY
        sync: false  # Set manually in dashboard
      - key: RUNPOD_ENDPOINT_URL
        sync: false
      - key: APP_PASSWORD_HASH
        sync: false
      - key: APP_SECRET_KEY
        generateValue: true  # Auto-generate random secret
```

### Deploy Steps
1. Create new Render account (if needed)
2. Click **New** → **Web Service**
3. Connect GitHub repo (`paper-rag-web`)
4. Configure:
   - **Environment**: Docker
   - **Region**: Choose closest to you
   - **Instance Type**: Free tier works for testing, Starter ($7/mo) for production
5. Add environment variables:
   - `MCP_API_KEY` - your RunPod MCP API key
   - `RUNPOD_ENDPOINT_URL` - `https://9f6jgnmmeatk98.api.runpod.ai`
   - `APP_PASSWORD_HASH` - SHA256 hash of your password
   - `APP_SECRET_KEY` - random secret (use `secrets.token_hex(32)`)
6. Click **Create Web Service**
7. Deploys automatically on push to main branch

### Alternative: No Docker (Native Python)

Create `render.yaml`:
```yaml
services:
  - type: web
    name: paper-rag-web
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Render sets `$PORT` automatically (usually 10000).

---

## Development Workflow

1. **Create new repo**: `paper-rag-web`
2. **Set up virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install fastapi uvicorn httpx python-multipart jinja2
   ```
3. **Create project structure** (as outlined above)
4. **Implement RunPod client** first (test connectivity)
5. **Build API routes** with mock data
6. **Add HTML templates**
7. **Implement authentication**
8. **Deploy to Railway**

---

## MCP Tool Reference

Complete signatures for all available MCP tools on the RunPod server:

### search_papers
```python
search_papers(
    query: str,                    # Required - search query
    n_results: int = 5,            # 1-20, number of results
    filter_section: str = None,    # Methods, Results, Discussion, Introduction
    min_year: int = None,          # Filter by year
    output_format: str = "text"    # "text" or "json"
) -> str
```
**JSON response format:**
```json
{
  "results": [
    {
      "title": "...",
      "authors": ["Author1", "Author2"],
      "year": 2024,
      "journal": "...",
      "doi": "...",
      "url": "...",
      "bibtex_key": "Smith2024",
      "abstract": "...",
      "relevance_score": 0.85,
      "section": "Methods",
      "page": 5
    }
  ],
  "query": "original query",
  "count": 5
}
```

### add_paper_from_upload
```python
add_paper_from_upload(
    pdf_data: str,                 # Required - base64-encoded PDF
    filename: str,                 # Required - original filename
    custom_tags: list[str] = []    # Optional tags
) -> str  # Status message with paper details
```

### add_papers_from_folder_upload
```python
add_papers_from_folder_upload(
    pdf_files: list[dict],         # Required - [{"filename": "...", "pdf_data": "base64..."}]
    custom_tags: list[str] = []    # Optional tags for all papers
) -> str  # Summary with processed/skipped/failed counts
```

### get_paper_details
```python
get_paper_details(
    bibtex_key: str                # Required - e.g., "Smith2024"
) -> str  # Formatted text with metadata + BibTeX entry
```

### list_recent_papers
```python
list_recent_papers(
    n: int = 10                    # Number of papers to list
) -> str  # Formatted text list
```

### delete_paper
```python
delete_paper(
    bibtex_key: str,               # Required
    delete_files: bool = True      # Also delete PDF and .bib files
) -> str  # Status message
```

### database_stats
```python
database_stats() -> str            # Formatted statistics text
```

### generate_bibliography
```python
generate_bibliography(
    bibtex_keys: list[str],        # Required - keys to include
    output_path: str = "./references.bib",
    include_abstracts: bool = False
) -> str  # Status message (writes to server filesystem)
```

---

## Testing Checklist

- [ ] Password login works
- [ ] Search returns results
- [ ] Single PDF upload works
- [ ] Batch upload works
- [ ] Paper details display correctly
- [ ] Delete paper works
- [ ] Bibliography export works
- [ ] Stats display correctly
- [ ] Mobile responsive
