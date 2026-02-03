"""
EXTENDED: HybridRAG Documentation Search Tool
With document filtering and page navigation (supports merged pages)
"""

import os
import logging
from typing import Optional, Dict, Any, List
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='graphrag.log',
    filemode='a'
)

logger = logging.getLogger(__name__)

class DocumentationGPTTool:
    """HybridRAG tool for semantic + intra-document graph-based search with filtering."""
    
    def __init__(self):
        """Initialize connections to Neo4j, Qdrant, and embedding model."""
        # Neo4j config
        self.neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')
        self.neo4j_driver = None
        
        # Qdrant config
        self.qdrant_host = os.getenv('QDRANT_HOST', 'localhost')
        self.qdrant_port = int(os.getenv('QDRANT_PORT', 6333))
        self.qdrant_collection = os.getenv('QDRANT_COLLECTION', 'document_chunks')
        self.qdrant_client = None
        
        # Embedding model
        self.embedder = None
        self.model_name = 'all-MiniLM-L6-v2'
        
        self.initialize_connections()
    
    def initialize_connections(self):
        """Establish connections to all services."""
        # Connect to Neo4j
        try:
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password),
                encrypted=False
            )
            self.neo4j_driver.verify_connectivity()
            
            with self.neo4j_driver.session() as session:
                result = session.run("MATCH (d:Document) RETURN count(d) as doc_count")
                doc_count = result.single()['doc_count']
                logger.info(f"Neo4j connected. Documents: {doc_count}")
                print(f"Neo4j connected. Documents: {doc_count}")
        except Exception as e:
            logger.error(f"Neo4j connection failed: {str(e)}")
            print(f"Neo4j failed: {str(e)}")
            self.neo4j_driver = None
        
        # Connect to Qdrant
        try:
            self.qdrant_client = QdrantClient(
                host=self.qdrant_host,
                port=self.qdrant_port
            )
            collection_info = self.qdrant_client.get_collection(self.qdrant_collection)
            points_count = collection_info.points_count
            logger.info(f"Qdrant connected. Vectors: {points_count}")
            print(f"Qdrant connected. Vectors: {points_count}")
        except Exception as e:
            logger.error(f"Qdrant connection failed: {str(e)}")
            print(f"Qdrant failed: {str(e)}")
            self.qdrant_client = None
        
        # Load embedding model
        try:
            self.embedder = SentenceTransformer(self.model_name)
            logger.info(f"Embedding model loaded: {self.model_name}")
            print(f"Embedding model loaded: {self.model_name}")
        except Exception as e:
            logger.error(f"Embedding model failed: {str(e)}")
            print(f"Embedding model failed: {str(e)}")
    
    def search_documentation(self, query: str, limit: int = 5, doc_filter: Optional[str] = None) -> Dict[str, Any]:
        """Vector search - find semantically similar chunks with optional document filtering.
        
        Args:
            query: Search query
            limit: Max results to return
            doc_filter: Optional document ID to filter results (e.g., 'application_spec', 'core_spec')
        
        Returns:
            Dict with results
        """
        results = {
            'query': query,
            'chunks': [],
            'count': 0,
            'search_type': 'vector_search',
            'filter_applied': doc_filter is not None,
            'filter': doc_filter
        }
        
        if not self.embedder or not self.qdrant_client:
            results['error'] = 'Embedder or Qdrant not initialized'
            return results
        
        try:
            # Encode query
            query_embedding = self.embedder.encode(query).tolist()
            
            # Build filter if doc_filter provided
            query_filter = None
            if doc_filter:
                query_filter = {
                    "must": [
                        {
                            "key": "doc",
                            "match": {
                                "value": doc_filter
                            }
                        }
                    ]
                }
            
            # Search Qdrant
            search_results = self.qdrant_client.query_points(
                collection_name=self.qdrant_collection,
                query=query_embedding,
                query_filter=query_filter,
                limit=limit,
                with_payload=True
            )
            
            # Process results
            for result in search_results.points:
                payload = result.payload
                chunk_entry = {
                    'id': result.id,
                    'text': payload.get('text', ''),
                    'doc': payload.get('doc', ''),
                    'chunk_idx': payload.get('chunk_idx', 0),
                    'page_num': payload.get('page_num', 0),
                    'page_range': payload.get('page_range', []),
                    'is_merged': payload.get('is_merged', False),
                    'score': result.score
                }
                results['chunks'].append(chunk_entry)
            
            results['count'] = len(results['chunks'])
            logger.info(f"Vector search found {results['count']} chunks for query: {query}")
            if doc_filter:
                logger.info(f"  (filtered by document: {doc_filter})")
        
        except Exception as e:
            results['error'] = str(e)
            logger.error(f"Vector search failed: {str(e)}")
        
        return results
    
    def get_intra_document_context(self, doc_id: str, chunk_idx: int) -> Dict[str, Any]:
        """Find related chunks within the same document using INTRA-DOC relationships."""
        context = {
            'doc_id': doc_id,
            'chunk_idx': chunk_idx,
            'next_chunks': [],
            'discussing_chunks': [],
            'previous_chunks': [],
            'error': None
        }
        
        if not self.neo4j_driver:
            context['error'] = 'Neo4j not connected'
            return context
        
        try:
            with self.neo4j_driver.session() as session:
                # Find Page by chunk_idx (supports merged pages)
                result = session.run("""
                    MATCH (p:Page {doc_id: $doc_id, chunk_idx: $chunk_idx})
                    RETURN p.id as id, p.page_range_str as page_range_str
                """, doc_id=doc_id, chunk_idx=chunk_idx)
                
                rec = result.single()
                if not rec:
                    context['error'] = f'Chunk {chunk_idx} not found in {doc_id}'
                    return context
                
                page_id = rec['id']
                
                # Find NEXT pages (sequential within document)
                result = session.run("""
                    MATCH (p1:Page {id: $page_id})-[:NEXT_PAGE]->(p2:Page)
                    RETURN p2.id as id, p2.chunk_idx as idx, p2.text as text,
                           p2.page_range_str as page_range_str
                    LIMIT 5
                """, page_id=page_id)
                for rec in result:
                    context['next_chunks'].append({
                        'id': rec['id'],
                        'chunk_idx': rec['idx'],
                        'page_range': rec['page_range_str'],
                        'text': rec['text'][:200] if rec['text'] else 'N/A'
                    })
                
                # Find PREVIOUS pages (backward sequential)
                result = session.run("""
                    MATCH (p1:Page {id: $page_id})<-[:NEXT_PAGE]-(p2:Page)
                    RETURN p2.id as id, p2.chunk_idx as idx, p2.text as text,
                           p2.page_range_str as page_range_str
                    LIMIT 5
                """, page_id=page_id)
                for rec in result:
                    context['previous_chunks'].append({
                        'id': rec['id'],
                        'chunk_idx': rec['idx'],
                        'page_range': rec['page_range_str'],
                        'text': rec['text'][:200] if rec['text'] else 'N/A'
                    })
                
                # Find RELATED_TO pages (semantic similarity within document)
                result = session.run("""
                    MATCH (p1:Page {id: $page_id})-[r:RELATED_TO]->(p2:Page)
                    RETURN p2.id as id, p2.chunk_idx as idx, p2.text as text,
                           p2.page_range_str as page_range_str,
                           r.common_keywords as keywords, r.page_distance as distance
                    ORDER BY size(r.common_keywords) DESC
                    LIMIT 5
                """, page_id=page_id)
                for rec in result:
                    context['discussing_chunks'].append({
                        'id': rec['id'],
                        'chunk_idx': rec['idx'],
                        'page_range': rec['page_range_str'],
                        'text': rec['text'][:200] if rec['text'] else 'N/A',
                        'shared_keywords': rec['keywords'] or [],
                        'distance': rec['distance']
                    })
                
                logger.info(f"Found intra-doc context for chunk {chunk_idx} in {doc_id}")
        
        except Exception as e:
            context['error'] = str(e)
            logger.error(f"Intra-doc context failed: {str(e)}")
        
        return context
    
    def hybrid_search(self, query: str, limit: int = 5, doc_filter: Optional[str] = None, expand_context: bool = True) -> Dict[str, Any]:
        """Hybrid search: vector similarity + intra-document graph context with optional filtering.
        
        Args:
            query: Search query
            limit: Max results from vector search
            doc_filter: Optional document ID to filter results
            expand_context: Whether to expand with graph context
        
        Returns:
            Dict with enriched results
        """
        # Step 1: Vector search
        results = self.search_documentation(query, limit=limit, doc_filter=doc_filter)
        results['search_type'] = 'hybrid_search'
        results['expanded_with_context'] = False
        
        if not expand_context or not results.get('chunks'):
            return results
        
        # Step 2: Expand with graph context from intra-document relationships
        try:
            for chunk in results['chunks']:
                doc_id = chunk['doc']
                chunk_idx = chunk['chunk_idx']
                
                context = self.get_intra_document_context(doc_id, chunk_idx)
                
                chunk['related_next'] = context.get('next_chunks', [])
                chunk['related_previous'] = context.get('previous_chunks', [])
                chunk['related_discussing'] = context.get('discussing_chunks', [])
                chunk['context_error'] = context.get('error')
            
            results['expanded_with_context'] = True
            logger.info("Hybrid search expanded with intra-doc context")
        
        except Exception as e:
            logger.error(f"Hybrid search expansion failed: {str(e)}")
        
        return results
    
    def get_page_content(self, doc_id: str, start_page: int, end_page: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve complete content of a specific page or page range.
        Handles merged pages (e.g., if pages 1-3 merged, can query any of 1, 2, or 3).
        
        Args:
            doc_id: Document identifier (e.g., 'core_spec', 'application_spec')
            start_page: Starting page number to retrieve
            end_page: Optional ending page number for range retrieval. If None, retrieves only start_page.
        
        Returns:
            Dict with page content, metadata, and related pages
        """
        # Determine if this is a range request
        is_range_request = end_page is not None and end_page != start_page
        
        result = {
            'doc_id': doc_id,
            'start_page': start_page,
            'end_page': end_page if is_range_request else start_page,
            'content': None,
            'word_count': 0,
            'page_range': None,
            'is_range': is_range_request,
            'pages_retrieved': 0,
            'is_merged': False,
            'next_page': None,
            'prev_page': None,
            'related_pages': [],
            'error': None
        }
        
        if not self.neo4j_driver:
            result['error'] = 'Neo4j not connected'
            return result
        
        try:
            with self.neo4j_driver.session() as session:
                if is_range_request:
                    # Get all pages in the range
                    res = session.run("""
                        MATCH (p:Page {doc_id: $doc_id})
                        WHERE ANY(page IN p.page_range WHERE page >= $start_page AND page <= $end_page)
                        RETURN p.text as text, 
                               p.word_count as word_count, 
                               p.id as id,
                               p.page_range as page_range,
                               p.page_range_str as page_range_str,
                               p.is_merged as is_merged,
                               p.chunk_idx as chunk_idx
                        ORDER BY p.chunk_idx
                    """, doc_id=doc_id, start_page=start_page, end_page=end_page)
                    
                    pages = list(res)
                    if not pages:
                        result['error'] = f'No pages found in range {start_page}-{end_page} in {doc_id}'
                        return result
                    
                    # Combine content from all pages
                    combined_content = []
                    total_word_count = 0
                    all_pages = set()
                    first_page_id = None
                    last_page_id = None
                    
                    for idx, rec in enumerate(pages):
                        if idx == 0:
                            first_page_id = rec['id']
                        if idx == len(pages) - 1:
                            last_page_id = rec['id']
                        
                        page_range_str = rec['page_range_str']
                        combined_content.append(f"\n--- Pages {page_range_str} ---\n")
                        combined_content.append(rec['text'] or '')
                        total_word_count += rec['word_count'] or 0
                        all_pages.update(rec['page_range'])
                    
                    result['content'] = '\n'.join(combined_content)
                    result['word_count'] = total_word_count
                    result['page_range'] = sorted(list(all_pages))
                    result['pages_retrieved'] = len(pages)
                    result['info'] = f"Retrieved {len(pages)} page chunk(s) covering pages {start_page}-{end_page}"
                    
                    # Use first and last page for navigation
                    page_id = first_page_id
                    last_page_for_next = last_page_id
                    
                else:
                    # Single page retrieval (original behavior)
                    res = session.run("""
                        MATCH (p:Page {doc_id: $doc_id})
                        WHERE $start_page IN p.page_range
                        RETURN p.text as text, 
                               p.word_count as word_count, 
                               p.id as id,
                               p.page_range as page_range,
                               p.page_range_str as page_range_str,
                               p.is_merged as is_merged
                    """, doc_id=doc_id, start_page=start_page)
                    
                    rec = res.single()
                    if not rec:
                        result['error'] = f'Page {start_page} not found in {doc_id}'
                        return result
                    
                    result['content'] = rec['text']
                    result['word_count'] = rec['word_count']
                    result['page_range'] = rec['page_range']
                    result['is_merged'] = rec['is_merged']
                    result['pages_retrieved'] = 1
                    page_id = rec['id']
                    last_page_for_next = page_id
                    
                    # Add info message if page was part of merged chunk
                    if result['is_merged']:
                        result['info'] = f"Page {start_page} is part of merged pages {rec['page_range_str']}"
                
                # Get next page (next chunk's first page) - use last page if range
                res = session.run("""
                    MATCH (p1:Page {id: $page_id})-[:NEXT_PAGE]->(p2:Page)
                    RETURN p2.page_num as page_num, p2.page_range_str as page_range_str
                """, page_id=last_page_for_next)
                rec = res.single()
                if rec:
                    result['next_page'] = {
                        'page_num': rec['page_num'],
                        'page_range': rec['page_range_str']
                    }
                
                # Get previous page (previous chunk's first page)
                res = session.run("""
                    MATCH (p1:Page {id: $page_id})<-[:NEXT_PAGE]-(p2:Page)
                    RETURN p2.page_num as page_num, p2.page_range_str as page_range_str
                """, page_id=page_id)
                rec = res.single()
                if rec:
                    result['prev_page'] = {
                        'page_num': rec['page_num'],
                        'page_range': rec['page_range_str']
                    }
                
                # Get related pages (semantic similarity)
                res = session.run("""
                    MATCH (p1:Page {id: $page_id})-[r:RELATED_TO]->(p2:Page)
                    RETURN p2.page_num as page_num, 
                           p2.page_range_str as page_range_str,
                           r.common_keywords as keywords
                    ORDER BY size(r.common_keywords) DESC
                    LIMIT 5
                """, page_id=page_id)
                for rec in res:
                    result['related_pages'].append({
                        'page_num': rec['page_num'],
                        'page_range': rec['page_range_str'],
                        'shared_keywords': rec['keywords']
                    })
                
                if is_range_request:
                    logger.info(f"Retrieved page range {start_page}-{end_page} from {doc_id}")
                else:
                    logger.info(f"Retrieved page {start_page} from {doc_id}")
        
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Get page failed: {str(e)}")
        
        return result
    
    def get_document_info(self, doc_id: str) -> Dict[str, Any]:
        """Get all chunks from a document and intra-doc relationship stats."""
        result = {
            'doc_id': doc_id,
            'chunks': [],
            'stats': {
                'total_chunks': 0,
                'merged_chunks': 0,
                'next_relationships': 0,
                'discusses_relationships': 0,
                'total_relationships': 0
            },
            'error': None
        }
        
        if not self.neo4j_driver:
            result['error'] = 'Neo4j not connected'
            return result
        
        try:
            with self.neo4j_driver.session() as session:
                # Get all pages
                res = session.run("""
                    MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(p:Page)
                    RETURN p.id as id, p.chunk_idx as idx, p.text as text,
                           p.page_range_str as page_range_str, p.is_merged as is_merged
                    ORDER BY idx
                """, doc_id=doc_id)
                
                merged_count = 0
                for rec in res:
                    result['chunks'].append({
                        'id': rec['id'],
                        'chunk_idx': rec['idx'],
                        'page_range': rec['page_range_str'],
                        'is_merged': rec['is_merged'],
                        'text': rec['text'][:150] if rec['text'] else 'N/A'
                    })
                    if rec['is_merged']:
                        merged_count += 1
                
                result['stats']['total_chunks'] = len(result['chunks'])
                result['stats']['merged_chunks'] = merged_count
                
                # Count NEXT_PAGE relationships
                res = session.run("""
                    MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(p:Page)
                    MATCH (p)-[:NEXT_PAGE]->()
                    RETURN count(*) as count
                """, doc_id=doc_id)
                rec = res.single()
                if rec:
                    result['stats']['next_relationships'] = rec['count']
                
                # Count RELATED_TO relationships
                res = session.run("""
                    MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(p:Page)
                    MATCH (p)-[:RELATED_TO]->()
                    RETURN count(*) as count
                """, doc_id=doc_id)
                rec = res.single()
                if rec:
                    result['stats']['discusses_relationships'] = rec['count']
                
                result['stats']['total_relationships'] = (
                    result['stats']['next_relationships'] +
                    result['stats']['discusses_relationships']
                )
                
                logger.info(f"Got info for document {doc_id}")
        
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Document info failed: {str(e)}")
        
        return result
    
    def list_documents(self) -> Dict[str, Any]:
        """List all indexed documents."""
        result = {
            'documents': [],
            'total': 0,
            'error': None
        }
        
        if not self.neo4j_driver:
            result['error'] = 'Neo4j not connected'
            return result
        
        try:
            with self.neo4j_driver.session() as session:
                res = session.run("""
                    MATCH (d:Document)
                    RETURN d.id as id, d.source as source, d.title as title
                    ORDER BY id
                """)
                
                for rec in res:
                    result['documents'].append({
                        'id': rec['id'],
                        'source': rec['source'],
                        'title': rec['title']
                    })
                
                result['total'] = len(result['documents'])
                logger.info(f"Listed {result['total']} documents")
        
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"List documents failed: {str(e)}")
        
        return result
    
    def close(self):
        """Close all connections."""
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("Neo4j connection closed")
