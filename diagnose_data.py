"""
✅ FIXED DIAGNOSIS SCRIPT - No Cypher syntax errors
"""

from qdrant_client import QdrantClient
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to services
qdrant = QdrantClient(host='localhost', port=6333)
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password'), encrypted=False)

print("\n" + "="*70)
print("🔍 DIAGNOSIS: Checking Qdrant & Neo4j Data")
print("="*70 + "\n")

# TEST 1: Check Qdrant payload structure
print("TEST 1️⃣ : Qdrant - First 5 vectors and their payloads")
print("-" * 70)
try:
    # Get some points from Qdrant
    points = qdrant.scroll(
        collection_name='document_chunks',
        limit=5,
        with_payload=True,
        with_vectors=False
    )
    
    for i, point in enumerate(points[0], 1):
        print(f"\n📦 Point {i} (ID: {point.id})")
        if point.payload:
            doc = point.payload.get('doc', '')
            chunk_idx = point.payload.get('chunk_idx', '')
            text = point.payload.get('text', '')[:60]
            print(f"   ✓ doc: '{doc}'")
            print(f"   ✓ chunk_idx: {chunk_idx}")
            print(f"   ✓ text: {text}...")
        else:
            print("   ⚠️  EMPTY PAYLOAD!")
    
except Exception as e:
    print(f"❌ Error: {e}")

# TEST 2: Check Neo4j documents
print("\n\nTEST 2️⃣ : Neo4j - Documents & their chunk counts")
print("-" * 70)
try:
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document)
            RETURN d.id as id, d.title as title, d.source as source
            ORDER BY id
        """)
        
        docs_found = 0
        for record in result:
            doc_id = record['id']
            if doc_id:  # Skip None entries
                # Count chunks for this doc
                chunk_result = session.run("""
                    MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(c:Chunk)
                    RETURN count(c) as count
                """, doc_id=doc_id)
                
                chunk_count = chunk_result.single()['count']
                print(f"\n📄 {doc_id}")
                print(f"   • Chunks: {chunk_count}")
                docs_found += 1
        
        print(f"\n✓ Total documents indexed: {docs_found}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# TEST 3: Check Neo4j chunk structure
print("\n\nTEST 3️⃣ : Neo4j - Sample chunks")
print("-" * 70)
try:
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Chunk)
            RETURN c.id as id, c.doc_id as doc_id, c.chunk_idx as idx
            LIMIT 3
        """)
        
        for i, record in enumerate(result, 1):
            chunk_id = record['id']
            doc_id = record['doc_id']
            idx = record['idx']
            
            print(f"\n🧩 Chunk {i}: {chunk_id}")
            print(f"   • doc_id: {doc_id}")
            print(f"   • chunk_idx: {idx}")
            
            # Count relationships FROM this chunk
            rel_result = session.run("""
                MATCH (c:Chunk {id: $chunk_id})-[r:NEXT]->()
                RETURN count(r) as next_count
            """, chunk_id=chunk_id)
            next_count = rel_result.single()['next_count']
            
            dis_result = session.run("""
                MATCH (c:Chunk {id: $chunk_id})-[r:DISCUSSES]->()
                RETURN count(r) as dis_count
            """, chunk_id=chunk_id)
            dis_count = dis_result.single()['dis_count']
            
            print(f"   • NEXT relationships: {next_count}")
            print(f"   • DISCUSSES relationships: {dis_count}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# TEST 4: Verify doc IDs match
print("\n\nTEST 4️⃣ : Verify Qdrant & Neo4j doc IDs match")
print("-" * 70)
try:
    # Get all unique docs from Qdrant
    points = qdrant.scroll(collection_name='document_chunks', limit=1000, with_payload=True)[0]
    qdrant_docs = set(p.payload.get('doc', '') for p in points if p.payload.get('doc'))
    
    print(f"\n✓ Qdrant unique docs: {qdrant_docs}")
    
    # Get docs from Neo4j
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document)
            WHERE d.id IS NOT NULL
            RETURN collect(d.id) as doc_ids
        """)
        
        neo4j_docs = set(result.single()['doc_ids'])
        print(f"✓ Neo4j documents: {neo4j_docs}")
        
        # Check if they match
        if qdrant_docs == neo4j_docs:
            print(f"\n✅ MATCH! Both have: {qdrant_docs}")
        else:
            print(f"\n⚠️ MISMATCH!")
            print(f"   In Qdrant but not Neo4j: {qdrant_docs - neo4j_docs}")
            print(f"   In Neo4j but not Qdrant: {neo4j_docs - qdrant_docs}")
    
except Exception as e:
    print(f"❌ Error: {e}")

# TEST 5: Verify data flow
print("\n\nTEST 5️⃣ : Test intra-doc context lookup")
print("-" * 70)
try:
    with driver.session() as session:
        result = session.run("""
            MATCH (c:Chunk)
            WHERE c.doc_id IS NOT NULL
            RETURN c.id as id, c.doc_id as doc_id, c.chunk_idx as idx
            LIMIT 1
        """)
        
        record = result.single()
        if record:
            chunk_id = record['id']
            doc_id = record['doc_id']
            idx = record['idx']
            
            print(f"\n✓ Testing with chunk: {chunk_id}")
            
            # Count NEXT relationships
            next_result = session.run("""
                MATCH (c:Chunk {id: $chunk_id})-[:NEXT]->()
                RETURN count(*) as count
            """, chunk_id=chunk_id)
            next_count = next_result.single()['count']
            
            # Count DISCUSSES relationships
            dis_result = session.run("""
                MATCH (c:Chunk {id: $chunk_id})-[:DISCUSSES]->()
                RETURN count(*) as count
            """, chunk_id=chunk_id)
            dis_count = dis_result.single()['count']
            
            print(f"✓ NEXT relationships: {next_count}")
            print(f"✓ DISCUSSES relationships: {dis_count}")
            
            if next_count > 0 and dis_count > 0:
                print(f"\n✅ Both relationship types working!")
        
except Exception as e:
    print(f"❌ Error: {e}")

driver.close()

print("\n" + "="*70)
print("✅ DIAGNOSIS COMPLETE!")
print("="*70 + "\n")
