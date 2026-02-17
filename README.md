# GraphRAG MCP Server

A Model Context Protocol server for querying a hybrid graph and vector database system, combining Neo4j (graph database) and Qdrant (vector database) for powerful semantic and graph-based document retrieval.

## Overview

GraphRAG MCP provides a seamless integration between large language models and a hybrid retrieval system that leverages the strengths of both graph databases (Neo4j) and vector databases (Qdrant). This enables:

- **Semantic search** through document embeddings
- **Graph-based context expansion** following intra-document relationships
- **Hybrid search** combining vector similarity with graph relationships
- **Page-based chunking** with smart merging for optimal retrieval
- **Precise page navigation** with support for merged pages
- Full integration with Claude, VS Code, Cursor, and other MCP-enabled clients

This project follows the [Model Context Protocol](https://github.com/modelcontextprotocol/python-sdk) specification, making it compatible with any MCP-enabled client.

## Features

- **Semantic search** using sentence embeddings (all-MiniLM-L6-v2) and Qdrant
- **Graph-based context expansion** using Neo4j intra-document relationships
- **Hybrid search** combining both approaches for comprehensive results
- **Page-level retrieval** - Get exact content from specific pages or page ranges
- **Smart page merging** - Automatically merges small pages during indexing
- **Document filtering** - Search within specific documents
- **MCP tools and resources** for seamless LLM integration
- **Docker Compose** setup for easy deployment
- **Utility scripts** for indexing, testing, and diagnostics

## Prerequisites

- **Python 3.12+** (required for the MCP server)
- **Docker & Docker Compose** (recommended for easy database setup)
- **uv** package manager (for dependency management)

  Install uv:

  ```bash
  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Windows (PowerShell)
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

## Installation

### Quick Start (Recommended)

1. **Clone this repository:**

   ```bash
   git clone https://github.com/AN-SWAPNIL/graphrag_mcp.git
   cd graphrag_mcp
   ```

2. **Install Python dependencies:**

   ```bash
   uv install
   ```

3. **Configure environment variables:**

   Copy the example environment file and customize if needed:

   ```bash
   # Linux/macOS
   cp .env.example .env

   # Windows
   copy .env.example .env
   ```

   Default `.env` configuration:

   ```env
   # Neo4j Configuration
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=password

   # Qdrant Configuration
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   QDRANT_COLLECTION=document_chunks

   # HuggingFace Token (optional, for downloading models)
   HF_TOKEN=your_token_here
   ```

4. **Start databases with Docker Compose:**

   ```bash
   docker-compose up -d
   ```

   This starts:
   - Neo4j on ports 7474 (HTTP) and 7687 (Bolt)
   - Qdrant on ports 6333 (HTTP) and 6334 (gRPC)

   Wait ~20 seconds for databases to initialize.

5. **Index your documents:**

   Place markdown files in the `specs/` directory, then run:

   ```bash
   uv run index_markdown.py
   ```

   This script:
   - Splits documents by page boundaries
   - Merges small pages intelligently
   - Creates embeddings with sentence-transformers
   - Stores vectors in Qdrant
   - Builds graph relationships in Neo4j

6. **Run the MCP server:**
   ```bash
   uv run main.py
   ```

### Windows Quick Start (Batch Scripts)

For Windows users, convenient batch scripts are provided:

```batch
# Start everything (Docker + MCP server)
mcp_start.bat

# Stop everything
mcp_stop.bat
```

### Manual Setup (Without Docker)

If you prefer to run Neo4j and Qdrant without Docker:

#### Neo4j Setup

1. **Using Docker (single container):**

   ```bash
   docker run \
     --name neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/password \
     -v $HOME/neo4j/data:/data \
     -v $HOME/neo4j/logs:/logs \
     neo4j:latest
   ```

2. **Or install locally:**
   - Download from [neo4j.com/download](https://neo4j.com/download/)
   - Follow platform-specific installation instructions
   - Set password to `password` or update `.env` file

#### Qdrant Setup

1. **Using Docker (single container):**

   ```bash
   docker run -p 6333:6333 -p 6334:6334 \
     -v $HOME/qdrant/storage:/qdrant/storage \
     qdrant/qdrant
   ```

2. **Or install locally:**
   - Download from [qdrant.tech/documentation/quick-start](https://qdrant.tech/documentation/quick-start/)
   - Follow installation instructions for your platform

## Project Structure

```
graphrag_mcp/
├── graphrag_mcp/              # Main package
│   ├── __init__.py
│   └── documentation_tool.py  # Core hybrid search implementation
├── specs/                     # Your markdown documents go here
├── .env                       # Environment configuration (create from .env.example)
├── .env.example               # Example environment variables
├── docker-compose.yml         # Docker setup for Neo4j + Qdrant
├── main.py                    # MCP server entry point
├── server.py                  # MCP tool and resource definitions
├── index_markdown.py          # Document indexing script (page-based chunking)
├── clear.py                   # Utility to clear all indexed data
├── test_graphrag.py           # Test script for functionality
├── diagnose_data.py           # Diagnostic script for data validation
├── mcp_start.bat              # Windows: Start Docker + MCP server
├── mcp_stop.bat               # Windows: Stop all services
└── pyproject.toml             # Python dependencies
```

## Utility Scripts

### Indexing Documents: `index_markdown.py`

Indexes markdown files with advanced page-based chunking:

```bash
uv run index_markdown.py
```

**Features:**

- Splits documents by "Page N" markers
- Merges pages with fewer than 50 words into adjacent pages
- Creates semantic embeddings (384-dim vectors)
- Builds Neo4j graph with three relationship types:
  - `NEXT_PAGE`: Sequential page flow
  - `RELATED_TO`: Semantic similarity within document
  - `CONTAINS`: Document-to-page relationships

**Output:**

- Vectors stored in Qdrant with page metadata
- Graph nodes (`:Document`, `:Page`) in Neo4j
- Detailed statistics on merging and relationships

### Testing: `test_graphrag.py`

Quick functionality test:

```bash
uv run test_graphrag.py
```

Tests:

1. Vector search
2. Hybrid search with context expansion
3. Intra-document context retrieval

### Diagnostics: `diagnose_data.py`

Validate your indexed data:

```bash
uv run diagnose_data.py
```

Checks:

- Qdrant payload structure
- Neo4j document and page counts
- Relationship statistics
- Sample data from both databases

### Clear Data: `clear.py`

Remove all indexed data (use with caution):

```bash
uv run clear.py
```

This deletes:

- All Neo4j nodes and relationships
- The entire Qdrant collection

## Integration with MCP Clients

The GraphRAG MCP server works with any MCP-compatible client, including VS Code, Claude Desktop, and Cursor.

### VS Code Integration

1. **Open VS Code settings** and search for "MCP" or edit your MCP configuration file directly.

2. **Add the server configuration** to your `mcp.json` file:

   **Location (Windows):**

   ```
   C:\Users\<YourUsername>\AppData\Roaming\Code\User\mcp.json
   ```

   **Location (macOS/Linux):**

   ```
   ~/.config/Code/User/mcp.json
   ```

3. **Configuration:**

   ```json
   {
     "servers": {
       "my-graph-rag-mcp": {
         "type": "stdio",
         "command": "uv",
         "args": [
           "--directory",
           "D:\\Codes\\mcp\\graphrag_mcp", // Change to your path
           "run",
           "main.py"
         ]
       }
     }
   }
   ```

   **For Unix-like systems (macOS/Linux):**

   ```json
   {
     "servers": {
       "my-graph-rag-mcp": {
         "type": "stdio",
         "command": "uv",
         "args": ["--directory", "/path/to/graphrag_mcp", "run", "main.py"]
       }
     }
   }
   ```

4. **Restart VS Code** - The MCP server will now be available to GitHub Copilot Chat.

### Claude Desktop Integration

1. **Locate your Claude configuration file:**

   **macOS:**

   ```
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

   **Windows:**

   ```
   %APPDATA%\Claude\claude_desktop_config.json
   ```

2. **Add the server:**

   ```json
   {
     "mcpServers": {
       "GraphRAG": {
         "command": "uv",
         "args": ["--directory", "/path/to/graphrag_mcp", "run", "main.py"]
       }
     }
   }
   ```

3. **Restart Claude Desktop**

### Cursor Integration

1. **Locate your Cursor configuration file:**

   **macOS/Linux:**

   ```
   ~/.cursor/mcp.json
   ```

   **Windows:**

   ```
   %APPDATA%\Cursor\mcp.json
   ```

2. **Add the configuration:**

   ```json
   {
     "mcpServers": {
       "GraphRAG": {
         "command": "uv",
         "args": ["--directory", "/path/to/graphrag_mcp", "run", "main.py"]
       }
     }
   }
   ```

3. **Restart Cursor**

## Usage

### MCP Tools

The server provides **5 powerful tools** for LLM integration:

#### 1. `search_documentation` - Semantic Vector Search

Search documentation using pure vector similarity.

**Parameters:**

- `query` (str): Natural language query
- `limit` (int, default=5): Maximum chunks to return
- `doc_filter` (str, optional): Filter by document ID (e.g., 'application_spec', 'core_spec')

**Example:**

```python
result = search_documentation(
    query="How does authentication work?",
    limit=5,
    doc_filter="core_spec"
)
```

**Returns:**

```json
{
  "query": "How does authentication work?",
  "chunks": [
    {
      "doc": "core_spec",
      "chunk_idx": 15,
      "page_num": 42,
      "page_range": [42],
      "text": "Authentication is handled via...",
      "score": 0.87
    }
  ],
  "count": 5,
  "search_type": "vector_search"
}
```

#### 2. `hybrid_search` - Vector + Graph Context

Combine semantic search with graph-based context expansion using intra-document relationships.

**Parameters:**

- `query` (str): Natural language query
- `limit` (int, default=5): Maximum seed chunks from vector search
- `doc_filter` (str, optional): Filter by document ID
- `expand_context` (bool, default=True): Enrich with graph relationships

**Example:**

```python
result = hybrid_search(
    query="API endpoints and authentication",
    limit=5,
    doc_filter=None,
    expand_context=True
)
```

**Returns:** Same as `search_documentation`, plus additional relationship data:

```json
{
  "chunks": [
    {
      "doc": "core_spec",
      "chunk_idx": 15,
      "page_num": 42,
      "text": "...",
      "score": 0.87,
      "related_next": [{ "chunk_idx": 16, "page_num": 43, "text": "..." }],
      "related_previous": [{ "chunk_idx": 14, "page_num": 41, "text": "..." }],
      "related_discussing": [
        {
          "chunk_idx": 89,
          "page_num": 234,
          "text": "...",
          "keywords": ["API", "auth"]
        }
      ]
    }
  ],
  "expanded_with_context": true
}
```

#### 3. `get_page` - Retrieve Specific Pages

Get exact content from a specific page or page range. Automatically handles merged pages.

**Parameters:**

- `doc_id` (str): Document identifier (e.g., 'core_spec')
- `start_page` (int): Page number to retrieve
- `end_page` (int, optional): End of page range (if requesting multiple pages)

**Examples:**

```python
# Single page
result = get_page(doc_id='core_spec', start_page=494)

# Page range
result = get_page(doc_id='core_spec', start_page=494, end_page=500)
```

**Returns:**

```json
{
  "doc_id": "core_spec",
  "start_page": 494,
  "end_page": 494,
  "content": "Page 494\n\nFull text content...",
  "word_count": 523,
  "page_range": [494],
  "is_range": false,
  "pages_retrieved": 1,
  "is_merged": false,
  "next_page": { "page_num": 495, "page_range": [495] },
  "prev_page": { "page_num": 493, "page_range": [493] },
  "related_pages": [
    { "chunk_idx": 120, "page_num": 315, "keywords": ["shared", "topic"] }
  ]
}
```

**Note on Merged Pages:** If page 2 was merged into pages 1-3 during indexing, querying page 2 will return the merged chunk with `page_range: [1, 2, 3]` and `is_merged: true`.

#### 4. `get_document_info` - Table of Contents & Statistics

Get the first N pages (typically Table of Contents) and document statistics.

**Parameters:**

- `doc_id` (str): Document identifier
- `max_pages` (int, default=20): Number of initial pages to return

**Example:**

```python
result = get_document_info(doc_id='core_spec', max_pages=20)
```

**Returns:**

```json
{
  "doc_id": "core_spec",
  "chunks": [
    { "chunk_idx": 0, "page_num": 1, "page_range": [1, 2, 3], "text": "..." },
    { "chunk_idx": 1, "page_num": 4, "page_range": [4], "text": "..." }
  ],
  "stats": {
    "total_chunks": 523,
    "merged_chunks": 45,
    "next_relationships": 522,
    "discusses_relationships": 1847,
    "total_relationships": 2369
  },
  "max_pages_returned": 20,
  "is_truncated": true
}
```

### MCP Resources

The server exposes **3 resources** for system information:

#### 1. `https://graphrag.db/schema/neo4j`

Neo4j graph schema information including:

- Node labels (`:Document`, `:Page`)
- Relationship types (`NEXT_PAGE`, `RELATED_TO`, `CONTAINS`)
- Property keys
- Node counts by label

#### 2. `https://graphrag.db/collection/qdrant`

Qdrant vector collection information:

- Collection name
- Vector count
- Vector dimensions (384)
- Distance metric (Cosine)

#### 3. `https://graphrag.db/documents/list`

List of all indexed documents with their IDs and sources.

## How It Works

### Page-Based Chunking with Smart Merging

The indexing process (`index_markdown.py`) uses an intelligent chunking strategy:

1. **Page Detection:** Splits documents at "Page N" markers
2. **Smart Merging:** Pages with < 50 words are automatically merged with adjacent pages
3. **Metadata Preservation:** Tracks original page numbers and ranges even after merging
4. **Quality Assurance:** Ensures all chunks meet minimum word threshold

**Example:**

```
Page 1 (30 words) →
Page 2 (25 words) → Merged into single chunk: pages [1, 2, 3]
Page 3 (40 words) →

Page 4 (150 words) → Standalone chunk: page [4]
```

### Graph Relationships

Three types of relationships connect pages within each document:

1. **`NEXT_PAGE`** - Sequential flow

   ```
   Page 1 -[NEXT_PAGE]-> Page 2 -[NEXT_PAGE]-> Page 3
   ```

2. **`RELATED_TO`** - Semantic similarity (cosine similarity > threshold)

   ```
   Page 5 -[RELATED_TO {keywords: [...], similarity: 0.87}]-> Page 89
   ```

3. **`CONTAINS`** - Document ownership
   ```
   Document -[CONTAINS]-> Page 1, Page 2, Page 3, ...
   ```

### Hybrid Search Process

1. **Vector Search:** Query → Embedding → Qdrant similarity search → Top K chunks
2. **Graph Expansion:** For each chunk, retrieve:
   - Sequential context (previous/next pages)
   - Semantically related pages within same document
3. **Enrichment:** Combine results with graph context for comprehensive answers

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to Neo4j or Qdrant

**Solutions:**

- Ensure Docker containers are running: `docker ps`
- Check if ports are available: `netstat -an | grep 7687` (Neo4j) or `netstat -an | grep 6333` (Qdrant)
- Restart containers: `docker-compose restart`
- Check logs: `docker-compose logs neo4j` or `docker-compose logs qdrant`

### Empty Search Results

**Problem:** Searches return no results

**Solutions:**

- Verify data is indexed: `uv run diagnose_data.py`
- Check document count in Neo4j: Visit `http://localhost:7474` (Neo4j Browser)
- Re-index documents: `uv run clear.py` then `uv run index_markdown.py`
- Ensure documents are in `specs/` directory

### Missing Dependencies

**Problem:** Import errors or missing packages

**Solutions:**

- Reinstall dependencies: `uv install`
- Check Python version: `python --version` (must be 3.12+)
- Verify uv is installed: `uv --version`

### Database Authentication

**Problem:** Neo4j authentication failed

**Solutions:**

- Verify credentials in `.env` file match Neo4j settings
- Default credentials: username=`neo4j`, password=`password`
- Reset Neo4j password via Neo4j Browser: `http://localhost:7474`

### Port Conflicts

**Problem:** Docker containers fail to start due to port conflicts

**Solutions:**

- Check what's using the ports:

  ```bash
  # Windows
  netstat -ano | findstr :7687
  netstat -ano | findstr :6333

  # Linux/macOS
  lsof -i :7687
  lsof -i :6333
  ```

- Stop conflicting services or change ports in `docker-compose.yml`

### MCP Server Not Detected

**Problem:** MCP client doesn't see the server

**Solutions:**

- Verify `mcp.json` path is correct for your OS
- Check JSON syntax is valid
- Ensure `uv` is in your system PATH
- Restart the MCP client completely
- Check server logs in `graphrag.log`

## Advanced Usage

### Custom Document Indexing

To index your own documents:

1. **Prepare documents:**
   - Place markdown files in `specs/` directory
   - Ensure page markers are present: `Page N` on standalone lines
   - Or modify `index_markdown.py` for different formats

2. **Adjust chunking parameters** in `index_markdown.py`:

   ```python
   MIN_WORDS = 50  # Minimum words per chunk
   SIMILARITY_THRESHOLD = 3  # For RELATED_TO relationships
   ```

3. **Run indexing:**
   ```bash
   uv run index_markdown.py
   ```

### Programmatic Usage

Use the tool directly in Python:

```python
from graphrag_mcp.documentation_tool import DocumentationGPTTool

tool = DocumentationGPTTool()

# Vector search
results = tool.search_documentation(
    query="authentication mechanisms",
    limit=5,
    doc_filter="core_spec"
)

# Hybrid search
results = tool.hybrid_search(
    query="API design patterns",
    limit=10,
    expand_context=True
)

# Get specific page
page = tool.get_page_content(
    doc_id="core_spec",
    start_page=494,
    end_page=500
)

# Get document info
info = tool.get_document_info(
    doc_id="application_spec",
    max_pages=20
)

# Clean up
tool.close()
```

### Querying Neo4j Directly

Access Neo4j Browser at `http://localhost:7474`:

```cypher
// Find all documents
MATCH (d:Document) RETURN d

// Find pages in a documentMATCH (d:Document {id: 'core_spec'})-[:CONTAINS]->(p:Page)
RETURN p.page_num, p.page_range, p.text
ORDER BY p.page_num

// Find semantically related pages
MATCH (p1:Page)-[r:RELATED_TO]->(p2:Page)
WHERE p1.doc_id = 'core_spec'
RETURN p1.page_num, p2.page_num, r.keywords, r.similarity
ORDER BY r.similarity DESC

// Find page sequence
MATCH path = (p:Page)-[:NEXT_PAGE*1..5]->(next:Page)
WHERE p.page_num = 1 AND p.doc_id = 'core_spec'
RETURN path
```

## Performance Considerations

- **Indexing Time:** ~1-2 seconds per page (depends on page size and merging)
- **Search Latency:**
  - Vector search: ~50-100ms for 5 results
  - Hybrid search: ~150-250ms (includes graph traversal)
  - Page retrieval: ~20-50ms
- **Memory Usage:**
  - Embedding model: ~100MB RAM
  - Neo4j: ~500MB-2GB (scales with data)
  - Qdrant: ~200MB-1GB (scales with vectors)

**Optimization Tips:**

- Use `doc_filter` to narrow search scope
- Adjust `limit` parameter based on needs
- Set `expand_context=False` for faster hybrid_search
- Index only necessary documents

## Contributing

Contributions are welcome! Here's how you can help:

1. **Report Bugs:** Open an issue with reproduction steps
2. **Suggest Features:** Describe your use case and proposed solution
3. **Submit Pull Requests:**
   - Fork the repository
   - Create a feature branch: `git checkout -b feature/amazing-feature`
   - Commit changes: `git commit -m 'Add amazing feature'`
   - Push to branch: `git push origin feature/amazing-feature`
   - Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/graphrag_mcp.git
cd graphrag_mcp

# Install with dev dependencies
uv install --dev

# Run tests
uv run pytest

# Run diagnostic checks
uv run diagnose_data.py
```

## License

MIT License

Copyright (c) 2025 AN-SWAPNIL

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Attribution & Acknowledgments

This project is a fork and significant extension of the original work by **Riley Lemm** ([rileylemm/graphrag_mcp](https://github.com/rileylemm/graphrag_mcp)).

**Enhancements in this fork:**

- Docker Compose setup for easy deployment
- Page-based chunking with smart merging algorithm
- Additional MCP tools (`get_page`, `get_document_info`)
- Document filtering capabilities
- Windows batch scripts for automation
- Comprehensive utility scripts (diagnose, test, clear)
- Extended documentation and examples
- VS Code MCP integration

**Original Concept:** Riley Lemm  
**Extended By:** AN-SWAPNIL ([GitHub](https://github.com/AN-SWAPNIL))

---

**Built with:**

- [Model Context Protocol](https://modelcontextprotocol.io/) - LLM integration framework
- [Neo4j](https://neo4j.com/) - Graph database
- [Qdrant](https://qdrant.tech/) - Vector database
- [Sentence Transformers](https://www.sbert.net/) - Embedding models
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
