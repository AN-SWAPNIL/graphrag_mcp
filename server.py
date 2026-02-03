from mcp.server.fastmcp import FastMCP
from graphrag_mcp.documentation_tool import DocumentationGPTTool

# Create an MCP server
mcp = FastMCP(
    "GraphRAG Documentation",
    dependencies=["neo4j", "qdrant-client", "sentence-transformers"],
)

# Initialize the documentation tool (vector + graph backend)
doc_tool = DocumentationGPTTool()

@mcp.tool()
def search_documentation(query: str, limit: int = 5, doc_filter: str = None) -> dict:
    """Search documentation using semantic vector search.
    
    Args:
        query: Natural language query to search in the indexed docs.
        limit: Max number of chunks to return.
        doc_filter: Optional document ID to filter results (e.g., 'application_spec', 'core_spec').
    
    Returns:
        Dict with `chunks`, each containing: doc, chunk_idx, page_num, page_range, text, score.
    """
    return doc_tool.search_documentation(query=query, limit=limit, doc_filter=doc_filter)

@mcp.tool()
def hybrid_search(query: str, limit: int = 5, doc_filter: str = None, expand_context: bool = True) -> dict:
    """Hybrid search combining vector search + intra-document graph context.
    
    Args:
        query: Natural language query.
        limit: Max number of seed chunks from vector search.
        doc_filter: Optional document ID to filter results (e.g., 'application_spec', 'core_spec').
        expand_context: If True, enrich each chunk with NEXT_PAGE / RELATED_TO context
                       from the Neo4j graph.
    
    Returns:
        Dict with `chunks`, where each chunk may contain:
        - related_next: Following pages in sequence
        - related_previous: Preceding pages in sequence
        - related_discussing: Semantically similar pages with shared keywords
    """
    return doc_tool.hybrid_search(query=query, limit=limit, doc_filter=doc_filter, expand_context=expand_context)

@mcp.tool()
def get_page(doc_id: str, start_page: int, end_page: int = None) -> dict:
    """Get the exact content of a specific page or page range.
    
    Works with merged pages - if page 2 was merged into pages 1-3,
    querying page 2 will return the merged chunk with all content.
    
    Args:
        doc_id: Document identifier (e.g., 'core_spec', 'application_spec')
        start_page: Starting page number to retrieve (e.g., 494)
        end_page: Optional ending page number for range retrieval (e.g., 500). 
                 If not provided, retrieves only start_page.
    
    Returns:
        Dict with:
        - content: Full page text (may include multiple pages if merged or range requested)
        - word_count: Total word count across all pages
        - page_range: List of page numbers retrieved
        - is_range: Boolean indicating if multiple pages were requested
        - pages_retrieved: Number of pages retrieved
        - info: Informational message about merged pages or range
        - next_page: Next chunk info (page_num and page_range)
        - prev_page: Previous chunk info (page_num and page_range)
        - related_pages: Semantically related pages with shared keywords
    
    Example:
        # Query single page
        get_page(doc_id='core_spec', start_page=494)
        
        # Query page range
        get_page(doc_id='core_spec', start_page=494, end_page=500)
        # Returns: content from pages 494-500 combined
        
        # Query page that was merged (e.g., page 2 in merged chunk 1-3)
        get_page(doc_id='core_spec', start_page=2)
        # Returns: page_range=[1,2,3], info="Page 2 is part of merged pages 1-3"
    """
    return doc_tool.get_page_content(doc_id, start_page, end_page)

@mcp.tool()
def get_document_info(doc_id: str) -> dict:
    """Get comprehensive information about a document.
    
    Args:
        doc_id: Document identifier (e.g., 'core_spec', 'application_spec')
    
    Returns:
        Dict with:
        - chunks: List of all page chunks with their page ranges
        - stats: Statistics including:
            - total_chunks: Total number of page chunks
            - merged_chunks: Number of chunks created from merging small pages
            - next_relationships: Sequential page links
            - discusses_relationships: Semantic similarity links
            - total_relationships: Sum of all relationships
    """
    return doc_tool.get_document_info(doc_id)

@mcp.resource("https://graphrag.db/schema/neo4j")
def get_graph_schema() -> str:
    """Return a simple schema summary from Neo4j (labels, rel types, property keys)."""
    try:
        schema: list[str] = []
        
        with doc_tool.neo4j_driver.session() as session:
            # Node labels
            result = session.run("""
                CALL db.labels() YIELD label
                RETURN collect(label) AS labels
            """)
            labels = result.single()["labels"]
            schema.append("Node Labels: " + ", ".join(labels))
            
            # Relationship types
            result = session.run("""
                CALL db.relationshipTypes() YIELD relationshipType
                RETURN collect(relationshipType) AS types
            """)
            rel_types = result.single()["types"]
            schema.append("Relationship Types: " + ", ".join(rel_types))
            
            # Property keys
            result = session.run("""
                CALL db.propertyKeys() YIELD propertyKey
                RETURN collect(propertyKey) AS keys
            """)
            prop_keys = result.single()["keys"]
            schema.append("Property Keys: " + ", ".join(prop_keys))
            
            # Node count by label
            schema.append("\nNode Counts:")
            for label in labels:
                count_query = f"MATCH (n:{label}) RETURN count(n) AS count"
                count = session.run(count_query).single()["count"]
                schema.append(f"  {label}: {count}")
        
        return "\n".join(schema)
    
    except Exception as e:  # pragma: no cover - diagnostic helper
        return f"Error retrieving graph schema: {str(e)}"

@mcp.resource("https://graphrag.db/collection/qdrant")
def get_vector_collection_info() -> str:
    """Return basic information about the Qdrant vector collection."""
    try:
        info: list[str] = []
        collection_info = doc_tool.qdrant_client.get_collection(doc_tool.qdrant_collection)
        
        # Vectors / points count (different client versions expose different attrs)
        vectors_count = 0
        if hasattr(collection_info, "vectors_count"):
            vectors_count = collection_info.vectors_count
        elif hasattr(collection_info, "points_count"):
            vectors_count = collection_info.points_count
        
        info.append(f"Collection: {doc_tool.qdrant_collection}")
        info.append(f"Vectors Count: {vectors_count}")
        
        # Optional: vector configuration
        try:
            if hasattr(collection_info, "config") and hasattr(collection_info.config, "params"):
                params = collection_info.config.params
                vector_size = getattr(params, "vector_size", "unknown")
                distance = getattr(params, "distance", "unknown")
                info.append(f"Vector Size: {vector_size}")
                info.append(f"Distance Function: {distance}")
        except Exception:
            info.append("Could not retrieve detailed vector configuration")
        
        return "\n".join(info)
    
    except Exception as e:  # pragma: no cover - diagnostic helper
        return f"Error retrieving vector collection info: {str(e)}"

@mcp.resource("https://graphrag.db/documents/list")
def get_documents_list() -> str:
    """List all indexed documents."""
    try:
        result = doc_tool.list_documents()
        
        if result['error']:
            return f"Error: {result['error']}"
        
        lines = ["Indexed Documents:"]
        for doc in result['documents']:
            lines.append(f"  • {doc['id']}: {doc['source']}")
        
        lines.append(f"\nTotal: {result['total']} documents")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"Error listing documents: {str(e)}"

if __name__ == "__main__":
    mcp.run()
