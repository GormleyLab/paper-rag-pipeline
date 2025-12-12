# Jiminy - Academic Research Assistant

*"Let your conscience be your guide"* — A wise research companion for your scientific journey

---

## Project Vision

**Jiminy** is named after Jiminy Cricket from Disney's Pinocchio — the wise, grounded mentor who helps guide Pinocchio on his journey to become real. Just as Jiminy Cricket provides moral clarity and trustworthy guidance through confusing situations, this application serves as a reliable companion for researchers navigating the complex landscape of scientific literature.

### The Jiminy Philosophy

| Jiminy Cricket | Jiminy App |
|----------------|------------|
| Guides Pinocchio through moral dilemmas | Guides researchers through complex literature |
| Provides grounded, trustworthy advice | Provides fact-based, cited information |
| Helps distinguish right from wrong | Helps distinguish reliable findings from speculation |
| Offers wisdom during chaotic moments | Brings clarity to overwhelming paper collections |
| Mentors on the journey to becoming "real" | Mentors on the journey to producing real science |
| Small but mighty conscience | Lightweight but powerful research tool |

The character's essence — being helpful, grounded, honest, and gently guiding — should permeate every aspect of the user experience, from the friendly chat interface to the trustworthy citations.

---

## Overview

A comprehensive web application for managing academic papers via the Paper RAG MCP server, with an integrated AI research assistant powered by the Claude API.

**Use this as the complete specification when building the site using Claude Code.**

---

## Claude Code Prompt

Use this prompt to start building the web interface in a new repository:

```
Create a FastAPI web application called "jiminy" that provides:
1. A web interface for managing academic papers stored on a remote RunPod MCP server
2. An AI-powered research assistant chat interface using the Claude API with MCP tool integration

The app is themed after Jiminy Cricket from Pinocchio — a wise, grounded mentor who guides researchers through their scientific journey with trustworthy, cited information.

Use the WEB_INTERFACE_PLAN.md file as the complete specification. It contains:
- Project structure with all files
- Complete RunPod client implementation with MCP response parsing
- Claude API client implementation with MCP connector for autonomous RAG queries
- Authentication implementation
- All API endpoints (paper management + chat)
- UI page descriptions with chat interface
- Environment variables
- Render deployment configuration
- Complete MCP tool signatures and response formats

**IMPORTANT**: Before implementing any frontend components, read and follow the frontend-design skill at:
https://claude-plugins.dev/skills/@anthropics/claude-code/frontend-design

Apply the frontend-design principles to create a distinctive, visually striking interface that:
- Avoids generic AI aesthetics (no purple gradients, no Inter/Roboto fonts)
- Evokes the Jiminy Cricket character: warm, wise, trustworthy, slightly whimsical
- Uses a nature-inspired or vintage storybook color palette (consider: warm greens, amber/gold accents, cream backgrounds, touches of cricket-wing iridescence)
- Typography should feel scholarly yet approachable — like a wise friend explaining complex topics
- Include subtle cricket/conscience-themed motifs where appropriate (umbrella icon, top hat, star wishes)
- Animations should feel gentle and helpful, not flashy
- The overall vibe: "Your friendly research conscience"

Key requirements:
1. Use FastAPI with Jinja2 templates
2. Simple password authentication with secure session cookies
3. Paper operations go through RunPodClient which calls the MCP server
4. Chat operations use the Anthropic Python SDK with MCP connector
5. Use HTMX for interactive updates without full page reloads
6. Tailwind CSS for styling (via CDN)
7. Mobile responsive design
8. Real-time chat streaming with Server-Sent Events (SSE)

Start by:
1. Creating the project structure
2. Implementing the RunPodClient from the plan
3. Implementing the ClaudeAPIClient with MCP connector
4. Setting up FastAPI with authentication
5. Building the home page with search
6. Building the chat interface
7. Adding upload functionality

The RunPod endpoint is already deployed and accepts Bearer token authentication at /mcp.
```

---

## Overview

### Why Jiminy?

Every researcher needs a trustworthy guide. Like Jiminy Cricket perched on Pinocchio's shoulder, this application serves two purposes:

1. **Paper Management Portal**: RunPod load-balanced endpoints require authentication at the proxy level, which blocks Claude Desktop's OAuth discovery flow. Jiminy handles user authentication separately and makes authenticated requests to RunPod from the backend.

2. **AI Research Conscience**: Users can chat with their "research conscience" about topics in their paper database. Claude automatically queries the RAG database via MCP tools to provide fact-based answers with proper citations — always grounded in your actual literature, never making things up.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Browser                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────────┐
        │  Paper Management │           │    Chat Interface     │
        │   (HTMX/REST)     │           │   (SSE Streaming)     │
        └───────────────────┘           └───────────────────────┘
                    │                               │
                    ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (Render/Railway)                        │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │      RunPodClient           │    │        ClaudeAPIClient              │ │
│  │  (Direct MCP Tool Calls)    │    │  (Claude API + MCP Connector)       │ │
│  └─────────────────────────────┘    └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                               │
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────────┐
        │   RunPod MCP      │           │   Anthropic API       │
        │   Server (SSE)    │◄──────────│   (MCP Connector)     │
        │                   │           │                       │
        │  Paper RAG Tools: │           │  Connects to RunPod   │
        │  - search_papers  │           │  MCP server via       │
        │  - get_paper_...  │           │  mcp_servers param    │
        │  - add_paper_...  │           │                       │
        │  - database_stats │           │                       │
        └───────────────────┘           └───────────────────────┘
```

### Two Integration Patterns

This application implements two distinct patterns for interacting with the MCP server:

#### Pattern 1: Direct MCP Tool Calls (Paper Management)
Used for CRUD operations where the user explicitly requests an action:
- Upload papers
- Search papers
- Delete papers
- View paper details
- Generate bibliographies

```python
# Direct tool call via RunPodClient
result = await runpod_client.search_papers(query="drug delivery nanoparticles")
```

#### Pattern 2: Claude API with MCP Connector (AI Chat)
Used for conversational AI interactions where Claude autonomously decides when to query the database:
- Research questions about topics in the database
- Synthesizing information across multiple papers
- Finding specific facts with citations
- Explaining concepts using papers as sources

```python
# Claude autonomously uses MCP tools via Anthropic API
response = await claude_client.chat(
    messages=[{"role": "user", "content": "What methods have been used for controlled release of ChABC?"}],
    use_mcp_tools=True  # Claude will call search_papers as needed
)
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | FastAPI (Python) | Web server, API routes, SSE streaming |
| Frontend | Jinja2 + HTMX | Server-side rendering with dynamic updates |
| Styling | Tailwind CSS (CDN) | Responsive, utility-first styling |
| Chat Streaming | Server-Sent Events | Real-time token streaming |
| MCP Client (Direct) | httpx | Direct JSON-RPC calls to RunPod |
| Claude API | anthropic SDK | Chat completions with MCP connector |
| Authentication | Session cookies | Simple password protection |
| Deployment | Render / Railway | Cloud hosting |

---

## Core Features

### Paper Management Features
1. **PDF Upload** - Drag-and-drop or file picker to upload PDFs
2. **Batch Upload** - Upload multiple PDFs from a folder
3. **Semantic Search** - Search across paper database with natural language
4. **Browse Papers** - List all papers with metadata
5. **Paper Details** - View full metadata, BibTeX entry
6. **Bibliography Export** - Generate .bib files from selected papers
7. **Delete Papers** - Remove papers from database
8. **Database Stats** - View paper count, year distribution

### AI Chat Features
1. **Research Chat** - Conversational interface for research queries
2. **RAG-Powered Responses** - Claude automatically searches papers for relevant information
3. **Cited Answers** - Responses include citations to source papers
4. **Streaming Responses** - Real-time token streaming for responsive UX
5. **Chat History** - Session-based conversation memory
6. **Source Attribution** - Clear indication when answers come from paper database

---

## Project Structure

```
jiminy/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings from environment
│   ├── auth.py                  # Password authentication
│   ├── runpod_client.py         # Direct MCP tool calls to RunPod
│   ├── claude_client.py         # Claude API with MCP connector
│   └── routes/
│       ├── __init__.py
│       ├── pages.py             # HTML page routes
│       ├── api.py               # JSON API routes (paper management)
│       └── chat.py              # Chat API routes (SSE streaming)
├── templates/
│   ├── base.html                # Base template with nav, Jiminy branding
│   ├── login.html               # Login page
│   ├── index.html               # Home/search page
│   ├── papers.html              # Paper list ("Your Library")
│   ├── paper_detail.html        # Single paper view
│   ├── upload.html              # Upload page
│   ├── chat.html                # AI research chat ("Ask Jiminy")
│   ├── bibliography.html        # Bibliography generator
│   └── components/
│       ├── search_bar.html
│       ├── paper_card.html
│       ├── chat_message.html
│       ├── citation_card.html
│       └── stats_widget.html
├── static/
│   ├── css/
│   │   └── styles.css           # Custom styles, Jiminy theme
│   ├── js/
│   │   ├── upload.js            # File upload handling
│   │   └── chat.js              # Chat interface with SSE
│   └── images/
│       └── jiminy-icon.svg      # Cricket/conscience icon
├── requirements.txt
├── Dockerfile
├── render.yaml
└── README.md
```

---

## API Endpoints

### Authentication
```python
POST /login          # Verify password, set session cookie
GET  /logout         # Clear session
```

### Paper Management (Direct MCP)
```python
GET  /api/search?q={query}&n={limit}    # Search papers
POST /api/upload                         # Upload single PDF (multipart)
POST /api/upload-batch                   # Upload multiple PDFs
GET  /api/papers                         # List recent papers
GET  /api/papers/{bibtex_key}           # Get paper details
GET  /api/papers/{bibtex_key}/pdf      # Download PDF file
DELETE /api/papers/{bibtex_key}         # Delete paper
GET  /api/stats                         # Database statistics
POST /api/bibliography                   # Generate .bib file
```

### AI Chat (Claude API + MCP)
```python
POST /api/chat                          # Send message, get response (JSON)
GET  /api/chat/stream                   # SSE stream for real-time tokens
POST /api/chat/clear                    # Clear conversation history
GET  /api/chat/history                  # Get current conversation
```

---

## Implementation Details

### RunPod Client (Queue-Based Endpoint)

```python
# app/runpod_client.py
import httpx
import base64
import json
from typing import Any, Optional

class MCPError(Exception):
    """Error from MCP server."""
    pass

class RunPodClient:
    """
    Client for MCP tool calls to RunPod queue-based endpoint.
    Used for paper management operations (CRUD).

    Queue-based endpoints use /runsync for synchronous calls with this format:
    {
        "input": {
            "mode": "tool_call",
            "tool": "tool_name",
            "arguments": {...}
        }
    }
    """

    def __init__(self, api_key: str, endpoint_id: str):
        self.api_key = api_key
        self.endpoint_id = endpoint_id
        self.base_url = f"https://api.runpod.ai/v2/{endpoint_id}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _parse_response(self, response_json: dict) -> str:
        """
        Parse RunPod queue response and extract result.

        Queue-based responses have this structure:
        {
            "id": "sync-xxx",
            "status": "COMPLETED",
            "output": {"result": "actual result here"},
            "delayTime": 123,
            "executionTime": 456
        }
        """
        if response_json.get("status") == "FAILED":
            error = response_json.get("error", "Unknown error")
            raise MCPError(f"Job failed: {error}")

        if response_json.get("status") == "IN_QUEUE":
            raise MCPError("Job still in queue - increase timeout or poll for result")

        output = response_json.get("output", {})

        # Handle tool_call mode responses
        if "result" in output:
            return output["result"]

        # Handle error in output
        if "error" in output:
            raise MCPError(f"Tool error: {output['error']}")

        return str(output)

    async def _call_tool(self, tool_name: str, arguments: dict, timeout: float = 120.0) -> str:
        """Call an MCP tool on the RunPod server via queue-based endpoint."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/runsync",
                    headers=self.headers,
                    json={
                        "input": {
                            "mode": "tool_call",
                            "tool": tool_name,
                            "arguments": arguments
                        }
                    },
                    timeout=timeout
                )
                response.raise_for_status()
                return self._parse_response(response.json())
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise MCPError("Authentication failed - check RUNPOD_API_KEY")
                raise MCPError(f"HTTP error {e.response.status_code}: {e.response.text}")
            except httpx.TimeoutException:
                raise MCPError(f"Request timed out after {timeout}s")

    async def search_papers(
        self,
        query: str,
        n_results: int = 10,
        filter_section: Optional[str] = None,
        min_year: Optional[int] = None
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
        return json.loads(result)

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
        """Get database statistics."""
        return await self._call_tool("database_stats", {})

    async def generate_bibliography(self, bibtex_keys: list[str], include_abstracts: bool = False) -> str:
        """
        Generate BibTeX file content for selected papers.
        
        NOTE: This returns BibTeX content as a string. For web download,
        you may need to return this content directly or save it temporarily
        on the server and provide a download link.
        """
        return await self._call_tool("generate_bibliography", {
            "bibtex_keys": bibtex_keys,
            "include_abstracts": include_abstracts,
            "output_path": "/tmp/references.bib"  # Server-side path (may not be used if returning content)
        })

    async def get_paper_pdf(self, bibtex_key: str) -> bytes:
        """Get PDF file as bytes. Returns base64-decoded PDF data."""
        result = await self._call_tool("get_paper_pdf", {"bibtex_key": bibtex_key})
        return base64.b64decode(result)
```

### Claude API Client with MCP Connector

```python
# app/claude_client.py
import anthropic
from typing import AsyncGenerator, Optional
import json

class ClaudeAPIClient:
    """
    Client for Claude API with MCP connector integration.
    Used for AI-powered research chat that can autonomously query the paper database.
    
    Uses Anthropic's MCP connector feature to let Claude automatically:
    - Search papers when answering research questions
    - Retrieve paper details for citations
    - Access database statistics
    
    Reference: https://docs.claude.com/en/docs/agents-and-tools/mcp-connector
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
        mcp_server_url: str,
        mcp_api_key: str,
        model: str = "claude-sonnet-4-5"
    ):
        self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        self.async_client = anthropic.AsyncAnthropic(api_key=anthropic_api_key)
        self.model = model
        self.mcp_server_url = mcp_server_url
        self.mcp_api_key = mcp_api_key
        
        # System prompt for Jiminy - the research conscience
        self.system_prompt = """You are Jiminy, a wise and friendly research assistant — like a helpful conscience guiding scientists through their literature. Your personality is warm, trustworthy, and gently encouraging, inspired by Jiminy Cricket from Pinocchio.

Your role is to help researchers understand their paper database by providing accurate, well-cited information. You're their guide on the journey of science.

IMPORTANT GUIDELINES:
1. When users ask research questions, use the search_papers tool to find relevant information from the database.
2. Always cite your sources using the paper's BibTeX key (e.g., [Smith2024], [Wang2023]).
3. If the database doesn't contain relevant papers, honestly say so — never make things up! A good conscience tells the truth.
4. Synthesize information from multiple papers when appropriate.
5. Be precise about what the papers actually say vs. your general knowledge.
6. When quoting or paraphrasing, indicate which paper the information comes from.
7. Be encouraging and supportive — research is hard, and you're here to help!

PERSONALITY NOTES:
- Warm and approachable, but scholarly
- Honest even when the answer is "I don't have that in my library"
- Gently guides users toward better questions when needed
- Celebrates when you find exactly what they're looking for
- Occasionally uses cricket/conscience metaphors if natural (but don't overdo it)

AVAILABLE TOOLS:
- search_papers: Search the paper database with semantic queries. Returns relevant text chunks with source attribution.
- get_paper_details: Get full metadata and BibTeX for a specific paper.
- database_stats: Check what papers are available in the database.

FORMAT FOR CITATIONS:
- Use inline citations like: "Controlled release mechanisms have been studied extensively [Smith2024]."
- When synthesizing: "Multiple studies have shown... [Paper1, Paper2]."
- For direct findings: "According to Wang et al., the results demonstrated... [Wang2023]."
"""

    def _get_mcp_config(self, allowed_tools: Optional[list[str]] = None) -> tuple[list, list]:
        """
        Get MCP server and toolset configuration for Claude API.
        
        Returns:
            Tuple of (mcp_servers list, tools list with mcp_toolset)
        """
        # MCP server definition
        mcp_servers = [
            {
                "type": "url",
                "url": self.mcp_server_url,
                "name": "paper-rag",
                "authorization_token": self.mcp_api_key
            }
        ]
        
        # MCP toolset configuration
        toolset_config = {
            "type": "mcp_toolset",
            "mcp_server_name": "paper-rag"
        }
        
        # Optionally restrict to specific tools
        if allowed_tools:
            toolset_config["default_config"] = {"enabled": False}
            toolset_config["configs"] = {
                tool: {"enabled": True} for tool in allowed_tools
            }
        
        return mcp_servers, [toolset_config]

    async def chat(
        self,
        messages: list[dict],
        use_mcp_tools: bool = True,
        allowed_tools: Optional[list[str]] = None,
        max_tokens: int = 4096
    ) -> dict:
        """
        Send a chat message to Claude with optional MCP tool access.
        
        Args:
            messages: Conversation history in Claude format
            use_mcp_tools: Whether to enable MCP tools for RAG
            allowed_tools: Optional list of specific tools to enable (default: all)
            max_tokens: Maximum response tokens
            
        Returns:
            dict with 'content' (response text) and 'citations' (papers referenced)
        """
        # Build request parameters
        request_params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": self.system_prompt,
            "messages": messages
        }
        
        # Add MCP configuration if tools are enabled
        extra_headers = {}
        if use_mcp_tools:
            mcp_servers, tools = self._get_mcp_config(allowed_tools)
            request_params["mcp_servers"] = mcp_servers
            request_params["tools"] = tools
            extra_headers["anthropic-beta"] = "mcp-client-2025-11-20"
        
        # Make API call
        response = await self.async_client.messages.create(
            **request_params,
            extra_headers=extra_headers if extra_headers else None
        )
        
        # Extract response content and any citations
        result = self._parse_response(response)
        return result

    async def chat_stream(
        self,
        messages: list[dict],
        use_mcp_tools: bool = True,
        allowed_tools: Optional[list[str]] = None,
        max_tokens: int = 4096
    ) -> AsyncGenerator[dict, None]:
        """
        Stream chat response with MCP tool support.
        
        Yields dicts with 'type' and 'content':
        - {"type": "text", "content": "..."}  - Text chunk
        - {"type": "tool_use", "content": {...}}  - Tool being called
        - {"type": "tool_result", "content": {...}}  - Tool result
        - {"type": "done", "content": null}  - Stream complete
        """
        # Build request parameters
        request_params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": self.system_prompt,
            "messages": messages
        }
        
        # Add MCP configuration if tools are enabled
        extra_headers = {}
        if use_mcp_tools:
            mcp_servers, tools = self._get_mcp_config(allowed_tools)
            request_params["mcp_servers"] = mcp_servers
            request_params["tools"] = tools
            extra_headers["anthropic-beta"] = "mcp-client-2025-11-20"
        
        # Stream response
        async with self.async_client.messages.stream(
            **request_params,
            extra_headers=extra_headers if extra_headers else None
        ) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "text":
                        pass  # Text will come in deltas
                    elif block.type == "mcp_tool_use":
                        yield {
                            "type": "tool_use",
                            "content": {
                                "tool": block.name,
                                "server": block.server_name
                            }
                        }
                
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "text"):
                        yield {"type": "text", "content": delta.text}
                
                elif event.type == "content_block_stop":
                    pass  # Block complete
                    
                elif event.type == "message_stop":
                    yield {"type": "done", "content": None}

    def _parse_response(self, response) -> dict:
        """
        Parse Claude response, extracting text and tracking MCP tool usage.
        """
        content_parts = []
        tool_uses = []
        citations = set()
        
        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
                # Extract citations from text (e.g., [Smith2024])
                import re
                found_citations = re.findall(r'\[([A-Za-z]+\d{4}[a-z]?)\]', block.text)
                citations.update(found_citations)
            
            elif block.type == "mcp_tool_use":
                tool_uses.append({
                    "tool": block.name,
                    "server": block.server_name,
                    "input": block.input
                })
            
            elif block.type == "mcp_tool_result":
                # Tool results are automatically handled by Claude
                pass
        
        return {
            "content": "".join(content_parts),
            "citations": list(citations),
            "tool_uses": tool_uses,
            "stop_reason": response.stop_reason
        }


# Convenience function for one-off queries
async def query_papers(
    query: str,
    anthropic_api_key: str,
    mcp_server_url: str,
    mcp_api_key: str
) -> dict:
    """
    Simple function to query the paper database via Claude.
    
    Example:
        result = await query_papers(
            "What are the main challenges in ChABC delivery?",
            api_key, mcp_url, mcp_key
        )
        print(result["content"])
        print("Citations:", result["citations"])
    """
    client = ClaudeAPIClient(anthropic_api_key, mcp_server_url, mcp_api_key)
    return await client.chat(
        messages=[{"role": "user", "content": query}],
        use_mcp_tools=True
    )
```

### Chat Routes with SSE Streaming

```python
# app/routes/chat.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from app.auth import require_auth
from app.claude_client import ClaudeAPIClient
from app.config import settings
import json

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Store conversation history per session (in production, use Redis or database)
conversation_store: dict[str, list] = {}

def get_claude_client() -> ClaudeAPIClient:
    return ClaudeAPIClient(
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        mcp_server_url=settings.MCP_SERVER_URL,
        mcp_api_key=settings.MCP_API_KEY,
        model=settings.CLAUDE_MODEL
    )

@router.post("")
async def chat(
    request: Request,
    auth: bool = Depends(require_auth),
    client: ClaudeAPIClient = Depends(get_claude_client)
):
    """Send a message and get a response (non-streaming)."""
    data = await request.json()
    user_message = data.get("message", "")
    session_id = request.cookies.get("session", "default")
    
    # Get or create conversation history
    if session_id not in conversation_store:
        conversation_store[session_id] = []
    
    messages = conversation_store[session_id]
    messages.append({"role": "user", "content": user_message})
    
    # Get response from Claude with MCP tools
    result = await client.chat(messages=messages, use_mcp_tools=True)
    
    # Add assistant response to history
    messages.append({"role": "assistant", "content": result["content"]})
    
    return {
        "response": result["content"],
        "citations": result["citations"],
        "tool_uses": result.get("tool_uses", [])
    }

@router.get("/stream")
async def chat_stream(
    request: Request,
    message: str,
    auth: bool = Depends(require_auth),
    client: ClaudeAPIClient = Depends(get_claude_client)
):
    """Stream chat response via Server-Sent Events."""
    session_id = request.cookies.get("session", "default")
    
    # Get or create conversation history
    if session_id not in conversation_store:
        conversation_store[session_id] = []
    
    messages = conversation_store[session_id]
    messages.append({"role": "user", "content": message})
    
    async def generate():
        full_response = []
        async for chunk in client.chat_stream(messages=messages, use_mcp_tools=True):
            if chunk["type"] == "text":
                full_response.append(chunk["content"])
                yield f"data: {json.dumps(chunk)}\n\n"
            elif chunk["type"] == "tool_use":
                yield f"data: {json.dumps(chunk)}\n\n"
            elif chunk["type"] == "done":
                # Save complete response to history
                messages.append({"role": "assistant", "content": "".join(full_response)})
                yield f"data: {json.dumps(chunk)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

@router.post("/clear")
async def clear_history(
    request: Request,
    auth: bool = Depends(require_auth)
):
    """Clear conversation history for current session."""
    session_id = request.cookies.get("session", "default")
    conversation_store[session_id] = []
    return {"status": "cleared"}

@router.get("/history")
async def get_history(
    request: Request,
    auth: bool = Depends(require_auth)
):
    """Get conversation history for current session."""
    session_id = request.cookies.get("session", "default")
    return {"messages": conversation_store.get(session_id, [])}
```

### Authentication

```python
# app/auth.py
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
import hashlib
import os

# Password hash stored in environment
PASSWORD_HASH = os.environ.get("APP_PASSWORD_HASH", "")

def hash_password(password: str) -> str:
    """Hash a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str) -> bool:
    """Verify a password against the stored hash."""
    return hash_password(password) == PASSWORD_HASH

async def require_auth(request: Request) -> bool:
    """Dependency to require authentication."""
    from app.config import settings
    session_token = request.cookies.get("session")
    if not session_token or session_token != settings.APP_PASSWORD_HASH:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True
```

---

## Environment Variables

```bash
# RunPod MCP Server Configuration (Queue-Based Endpoint)
RUNPOD_API_KEY=your-runpod-api-key                     # RunPod API key for authentication
RUNPOD_ENDPOINT_ID=bonn0doh0yb272                      # Your RunPod endpoint ID
MCP_API_KEY=your-mcp-api-key                           # MCP API key (for app-level auth if needed)

# The endpoint URL is: https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync

# Claude API Configuration  
ANTHROPIC_API_KEY=sk-ant-api-...                       # Anthropic API key
CLAUDE_MODEL=claude-sonnet-4-5                         # Model to use for chat

# App Authentication
APP_PASSWORD_HASH=sha256-hash-of-your-password         # Login password hash
APP_SECRET_KEY=random-secret-for-sessions              # Session cookie secret

# Optional
DEBUG=false
LOG_LEVEL=INFO
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

### Design Requirements — The Jiminy Aesthetic

**IMPORTANT**: Apply the frontend-design skill principles to all UI components, guided by the Jiminy Cricket character essence:

#### Color Palette
Evoke the warmth and wisdom of Jiminy Cricket:
- **Primary**: Warm forest green (#2D5A3D) — cricket-inspired, natural, trustworthy
- **Secondary**: Amber/gold (#D4A84B) — like lamplight, wisdom, "wishing star" accents
- **Background**: Warm cream/parchment (#FDF6E3) — like old books, scholarly
- **Text**: Deep charcoal (#2C2C2C) — readable, serious but not harsh
- **Accent**: Soft teal (#5B9A8B) — cricket-wing iridescence for highlights
- **Error/Warning**: Warm red (#C75B5B) — gentle alerts

#### Typography
- **Headings**: A characterful serif like Fraunces, Playfair Display, or Libre Baskerville — scholarly yet warm
- **Body**: A readable humanist sans like Source Sans Pro, Nunito, or Lato — friendly and clear
- **Code/Data**: JetBrains Mono or Fira Code — for BibTeX and technical content
- **Avoid**: Inter, Roboto, Arial — too generic

#### Visual Motifs (use sparingly)
- Small cricket silhouette or umbrella icon as logo/favicon
- Subtle star/sparkle accents (wishing on a star theme)
- Gentle curved lines rather than harsh angles
- Paper/parchment textures in backgrounds
- Warm shadows, not cold grays

#### Animation Philosophy
Like Jiminy himself — helpful and present, never flashy:
- Gentle fade-ins for content loading
- Subtle bounce on successful actions
- Smooth transitions between pages
- "Thinking" animation should feel contemplative, not frantic
- Celebrate moments (paper added, answer found) with brief, joyful feedback

#### Voice & Tone in UI Copy
- Helpful and encouraging, not robotic
- "Your library" not "Database"
- "Ask Jiminy" not "Chat Interface"
- "Let's find that for you" not "Searching..."
- Error messages should be gentle and solution-oriented

### Page Specifications

#### 1. Login Page (`/login`)
- Warm, welcoming design
- Jiminy logo/icon
- Tagline: "Let your conscience be your guide" or "Your research companion awaits"
- Simple password input with friendly styling
- "Remember me" option (optional checkbox)
- Subtle animation on form appearance
- Redirect to home on success

#### 2. Home/Dashboard (`/`)
- Greeting: "Good [morning/afternoon], researcher!" or "What shall we explore today?"
- Search bar prominently displayed with placeholder: "Search your library..."
- Database statistics as friendly cards (paper count, year range)
- "Recently Added" papers section
- Prominent "Ask Jiminy" button linking to chat

#### 3. Search Results (`/search?q=...`)
- Query display: "Searching for: [query]"
- Result count with encouraging message
- Paper cards showing: title, authors, year, journal, relevance score
- Excerpt preview with matched terms highlighted
- Click to view full details
- Add to bibliography selection

#### 4. Your Library (`/papers`)
- All papers sorted by date added (newest first)
- Filter by year range
- Visual cards or list view toggle
- Pagination (20 per page)
- Bulk selection for bibliography export
- Empty state: "Your library is waiting for papers! Upload some to get started."

#### 5. Paper Detail (`/papers/{key}`)
- Clean, readable layout
- Full metadata (title, authors, year, journal, DOI)
- Abstract in a highlighted card
- BibTeX entry with one-click copy (toast: "Copied to clipboard!")
- PDF download button: "Download PDF" with friendly styling
- External links (DOI, arXiv, PubMed) as friendly buttons
- Delete with confirmation: "Are you sure? This paper will leave your library."

#### 6. Add Papers (`/upload`)
- Drag-and-drop zone with cricket-themed empty state
- "Drop your PDFs here" with subtle animation on hover
- File picker button as alternative
- Optional tags input
- Progress indicator: "Jiminy is reading your paper..."
- Success feedback: "Paper added to your library!" with paper title
- Batch upload support

#### 7. Ask Jiminy (`/chat`) ⭐ FEATURED
The heart of the application — your research conscience.

**Header Area**:
- Jiminy icon/logo
- Title: "Ask Jiminy" 
- Subtitle: "Your research conscience — always grounded in your papers"
- "New Conversation" button

**Chat Area**:
- Message history scrolling up
- **User messages**: Right-aligned, warm accent color
- **Jiminy responses**: Left-aligned, with small cricket icon, cream background
- **Citation highlighting**: BibTeX keys are gold-colored, clickable links
- **Tool use indicators**: Gentle animation: "Searching your library..." with small magnifying glass or book icon

**Welcome State** (new conversation):
```
🦗 Hello! I'm Jiminy, your research conscience.

I'm here to help you explore and understand the papers in your library. 
I'll always cite my sources so you know exactly where information comes from.

Try asking me something like:
• "What methods have been used for controlled ChABC delivery?"
• "Summarize findings about RAFT polymerization in my papers"
• "What do I have about spinal cord injury?"

What would you like to explore?
```

**Input Area**:
- Textarea with placeholder: "Ask me about your papers..."
- Send button with subtle hover animation
- Character hint: "I'll search your library to find grounded answers"

**States**:
- Idle: Input ready, history visible
- Searching: "Searching your library..." with gentle animation
- Streaming: Response appearing word by word with subtle cursor
- Complete: Full response with clickable golden citations
- Error: "I had trouble with that. Let's try again?" (never scary)

#### 8. Bibliography Generator (`/bibliography`)
- Title: "Build Your Bibliography"
- Paper selection via checkboxes with paper cards
- Search/filter to find specific papers
- Select all / deselect all
- Include abstracts toggle
- Preview generated BibTeX in scrollable area
- Download button: "Download .bib file"
- Success: "Your bibliography is ready!"

---

## Frontend Implementation

### Chat JavaScript (SSE Streaming)

```javascript
// static/js/chat.js

class JiminyChat {
    constructor(options = {}) {
        this.messagesContainer = document.getElementById('chat-messages');
        this.inputField = document.getElementById('chat-input');
        this.sendButton = document.getElementById('chat-send');
        this.statusIndicator = document.getElementById('chat-status');
        
        this.setupEventListeners();
        this.setupPromptSuggestions();
    }
    
    setupEventListeners() {
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.inputField.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }
    
    setupPromptSuggestions() {
        document.querySelectorAll('.prompt-suggestion').forEach(btn => {
            btn.addEventListener('click', () => {
                this.inputField.value = btn.textContent.replace(/"/g, '');
                this.inputField.focus();
            });
        });
    }
    
    async sendMessage() {
        const message = this.inputField.value.trim();
        if (!message) return;
        
        // Add user message to UI
        this.addMessage('user', message);
        this.inputField.value = '';
        
        // Show searching state
        this.setStatus('searching');
        
        // Create Jiminy message container for streaming
        const jiminyDiv = this.addMessage('jiminy', '', true);
        
        try {
            // Connect to SSE endpoint
            const encodedMessage = encodeURIComponent(message);
            const eventSource = new EventSource(`/api/chat/stream?message=${encodedMessage}`);
            
            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'text') {
                    // Append text chunk
                    jiminyDiv.innerHTML += this.formatText(data.content);
                    this.scrollToBottom();
                    this.setStatus('streaming');
                } else if (data.type === 'tool_use') {
                    this.setStatus('searching', data.content.tool);
                } else if (data.type === 'done') {
                    // Stream complete
                    eventSource.close();
                    this.setStatus('idle');
                    this.highlightCitations(jiminyDiv);
                }
            };
            
            eventSource.onerror = (error) => {
                console.error('SSE error:', error);
                eventSource.close();
                this.setStatus('error');
                jiminyDiv.innerHTML += '<em class="error-text">I had trouble with that. Let\'s try again?</em>';
            };
            
        } catch (error) {
            console.error('Chat error:', error);
            this.setStatus('error');
        }
    }
    
    addMessage(role, content, streaming = false) {
        const div = document.createElement('div');
        const isJiminy = role === 'jiminy';
        div.className = `message message-${role} ${streaming ? 'streaming' : ''}`;
        
        if (isJiminy) {
            div.innerHTML = `
                <div class="message-avatar">🦗</div>
                <div class="message-content">${this.formatText(content)}</div>
            `;
        } else {
            div.innerHTML = `
                <div class="message-content">${this.formatText(content)}</div>
            `;
        }
        
        this.messagesContainer.appendChild(div);
        this.scrollToBottom();
        
        return div.querySelector('.message-content');
    }
    
    formatText(text) {
        // Basic markdown-like formatting
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }
    
    highlightCitations(element) {
        // Make citations clickable with golden highlight
        const html = element.innerHTML;
        const citationPattern = /\[([A-Za-z]+\d{4}[a-z]?)\]/g;
        element.innerHTML = html.replace(citationPattern, (match, key) => {
            return `<a href="/papers/${key}" class="citation-link" title="View paper in library">${match}</a>`;
        });
    }
    
    setStatus(status, detail = '') {
        const statusMap = {
            'idle': '',
            'searching': `📚 Searching your library${detail ? ` (${detail})` : ''}...`,
            'streaming': '✍️ Writing...',
            'error': '😔 Something went wrong'
        };
        
        this.statusIndicator.textContent = statusMap[status] || '';
        this.statusIndicator.className = `chat-status status-${status}`;
    }
    
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new JiminyChat();
});
```

### Chat Page Template

```html
<!-- templates/chat.html -->
{% extends "base.html" %}

{% block title %}Ask Jiminy{% endblock %}

{% block content %}
<div class="chat-container">
    <!-- Header -->
    <div class="chat-header">
        <div class="jiminy-icon">🦗</div>
        <div class="header-text">
            <h1>Ask Jiminy</h1>
            <p class="subtitle">Your research conscience — always grounded in your papers</p>
        </div>
        <button id="clear-chat" class="btn-secondary">New Conversation</button>
    </div>
    
    <!-- Messages Area -->
    <div id="chat-messages" class="chat-messages">
        <!-- Welcome message -->
        <div class="message message-jiminy">
            <div class="message-avatar">🦗</div>
            <div class="message-content">
                <p>Hello! I'm Jiminy, your research conscience.</p>
                <p>I'm here to help you explore and understand the papers in your library. I'll always cite my sources so you know exactly where information comes from.</p>
                <p class="mt-4"><strong>Try asking me something like:</strong></p>
                <ul class="example-prompts">
                    <li><button class="prompt-suggestion">"What methods have been used for controlled ChABC delivery?"</button></li>
                    <li><button class="prompt-suggestion">"Summarize findings about RAFT polymerization in my papers"</button></li>
                    <li><button class="prompt-suggestion">"What do I have about spinal cord injury?"</button></li>
                </ul>
                <p class="mt-2 text-muted">What would you like to explore?</p>
            </div>
        </div>
    </div>
    
    <!-- Status Indicator -->
    <div id="chat-status" class="chat-status"></div>
    
    <!-- Input Area -->
    <div class="chat-input-container">
        <textarea 
            id="chat-input" 
            placeholder="Ask me about your papers..."
            rows="2"
        ></textarea>
        <button id="chat-send" class="btn-primary">
            <span>Ask</span>
            <svg><!-- send icon --></svg>
        </button>
    </div>
    <p class="input-hint">I'll search your library to find grounded answers</p>
</div>

<script src="/static/js/chat.js"></script>
{% endblock %}
```

---

## MCP Tool Reference

Complete signatures for MCP tools available on the RunPod server (used both for direct calls and via Claude's MCP connector):

### search_papers
```python
search_papers(
    query: str,                    # Required - semantic search query
    n_results: int = 5,            # 1-20, number of results
    filter_section: str = None,    # Methods, Results, Discussion, Introduction
    min_year: int = None,          # Filter by publication year
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
      "page": 5,
      "matched_text": "The relevant excerpt from the paper..."
    }
  ],
  "query": "original query",
  "count": 5
}
```

### get_paper_details
```python
get_paper_details(
    bibtex_key: str                # Required - e.g., "Smith2024"
) -> str  # Formatted text with metadata + BibTeX entry
```

### get_paper_pdf
```python
get_paper_pdf(
    bibtex_key: str                # Required - e.g., "Smith2024"
) -> str  # Base64-encoded PDF file content
```
**Returns**: Base64-encoded string of the PDF file. The client should decode this to get the actual PDF bytes for download.

### list_recent_papers
```python
list_recent_papers(
    n: int = 10                    # Number of papers to list
) -> str  # Formatted text list
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
) -> str  # Status message (writes to server filesystem) or BibTeX content
```
**Note**: This tool may write to the server filesystem at `output_path`. For web applications, you may need to:
- Return the BibTeX content directly if the tool supports it
- Read the file from the server filesystem after generation
- Or fetch individual paper BibTeX entries using `get_paper()` and combine them client-side

---

## Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port (Render uses 10000)
EXPOSE 10000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
```

### requirements.txt

```
fastapi>=0.100.0
uvicorn>=0.23.0
httpx>=0.24.0
anthropic>=0.35.0
python-multipart>=0.0.6
jinja2>=3.1.0
python-dotenv>=1.0.0
itsdangerous>=2.1.0
```

### render.yaml

```yaml
services:
  - type: web
    name: jiminy
    runtime: docker
    repo: https://github.com/YOUR_USERNAME/jiminy
    envVars:
      - key: MCP_API_KEY
        sync: false  # Set manually in dashboard
      - key: MCP_SERVER_URL
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: CLAUDE_MODEL
        value: claude-sonnet-4-5
      - key: APP_PASSWORD_HASH
        sync: false
      - key: APP_SECRET_KEY
        generateValue: true  # Auto-generate random secret
```

### Deploy Steps

1. Create new Render account (if needed)
2. Click **New** → **Web Service**
3. Connect GitHub repo (`jiminy`)
4. Configure:
   - **Environment**: Docker
   - **Region**: Choose closest to you
   - **Instance Type**: Free tier works for testing, Starter ($7/mo) for production
5. Add environment variables:
   - `RUNPOD_API_KEY` - your RunPod API key
   - `RUNPOD_ENDPOINT_ID` - `bonn0doh0yb272` (or your endpoint ID)
   - `ANTHROPIC_API_KEY` - your Anthropic API key
   - `CLAUDE_MODEL` - `claude-sonnet-4-5` (or your preferred model)
   - `APP_PASSWORD_HASH` - SHA256 hash of your password
   - `APP_SECRET_KEY` - random secret (use `secrets.token_hex(32)`)
6. Click **Create Web Service**
7. Deploys automatically on push to main branch

### Alternative: No Docker (Native Python)

If you prefer not to use Docker, you can use Render's native Python runtime:

Create `render.yaml`:
```yaml
services:
  - type: web
    name: jiminy
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Render sets `$PORT` automatically (usually 10000).

---

## Testing Checklist

### Paper Management
- [ ] Password login works
- [ ] Search returns results with relevance scores
- [ ] Single PDF upload works ("Paper added to your library!")
- [ ] Batch upload works (shows summary)
- [ ] Paper details display correctly
- [ ] BibTeX copy button works (toast confirmation)
- [ ] Delete paper works (with friendly confirmation)
- [ ] Bibliography export generates valid .bib file
- [ ] Stats display correctly

### Ask Jiminy (Chat)
- [ ] Chat interface loads with welcome message
- [ ] Example prompts are clickable and populate input
- [ ] Messages send successfully
- [ ] Streaming works (text appears incrementally)
- [ ] "Searching your library..." indicator shows when using tools
- [ ] Citations are golden and clickable (link to paper detail)
- [ ] Conversation history persists in session
- [ ] "New Conversation" button clears history
- [ ] Error states are friendly ("Let's try again?")
- [ ] Jiminy avatar (🦗) appears on assistant messages

### UI/UX & Jiminy Theme
- [ ] Mobile responsive
- [ ] Distinctive design (warm greens, amber accents, cream backgrounds)
- [ ] No generic AI aesthetics (no purple gradients, no Inter font)
- [ ] Cricket/conscience motifs present but subtle
- [ ] Typography is scholarly yet approachable
- [ ] Animations are gentle and helpful
- [ ] Copy uses friendly Jiminy voice
- [ ] Loading states visible and encouraging
- [ ] Error messages are gentle and solution-oriented
- [ ] Navigation intuitive

---

## Development Workflow

1. **Create new repo**: `jiminy`
2. **Set up virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Create project structure** (as outlined above)
4. **Implement RunPod client** first (test connectivity)
5. **Implement Claude API client** with MCP connector
6. **Build API routes** with mock data
7. **Add HTML templates** with Jiminy theme
8. **Implement authentication**
9. **Add chat interface** with SSE streaming
10. **Deploy to Render**

---

## Security Considerations

1. **API Key Protection**: All API keys stored as environment variables, never in code
2. **Password Hashing**: SHA256 hash comparison for authentication
3. **Session Security**: Secure cookies with secret key
4. **Input Validation**: Sanitize user inputs before MCP calls
5. **Rate Limiting**: Consider adding rate limits for chat API
6. **CORS**: Configure appropriately for production

---

## Future Enhancements

1. **Persistent Chat History**: Store Jiminy conversations in database for cross-session continuity
2. **User Accounts**: Multi-user support with individual libraries and API keys
3. **Custom Jiminy Personality**: Allow users to customize the assistant's tone and focus areas
4. **Citation Export**: Export cited papers from chat as bibliography (one-click from chat)
5. **Paper Annotations**: Link Jiminy's insights back to specific papers as notes
6. **Research Journeys**: Save and revisit important conversation threads
7. **Webhook Integration**: Jiminy notifies you when new papers are added
8. **Dark Mode**: A cozy evening reading theme ("Starlight Mode" 🌟)
9. **Mobile App**: Take Jiminy with you on your research journey
