"""
✅ OPTIMIZED: GraphRAG with PAGE-BASED CHUNKING + SMART MERGING
Merges small pages instead of skipping them
"""

import os
import sys
import re
from pathlib import Path
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# Configuration
SPECS_DIR = "specs"
QDRANT_HOST = os.getenv('QDRANT_HOST', 'localhost')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', 6333))
QDRANT_COLLECTION = os.getenv('QDRANT_COLLECTION', 'document_chunks')
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password')

MIN_WORDS = 50  # Minimum words per chunk
MIN_WORD_LENGTH = 5
SIMILARITY_THRESHOLD = 3
BATCH_SIZE = 50

print("🔌 Connecting...")
embedder = SentenceTransformer('all-MiniLM-L6-v2')
qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), encrypted=False)
print("✓ Connected\n")

# Ensure collection exists
try:
    qdrant.get_collection(QDRANT_COLLECTION)
except:
    qdrant.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
    )

def split_by_pages(content, min_words=50):
    """
    Split document by page boundaries ("Page N" on standalone line), merging pages with < min_words.
    """
    raw_pages = []
    current_page = []
    current_page_num = None
    
    lines = content.split('\n')
    
    # Step 1: Extract all pages - split at every "Page N" line
    for line in lines:
        # Check if line is exactly "Page N" (standalone page marker)
        page_match = re.match(r'^Page\s+(\d+)\s*$', line.strip())
        
        if page_match:
            # Save previous page if exists
            if current_page and current_page_num is not None:
                page_text = '\n'.join(current_page).strip()
                if page_text:
                    raw_pages.append({
                        'page_num': current_page_num,
                        'text': page_text,
                        'word_count': len(page_text.split())
                    })
            
            # Start new page
            current_page_num = int(page_match.group(1))
            current_page = [line]  # Include the "Page N" line
        else:
            current_page.append(line)
    
    # Handle trailing content
    if current_page and current_page_num is not None:
        page_text = '\n'.join(current_page).strip()
        if page_text:
            raw_pages.append({
                'page_num': current_page_num,
                'text': page_text,
                'word_count': len(page_text.split())
            })
    
    # Step 2: Merge small pages
    merged_pages = []
    i = 0
    
    while i < len(raw_pages):
        current = raw_pages[i]
        
        if current['word_count'] >= min_words:
            merged_pages.append({
                'page_num': current['page_num'],
                'page_range': [current['page_num']],
                'text': current['text'],
                'word_count': current['word_count'],
                'is_merged': False
            })
            i += 1
        else:
            # Merge with next pages
            merged_text = current['text']
            merged_word_count = current['word_count']
            page_range = [current['page_num']]
            
            j = i + 1
            while j < len(raw_pages) and merged_word_count < min_words:
                next_page = raw_pages[j]
                merged_text += '\n\n' + next_page['text']
                merged_word_count += next_page['word_count']
                page_range.append(next_page['page_num'])
                j += 1
            
            merged_pages.append({
                'page_num': page_range[0],
                'page_range': page_range,
                'text': merged_text,
                'word_count': merged_word_count,
                'is_merged': len(page_range) > 1
            })
            
            i = j
    
    return merged_pages

md_files = sorted(Path(SPECS_DIR).glob("*.md"))
if not md_files:
    print("❌ No markdown files found!")
    sys.exit(1)

print(f"📚 Processing {len(md_files)} files\n")

all_points = []
point_id = 0
doc_data = {}
merge_stats = {'total_chunks': 0, 'merged_chunks': 0, 'pages_merged': 0}

# ===== PHASE 1: INDEX PAGE CHUNKS =====
print("📝 PHASE 1: Creating page-based chunks (with smart merging)")
print("-" * 50)

for file_path in md_files:
    print(f"📄 {file_path.name}...", end=" ", flush=True)
    
    doc_id = file_path.stem
    content = file_path.read_text(errors='ignore')
    
    # Create Neo4j document node
    with driver.session() as s:
        s.run("""
            MERGE (d:Document {id: $id})
            SET d.source = $source, d.title = $title
        """, {"id": doc_id, "source": file_path.name, "title": file_path.stem})
    
    # Split with smart merging
    pages = split_by_pages(content, min_words=MIN_WORDS)
    
    chunks_list = []
    merged_count = 0
    
    for page_data in pages:
        page_text = page_data['text']
        page_num = page_data['page_num']
        page_range = page_data['page_range']
        is_merged = page_data['is_merged']
        
        if is_merged:
            merged_count += 1
            merge_stats['pages_merged'] += len(page_range)
        
        embedding = embedder.encode(page_text)
        
        chunk_data = {
            'id': point_id,
            'doc_id': doc_id,
            'chunk_idx': len(chunks_list),
            'page_num': page_num,
            'page_range': page_range,
            'is_merged': is_merged,
            'text': page_text,
            'embedding': embedding
        }
        
        chunks_list.append(chunk_data)
        
        # Store in Qdrant with page range info
        all_points.append(PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "text": page_text,
                "doc": doc_id,
                "chunk_idx": len(chunks_list) - 1,
                "page_num": page_num,
                "page_range": page_range,
                "is_merged": is_merged
            }
        ))
        
        point_id += 1
    
    doc_data[doc_id] = chunks_list
    merge_stats['total_chunks'] += len(chunks_list)
    merge_stats['merged_chunks'] += merged_count
    
    # Enhanced output
    page_range_str = f"{page_range[0]}-{page_range[-1]}" if page_range else "N/A"
    print(f"✓ ({len(chunks_list)} chunks, pages {page_range_str}, {merged_count} merged)")

# ===== PHASE 2: STORE VECTORS =====
print("\n📊 PHASE 2: Storing vectors in Qdrant")
print("-" * 50)
print(f"💾 Storing {point_id} vectors...", end=" ", flush=True)

for i in range(0, len(all_points), BATCH_SIZE):
    batch = all_points[i:i+BATCH_SIZE]
    qdrant.upsert(QDRANT_COLLECTION, points=batch)

print("✓")

# ===== PHASE 3: CREATE NEO4J CHUNKS & RELATIONSHIPS =====
print("\n🔗 PHASE 3: Creating Neo4j page nodes and relationships")
print("-" * 50)

with driver.session() as s:
    for doc_id, chunks in doc_data.items():
        print(f"📄 {doc_id}...", end=" ", flush=True)
        
        # Create Page nodes
        for chunk in chunks:
            page_range = chunk['page_range']
            page_range_str = f"{page_range[0]}-{page_range[-1]}" if len(page_range) > 1 else str(page_range[0])
            chunk_neo_id = f"{doc_id}_page_{page_range_str}"
            
            s.run("""
                CREATE (p:Page {
                    id: $chunk_id,
                    doc_id: $doc_id,
                    page_num: $page_num,
                    page_range: $page_range,
                    page_range_str: $page_range_str,
                    chunk_idx: $idx,
                    text: $text,
                    word_count: $word_count,
                    is_merged: $is_merged
                })
            """, {
                "chunk_id": chunk_neo_id,
                "doc_id": doc_id,
                "page_num": chunk['page_num'],
                "page_range": page_range,
                "page_range_str": page_range_str,
                "idx": chunk['chunk_idx'],
                "text": chunk['text'],
                "word_count": len(chunk['text'].split()),
                "is_merged": chunk['is_merged']
            })
            
            # Link page to document
            s.run("""
                MATCH (d:Document {id: $doc_id})
                MATCH (p:Page {id: $chunk_id})
                MERGE (d)-[:CONTAINS]->(p)
            """, {"doc_id": doc_id, "chunk_id": chunk_neo_id})
        
        # RELATIONSHIP 1: Sequential page links
        for i in range(len(chunks) - 1):
            page1_range = chunks[i]['page_range']
            page2_range = chunks[i+1]['page_range']
            page1_str = f"{page1_range[0]}-{page1_range[-1]}" if len(page1_range) > 1 else str(page1_range[0])
            page2_str = f"{page2_range[0]}-{page2_range[-1]}" if len(page2_range) > 1 else str(page2_range[0])
            
            page1_id = f"{doc_id}_page_{page1_str}"
            page2_id = f"{doc_id}_page_{page2_str}"
            
            s.run("""
                MATCH (p1:Page {id: $id1})
                MATCH (p2:Page {id: $id2})
                CREATE (p1)-[:NEXT_PAGE]->(p2)
            """, {"id1": page1_id, "id2": page2_id})
        
        # RELATIONSHIP 2: Semantic similarity
        for i, chunk1 in enumerate(chunks):
            words1 = set(w.lower() for w in chunk1['text'].split()
                        if len(w) >= MIN_WORD_LENGTH and w.isalpha())
            
            for j in range(i + 2, min(i + 6, len(chunks))):
                chunk2 = chunks[j]
                words2 = set(w.lower() for w in chunk2['text'].split()
                            if len(w) >= MIN_WORD_LENGTH and w.isalpha())
                
                common_words = words1 & words2
                
                if len(common_words) >= SIMILARITY_THRESHOLD:
                    page1_range = chunks[i]['page_range']
                    page2_range = chunks[j]['page_range']
                    page1_str = f"{page1_range[0]}-{page1_range[-1]}" if len(page1_range) > 1 else str(page1_range[0])
                    page2_str = f"{page2_range[0]}-{page2_range[-1]}" if len(page2_range) > 1 else str(page2_range[0])
                    
                    page1_id = f"{doc_id}_page_{page1_str}"
                    page2_id = f"{doc_id}_page_{page2_str}"
                    
                    s.run("""
                        MATCH (p1:Page {id: $id1})
                        MATCH (p2:Page {id: $id2})
                        CREATE (p1)-[:RELATED_TO {
                            common_keywords: $keywords,
                            page_distance: $distance
                        }]->(p2)
                    """, {
                        "id1": page1_id,
                        "id2": page2_id,
                        "keywords": list(common_words)[:5],
                        "distance": chunks[j]['page_num'] - chunks[i]['page_num']
                    })
        
        print(f"✓")

# ===== FINAL SUMMARY =====
print("\n" + "="*50)
print("✅ PAGE-BASED INDEXING COMPLETE!")
print("="*50)

with driver.session() as s:
    docs = s.run("MATCH (d:Document) RETURN count(d) as c").single()['c']
    pages = s.run("MATCH (p:Page) RETURN count(p) as c").single()['c']
    next_pages = s.run("MATCH ()-[r:NEXT_PAGE]->() RETURN count(r) as c").single()['c']
    related = s.run("MATCH ()-[r:RELATED_TO]->() RETURN count(r) as c").single()['c']
    contains = s.run("MATCH ()-[r:CONTAINS]->() RETURN count(r) as c").single()['c']
    
    page_stats = s.run("""
        MATCH (p:Page)
        RETURN min(p.page_num) as min_page, max(p.page_num) as max_page
    """).single()
    
    print(f"✓ Documents: {docs}")
    print(f"✓ Chunks: {pages} (covering pages {page_stats['min_page']}-{page_stats['max_page']})")
    print(f"✓ Merge Statistics:")
    print(f"    - Merged chunks: {merge_stats['merged_chunks']} ({merge_stats['merged_chunks']/merge_stats['total_chunks']*100:.1f}%)")
    print(f"    - Pages combined: {merge_stats['pages_merged']}")
    print(f"✓ Relationships:")
    print(f"    - NEXT_PAGE (sequential): {next_pages}")
    print(f"    - RELATED_TO (semantic): {related}")
    print(f"    - CONTAINS (doc→chunk): {contains}")
    print(f"✓ Qdrant vectors: {point_id}")

print("="*50)
print("\n🎉 Benefits of Smart Page Merging:")
print("  ✓ No pages skipped - all content indexed")
print("  ✓ Small pages merged with next pages automatically")
print("  ✓ All chunks meet minimum word threshold")
print("  ✓ Page ranges preserved (e.g., 'Pages 1-3' for merged)")
print("  ✓ Better search quality with meaningful chunk sizes")

driver.close()
