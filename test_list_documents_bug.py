"""
Test script to verify list_documents collection filtering.

This tests whether list_documents properly filters by collection_name.
"""
import asyncio
from src.core.database import get_database
from src.core.collections import get_collection_manager
from src.mcp.tools import list_documents_impl

async def test_list_documents():
    db = get_database()
    coll_mgr = get_collection_manager(db)

    print("=" * 80)
    print("Testing list_documents with collection filter")
    print("=" * 80)

    # Test 1: List documents in wikipedia-quantum-computing collection
    print("\nTest 1: List documents in 'wikipedia-quantum-computing' collection")
    result = list_documents_impl(
        db=db,
        coll_mgr=coll_mgr,
        collection_name="wikipedia-quantum-computing",
        limit=50,
        offset=0,
        include_details=True
    )

    print(f"\nTotal documents found: {result['total_count']}")
    print(f"Returned: {result['returned_count']}")
    print("\nDocuments:")
    for doc in result['documents']:
        print(f"  ID {doc['id']}: {doc['filename']}")
        print(f"    Collections: {doc.get('collections', [])}")
        print(f"    Chunks: {doc['chunk_count']}")

    # Test 2: Verify doc 297 is ONLY in wikipedia-quantum-computing
    print("\n" + "=" * 80)
    print("Test 2: Verify doc 297 collection membership")
    print("=" * 80)

    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT c.name
            FROM collections c
            JOIN chunk_collections cc ON cc.collection_id = c.id
            JOIN document_chunks dc ON dc.id = cc.chunk_id
            WHERE dc.source_document_id = 297
        """)
        collections_297 = [row[0] for row in cur.fetchall()]
        print(f"\nDoc 297 belongs to collections: {collections_297}")

    # Test 3: Check what list_documents returns for other docs
    print("\n" + "=" * 80)
    print("Test 3: Check docs 296, 293 - should NOT be in wikipedia-quantum-computing")
    print("=" * 80)

    for doc_id in [296, 293]:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT c.name
                FROM collections c
                JOIN chunk_collections cc ON cc.collection_id = c.id
                JOIN document_chunks dc ON dc.id = cc.chunk_id
                WHERE dc.source_document_id = %s
            """, (doc_id,))
            collections = [row[0] for row in cur.fetchall()]
            print(f"\nDoc {doc_id} belongs to collections: {collections}")

if __name__ == "__main__":
    asyncio.run(test_list_documents())
