"""
Helper script to run queries and create ground truth labels.
Run this interactively to review results and label them.
"""

import json
from pathlib import Path
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.core.collections import get_collection_manager
from src.retrieval.search import get_similarity_search


def run_query_for_labeling(query: str, query_id: str, limit: int = 10):
    """Run a query and return detailed results for manual labeling."""
    db = get_database()
    embedder = get_embedding_generator()
    collection_mgr = get_collection_manager(db)
    searcher = get_similarity_search(db, embedder, collection_mgr)

    results = searcher.search_chunks(
        query=query,
        limit=limit,
        collection_name="claude-agent-sdk",
        include_source=False
    )

    print(f"\n{'='*80}")
    print(f"Query ID: {query_id}")
    print(f"Query: {query}")
    print(f"{'='*80}\n")

    output = {
        'query_id': query_id,
        'query': query,
        'results': []
    }

    for i, r in enumerate(results, 1):
        print(f"[{i}] Similarity: {r.similarity:.3f} | Chunk {r.chunk_index}")
        print(f"    Source: {r.source_filename} (Doc ID: {r.source_document_id})")
        print(f"    Content: {r.content[:200]}...")
        print()

        output['results'].append({
            'rank': i,
            'chunk_id': r.chunk_id,
            'source_document_id': r.source_document_id,
            'source_filename': r.source_filename,
            'chunk_index': r.chunk_index,
            'similarity': float(r.similarity),
            'content_preview': r.content[:300],
            # To be filled in by manual review:
            'relevance': None  # 'highly_relevant', 'relevant', 'not_relevant'
        })

    return output


# Queries to label based on user's interests
QUERIES_TO_LABEL = [
    ('wf-01', 'Claude Code configuration options'),
    ('wf-03', 'GitHub Actions integration guide'),
    ('tech-03', 'implementing custom hooks for git operations'),
    ('abbr-01', 'MCP server setup'),
    ('abbr-02', 'SDK migration'),
    ('poor-01', 'how make agent work'),
    ('tech-02', 'differences between Claude Code and Claude Agent SDK'),
    ('custom-01', 'how to implement features using Claude Agent SDK'),
]


if __name__ == "__main__":
    all_query_results = []

    for query_id, query_text in QUERIES_TO_LABEL:
        result = run_query_for_labeling(query_text, query_id)
        all_query_results.append(result)

    # Save raw results for review
    output_file = Path("test-data/ground-truth-raw.json")
    with open(output_file, 'w') as f:
        json.dump(all_query_results, f, indent=2)

    print(f"\n\nRaw results saved to: {output_file}")
    print("\nNext: Review results and add 'relevance' labels to each result")
    print("Options: 'highly_relevant', 'relevant', 'not_relevant'")
