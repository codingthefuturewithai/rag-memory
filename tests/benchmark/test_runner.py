"""
Baseline Test Runner for RAG Optimization Benchmarking

This script runs all test queries against the current search implementation
and captures detailed metrics for comparison across optimization phases.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import yaml

from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.core.collections import get_collection_manager
from src.retrieval.search import get_similarity_search

# Import metrics module
try:
    from tests.benchmark.metrics import calculate_all_metrics, format_metrics_report, load_ground_truth
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False


def load_test_queries() -> List[Dict[str, Any]]:
    """Load test queries from YAML file."""
    queries_file = Path(__file__).parent.parent.parent / "test-data" / "test-queries.yaml"
    with open(queries_file, 'r') as f:
        data = yaml.safe_load(f)
    return data['queries']


def run_baseline_search(query: str, collection: str = "claude-agent-sdk", limit: int = 5) -> Dict[str, Any]:
    """
    Run a single search query and capture results.

    Args:
        query: Search query string
        collection: Collection name to search
        limit: Number of results to return

    Returns:
        Dictionary with query results and metadata
    """
    db = get_database()
    embedder = get_embedding_generator()
    collection_mgr = get_collection_manager(db)
    searcher = get_similarity_search(db, embedder, collection_mgr)

    start_time = time.time()

    try:
        results = searcher.search_chunks(
            query=query,
            limit=limit,
            threshold=None,  # No threshold filtering for baseline
            collection_name=collection,
            include_source=False  # Faster without source content
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Extract key information from results
        processed_results = []
        for r in results:
            processed_results.append({
                'chunk_id': r.chunk_id,
                'source_document_id': r.source_document_id,
                'source_filename': r.source_filename,
                'chunk_index': r.chunk_index,
                'similarity': float(r.similarity),
                'content_preview': r.content[:200] if len(r.content) > 200 else r.content,
                'content_length': len(r.content)
            })

        return {
            'success': True,
            'query': query,
            'num_results': len(results),
            'results': processed_results,
            'latency_ms': round(elapsed_ms, 2),
            'error': None
        }

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            'success': False,
            'query': query,
            'num_results': 0,
            'results': [],
            'latency_ms': round(elapsed_ms, 2),
            'error': str(e)
        }


def run_baseline_benchmark(output_dir: str = "test-results") -> str:
    """
    Run full baseline benchmark suite.

    Args:
        output_dir: Directory to save results

    Returns:
        Path to results JSON file
    """
    print("=" * 80)
    print("BASELINE BENCHMARK - RAG Search Optimization Testing")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Load test queries
    test_queries = load_test_queries()
    print(f"Loaded {len(test_queries)} test queries")

    # Load ground truth if available
    ground_truth = None
    if METRICS_AVAILABLE:
        try:
            ground_truth = load_ground_truth()
            print(f"Loaded ground truth labels for evaluation")
        except Exception as e:
            print(f"Warning: Could not load ground truth: {e}")
    print()

    # Run each query
    all_results = []
    for i, query_spec in enumerate(test_queries, 1):
        query_id = query_spec['id']
        query_text = query_spec['query']
        category = query_spec['category']

        print(f"[{i}/{len(test_queries)}] {query_id} ({category}): {query_text}")

        result = run_baseline_search(query_text)

        # Add metadata from query spec
        result['query_id'] = query_id
        result['category'] = category
        result['expected_benefit'] = query_spec['expected_benefit']
        result['description'] = query_spec['description']

        # Calculate evaluation metrics if ground truth available
        if result['success'] and METRICS_AVAILABLE and ground_truth:
            metrics = calculate_all_metrics(result['results'], query_id, ground_truth)
            result['metrics'] = metrics
        else:
            result['metrics'] = None

        all_results.append(result)

        # Print quick summary
        if result['success']:
            print(f"   ✓ Found {result['num_results']} results in {result['latency_ms']:.1f}ms")
            if result['num_results'] > 0:
                print(f"   Top score: {result['results'][0]['similarity']:.3f}")

            # Print evaluation metrics if available
            if result.get('metrics') and result['metrics'].get('has_ground_truth'):
                print(format_metrics_report(result['metrics']))
        else:
            print(f"   ✗ Error: {result['error']}")
        print()

    # Calculate summary statistics
    successful_queries = [r for r in all_results if r['success']]

    summary = {
        'total_queries': len(test_queries),
        'successful_queries': len(successful_queries),
        'failed_queries': len(test_queries) - len(successful_queries),
        'avg_latency_ms': round(sum(r['latency_ms'] for r in successful_queries) / len(successful_queries), 2) if successful_queries else 0,
        'avg_results_per_query': round(sum(r['num_results'] for r in successful_queries) / len(successful_queries), 2) if successful_queries else 0,
        'avg_top_similarity': round(sum(r['results'][0]['similarity'] for r in successful_queries if r['num_results'] > 0) / len([r for r in successful_queries if r['num_results'] > 0]), 3) if any(r['num_results'] > 0 for r in successful_queries) else 0,
        'by_category': {}
    }

    # Add evaluation metrics to summary if available
    queries_with_metrics = [r for r in successful_queries if r.get('metrics') and r['metrics'].get('has_ground_truth')]
    if queries_with_metrics:
        summary['evaluation_metrics'] = {
            'queries_evaluated': len(queries_with_metrics),
            'avg_recall@5_any': round(sum(r['metrics']['recall@5_any'] for r in queries_with_metrics) / len(queries_with_metrics), 3),
            'avg_recall@5_high': round(sum(r['metrics']['recall@5_high'] for r in queries_with_metrics) / len(queries_with_metrics), 3),
            'avg_precision@5_any': round(sum(r['metrics']['precision@5_any'] for r in queries_with_metrics) / len(queries_with_metrics), 3),
            'avg_precision@5_high': round(sum(r['metrics']['precision@5_high'] for r in queries_with_metrics) / len(queries_with_metrics), 3),
            'avg_mrr_any': round(sum(r['metrics']['mrr_any'] for r in queries_with_metrics) / len(queries_with_metrics), 3),
            'avg_mrr_high': round(sum(r['metrics']['mrr_high'] for r in queries_with_metrics) / len(queries_with_metrics), 3),
            'avg_ndcg@10': round(sum(r['metrics']['ndcg@10'] for r in queries_with_metrics) / len(queries_with_metrics), 3),
        }

    # Per-category stats
    for category in ['well_formed', 'abbreviation', 'poorly_worded', 'technical']:
        cat_results = [r for r in successful_queries if r['category'] == category]
        if cat_results:
            summary['by_category'][category] = {
                'count': len(cat_results),
                'avg_results': round(sum(r['num_results'] for r in cat_results) / len(cat_results), 2),
                'avg_latency_ms': round(sum(r['latency_ms'] for r in cat_results) / len(cat_results), 2),
                'avg_top_similarity': round(sum(r['results'][0]['similarity'] for r in cat_results if r['num_results'] > 0) / len([r for r in cat_results if r['num_results'] > 0]), 3) if any(r['num_results'] > 0 for r in cat_results) else 0
            }

    # Create output structure
    output = {
        'benchmark_type': 'baseline',
        'timestamp': datetime.now().isoformat(),
        'collection': 'claude-agent-sdk',
        'search_method': 'vector_only',
        'summary': summary,
        'results': all_results
    }

    # Save results
    Path(output_dir).mkdir(exist_ok=True)
    timestamp_str = datetime.now().strftime('%Y%m%d-%H%M%S')
    output_file = Path(output_dir) / f"baseline-{timestamp_str}.json"

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print("=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)
    print(f"\nSummary:")
    print(f"  Total queries: {summary['total_queries']}")
    print(f"  Successful: {summary['successful_queries']}")
    print(f"  Failed: {summary['failed_queries']}")
    print(f"  Avg latency: {summary['avg_latency_ms']:.1f}ms")
    print(f"  Avg results per query: {summary['avg_results_per_query']:.1f}")
    print(f"  Avg top similarity: {summary['avg_top_similarity']:.3f}")

    # Print evaluation metrics summary
    if 'evaluation_metrics' in summary:
        em = summary['evaluation_metrics']
        print(f"\nEvaluation Metrics (based on {em['queries_evaluated']} labeled queries):")
        print(f"  Recall@5:      {em['avg_recall@5_any']:.1%} (any relevant), {em['avg_recall@5_high']:.1%} (highly relevant)")
        print(f"  Precision@5:   {em['avg_precision@5_any']:.1%} (any relevant), {em['avg_precision@5_high']:.1%} (highly relevant)")
        print(f"  MRR:           {em['avg_mrr_any']:.3f} (any relevant), {em['avg_mrr_high']:.3f} (highly relevant)")
        print(f"  nDCG@10:       {em['avg_ndcg@10']:.3f}")

    print()
    print("By Category:")
    for cat, stats in summary['by_category'].items():
        print(f"  {cat}:")
        print(f"    Queries: {stats['count']}")
        print(f"    Avg results: {stats['avg_results']:.1f}")
        print(f"    Avg similarity: {stats['avg_top_similarity']:.3f}")
    print()
    print(f"Results saved to: {output_file}")
    print()

    return str(output_file)


if __name__ == "__main__":
    import sys

    # Allow running from command line
    if len(sys.argv) > 1 and sys.argv[1] == "--baseline":
        run_baseline_benchmark()
    else:
        print("Usage: uv run python tests/benchmark/test_runner.py --baseline")
        sys.exit(1)
