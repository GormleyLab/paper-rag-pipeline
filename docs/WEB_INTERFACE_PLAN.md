# Paper RAG Web Interface - Implementation Plan

This document outlines the plan for building a custom web interface for the Paper RAG Pipeline.
**Use this as reference when building the site in a separate repository.**

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
- **Deployment**: Railway, Render, or Fly.io

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
from pathlib import Path

class RunPodClient:
    def __init__(self, api_key: str, endpoint_url: str):
        self.api_key = api_key
        self.endpoint_url = endpoint_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def _call_tool(self, tool_name: str, arguments: dict, timeout: float = 120.0):
        """Call an MCP tool on the RunPod server."""
        async with httpx.AsyncClient() as client:
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
            return response.json()

    async def search_papers(self, query: str, n_results: int = 10):
        return await self._call_tool("search_papers", {
            "query": query,
            "n_results": n_results,
            "output_format": "json"
        })

    async def upload_pdf(self, file_bytes: bytes, filename: str, tags: list = None):
        pdf_data = base64.b64encode(file_bytes).decode('utf-8')
        return await self._call_tool("add_paper_from_upload", {
            "pdf_data": pdf_data,
            "filename": filename,
            "custom_tags": tags or []
        }, timeout=300.0)

    async def upload_batch(self, files: list[tuple[str, bytes]], tags: list = None):
        pdf_files = [
            {"filename": name, "pdf_data": base64.b64encode(data).decode('utf-8')}
            for name, data in files
        ]
        return await self._call_tool("add_papers_from_folder_upload", {
            "pdf_files": pdf_files,
            "custom_tags": tags or []
        }, timeout=600.0)

    async def get_paper(self, bibtex_key: str):
        return await self._call_tool("get_paper_details", {
            "bibtex_key": bibtex_key
        })

    async def list_papers(self, n: int = 20):
        return await self._call_tool("list_recent_papers", {"n": n})

    async def delete_paper(self, bibtex_key: str):
        return await self._call_tool("delete_paper", {
            "bibtex_key": bibtex_key,
            "delete_files": True
        })

    async def get_stats(self):
        return await self._call_tool("database_stats", {})

    async def generate_bibliography(self, keys: list[str], output_path: str = None):
        return await self._call_tool("generate_bibliography", {
            "bibtex_keys": keys,
            "output_path": output_path or "./references.bib"
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
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_ENDPOINT_URL=https://9f6jgnmmeatk98.api.runpod.ai

# App Authentication
APP_PASSWORD_HASH=sha256-hash-of-your-password

# Optional
APP_SECRET_KEY=random-secret-for-sessions
```

To generate password hash:
```python
import hashlib
print(hashlib.sha256("your-password".encode()).hexdigest())
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

## Deployment (Railway)

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### requirements.txt
```
fastapi>=0.100.0
uvicorn>=0.23.0
httpx>=0.24.0
python-multipart>=0.0.6
jinja2>=3.1.0
python-dotenv>=1.0.0
```

### Deploy Steps
1. Create new Railway project
2. Connect GitHub repo
3. Set environment variables
4. Deploy automatically on push

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
