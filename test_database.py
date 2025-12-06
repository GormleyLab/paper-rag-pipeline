#!/usr/bin/env python3
"""
Simple test script for the Paper RAG Pipeline database.
Tests basic functionality without MCP protocol.
"""

import sys
from pathlib import Path
import asyncio
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.mcp_server import initialize_components, load_config
from src.mcp_server import (
    search_papers_tool,
    database_stats_tool, 
    list_recent_papers_tool,
    get_paper_details_tool
)

async def test_database():
    """Test basic database functionality."""
    print("🧪 Testing Paper RAG Pipeline Database\n")
    
    try:
        # Initialize components
        print("1. Loading configuration and initializing components...")
        config = load_config()
        initialize_components()
        print("✅ Components initialized successfully\n")
        
        # Test 1: Database stats
        print("2. Testing database statistics...")
        stats_result = await database_stats_tool({})
        print(stats_result[0].text)
        print()
        
        # Test 2: List recent papers
        print("3. Testing recent papers list...")
        recent_result = await list_recent_papers_tool({"n": 5})
        print(recent_result[0].text)
        print()
        
        # Test 3: Search functionality
        print("4. Testing search functionality...")
        search_query = "machine learning"
            
        search_result = await search_papers_tool({
            "query": search_query,
            "n_results": 3
        })
        print(f"Search results for '{search_query}':")
        print(search_result[0].text)
        print()
        
        # Test 4: Get paper details (if search found results)
        if "bibtex_key" in search_result[0].text and "[" in search_result[0].text:
            # Extract first bibtex key from search results
            import re
            bibtex_match = re.search(r'\[(\w+\d+[a-z]?)\]', search_result[0].text)
            if bibtex_match:
                bibtex_key = bibtex_match.group(1)
                print(f"5. Testing paper details for '{bibtex_key}'...")
                details_result = await get_paper_details_tool({"bibtex_key": bibtex_key})
                print(details_result[0].text)
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_database())