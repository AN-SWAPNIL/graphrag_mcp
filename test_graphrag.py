"""
Quick Test Script for HybridRAG Tool
Run with: python test_graphrag.py
"""

from graphrag_mcp.documentation_tool import DocumentationGPTTool

print("\n" + "="*70)
print("🚀 QUICK TEST: HybridRAG Tool with Intra-Document Relationships")
print("="*70 + "\n")

tool = DocumentationGPTTool()

# TEST 1: Vector Search
print("TEST 1️⃣ : Vector Search - 'authentication'")
print("-" * 70)
r = tool.search_documentation('authentication')
print(f"✅ Found {r['count']} chunks\n")
if r['chunks']:
    chunk = r['chunks'][0]
    print(f"   Top result:")
    print(f"   • Doc: {chunk['doc']}")
    print(f"   • Chunk: {chunk['chunk_idx']}")
    print(f"   • Score: {chunk['score']:.3f}")
    print(f"   • Text: {chunk['text'][:100]}...\n")

# TEST 2: Hybrid Search
print("TEST 2️⃣ : Hybrid Search - 'API endpoints'")
print("-" * 70)
r = tool.hybrid_search('API endpoints', limit=2, expand_context=True)
print(f"✅ Found {r['count']} chunks")
print(f"✅ Expanded with context: {r['expanded_with_context']}\n")
if r['chunks']:
    chunk = r['chunks'][0]
    print(f"   Top result:")
    print(f"   • Doc: {chunk['doc']}, Chunk: {chunk['chunk_idx']}")
    print(f"   • Next chunks: {len(chunk.get('related_next', []))}")
    print(f"   • Discussing chunks: {len(chunk.get('related_discussing', []))}\n")

# TEST 3: Intra-Doc Context
print("TEST 3️⃣ : Intra-Document Context")
print("-" * 70)
if r['chunks']:
    first = r['chunks'][0]
    context = tool.get_intra_document_context(first['doc'], first['chunk_idx'])
    print(f"✅ Context for chunk {first['chunk_idx']} in {first['doc']}:\n")
    print(f"   • NEXT chunks: {len(context['next_chunks'])}")
    print(f"   • PREVIOUS chunks: {len(context['previous_chunks'])}")
    print(f"   • DISCUSSING chunks: {len(context['discussing_chunks'])}\n")
    
    if context['discussing_chunks']:
        dc = context['discussing_chunks'][0]
        print(f"   Sample DISCUSSING chunk:")
        print(f"   • Chunk {dc['chunk_idx']}: {dc['text'][:80]}...")
        print(f"   • Shared keywords: {dc['shared_keywords'][:3]}\n")

# TEST 4: Document Info
print("TEST 4️⃣ : Document Statistics")
print("-" * 70)
docs = tool.list_documents()
print(f"✅ Documents found: {docs['total']}\n")
if docs['documents']:
    for doc in docs['documents'][:3]:  # Show first 3
        info = tool.get_document_info(doc['id'])
        print(f"   📄 {doc['id']}:")
        print(f"      • Chunks: {info['stats']['total_chunks']}")
        print(f"      • NEXT relationships: {info['stats']['next_relationships']}")
        print(f"      • DISCUSSES relationships: {info['stats']['discusses_relationships']}")
        print(f"      • Total relationships: {info['stats']['total_relationships']}\n")

tool.close()
print("="*70)
print("✅ ALL TESTS COMPLETE!")
print("="*70 + "\n")
