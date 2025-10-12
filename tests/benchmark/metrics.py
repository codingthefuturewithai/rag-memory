"""
Evaluation metrics for RAG search optimization.

Calculates metrics like Recall@K, MRR, nDCG using ground truth labels.
"""

from typing import List, Dict, Any
import yaml
from pathlib import Path


def load_ground_truth() -> Dict[str, Any]:
    """Load ground truth labels from YAML file."""
    gt_file = Path(__file__).parent.parent.parent / "test-data" / "ground-truth.yaml"
    with open(gt_file, 'r') as f:
        return yaml.safe_load(f)


def get_relevant_chunks(query_id: str, ground_truth: Dict[str, Any]) -> Dict[str, str]:
    """
    Get relevant chunks for a query from ground truth.

    Returns:
        Dict mapping chunk_id to relevance level ('highly_relevant', 'relevant', 'not_relevant')
    """
    for query in ground_truth['queries']:
        if query['query_id'] == query_id:
            relevance_map = {}

            for result in query['labeled_results']:
                # Handle both single chunk and multiple chunks
                if 'chunk_id' in result:
                    relevance_map[result['chunk_id']] = result['relevance']
                elif 'chunk_ids' in result:
                    for chunk_id in result['chunk_ids']:
                        relevance_map[chunk_id] = result['relevance']

            return relevance_map

    return {}


def calculate_recall_at_k(
    results: List[Dict[str, Any]],
    ground_truth_relevance: Dict[int, str],
    k: int = 5,
    min_relevance: str = 'relevant'
) -> float:
    """
    Calculate Recall@K: What fraction of relevant documents appear in top K results?

    Args:
        results: List of search results with 'chunk_id'
        ground_truth_relevance: Dict mapping chunk_id to relevance level
        k: Number of top results to consider
        min_relevance: Minimum relevance level to count ('relevant' or 'highly_relevant')

    Returns:
        Recall@K score (0.0 to 1.0)
    """
    if not ground_truth_relevance:
        return 0.0

    # Determine which documents are relevant based on min_relevance threshold
    if min_relevance == 'highly_relevant':
        relevant_chunks = {cid for cid, rel in ground_truth_relevance.items()
                          if rel == 'highly_relevant'}
    else:  # 'relevant' includes both 'relevant' and 'highly_relevant'
        relevant_chunks = {cid for cid, rel in ground_truth_relevance.items()
                          if rel in ['relevant', 'highly_relevant']}

    if not relevant_chunks:
        return 0.0

    # Check how many relevant chunks appear in top K results
    top_k_chunks = {r['chunk_id'] for r in results[:k]}
    found_relevant = top_k_chunks & relevant_chunks

    recall = len(found_relevant) / len(relevant_chunks)
    return recall


def calculate_precision_at_k(
    results: List[Dict[str, Any]],
    ground_truth_relevance: Dict[int, str],
    k: int = 5,
    min_relevance: str = 'relevant'
) -> float:
    """
    Calculate Precision@K: What fraction of top K results are relevant?

    Args:
        results: List of search results with 'chunk_id'
        ground_truth_relevance: Dict mapping chunk_id to relevance level
        k: Number of top results to consider
        min_relevance: Minimum relevance level to count

    Returns:
        Precision@K score (0.0 to 1.0)
    """
    if not results or not ground_truth_relevance:
        return 0.0

    top_k = results[:k]
    if not top_k:
        return 0.0

    # Count how many of top K are relevant
    relevant_in_top_k = 0
    for result in top_k:
        chunk_id = result['chunk_id']
        relevance = ground_truth_relevance.get(chunk_id, 'not_relevant')

        if min_relevance == 'highly_relevant':
            if relevance == 'highly_relevant':
                relevant_in_top_k += 1
        else:
            if relevance in ['relevant', 'highly_relevant']:
                relevant_in_top_k += 1

    precision = relevant_in_top_k / len(top_k)
    return precision


def calculate_mrr(
    results: List[Dict[str, Any]],
    ground_truth_relevance: Dict[int, str],
    min_relevance: str = 'relevant'
) -> float:
    """
    Calculate Mean Reciprocal Rank: 1 / rank of first relevant document.

    Args:
        results: List of search results with 'chunk_id'
        ground_truth_relevance: Dict mapping chunk_id to relevance level
        min_relevance: Minimum relevance level to count

    Returns:
        MRR score (0.0 to 1.0)
    """
    if not results or not ground_truth_relevance:
        return 0.0

    for rank, result in enumerate(results, start=1):
        chunk_id = result['chunk_id']
        relevance = ground_truth_relevance.get(chunk_id, 'not_relevant')

        is_relevant = False
        if min_relevance == 'highly_relevant':
            is_relevant = (relevance == 'highly_relevant')
        else:
            is_relevant = (relevance in ['relevant', 'highly_relevant'])

        if is_relevant:
            return 1.0 / rank

    return 0.0  # No relevant documents found


def calculate_ndcg(
    results: List[Dict[str, Any]],
    ground_truth_relevance: Dict[int, str],
    k: int = 10
) -> float:
    """
    Calculate Normalized Discounted Cumulative Gain (nDCG@K).

    Relevance scores:
      - highly_relevant: 2
      - relevant: 1
      - not_relevant: 0

    Args:
        results: List of search results with 'chunk_id'
        ground_truth_relevance: Dict mapping chunk_id to relevance level
        k: Number of results to consider

    Returns:
        nDCG@K score (0.0 to 1.0)
    """
    if not results or not ground_truth_relevance:
        return 0.0

    relevance_scores = {
        'highly_relevant': 2,
        'relevant': 1,
        'not_relevant': 0
    }

    # Calculate DCG (Discounted Cumulative Gain)
    dcg = 0.0
    for rank, result in enumerate(results[:k], start=1):
        chunk_id = result['chunk_id']
        relevance = ground_truth_relevance.get(chunk_id, 'not_relevant')
        rel_score = relevance_scores[relevance]

        # DCG formula: sum(rel_i / log2(i+1))
        import math
        dcg += rel_score / math.log2(rank + 1)

    # Calculate IDCG (Ideal DCG) - if results were perfectly ordered
    ideal_scores = sorted(
        [relevance_scores[rel] for rel in ground_truth_relevance.values()],
        reverse=True
    )
    idcg = 0.0
    for rank, rel_score in enumerate(ideal_scores[:k], start=1):
        import math
        idcg += rel_score / math.log2(rank + 1)

    if idcg == 0:
        return 0.0

    return dcg / idcg


def calculate_all_metrics(
    results: List[Dict[str, Any]],
    query_id: str,
    ground_truth: Dict[str, Any] = None
) -> Dict[str, float]:
    """
    Calculate all evaluation metrics for a query.

    Args:
        results: List of search results
        query_id: Query ID from ground truth
        ground_truth: Ground truth dict (loaded if None)

    Returns:
        Dict with all metric scores
    """
    if ground_truth is None:
        ground_truth = load_ground_truth()

    relevance_map = get_relevant_chunks(query_id, ground_truth)

    if not relevance_map:
        # No ground truth for this query
        return {
            'has_ground_truth': False,
            'recall@5': None,
            'precision@5': None,
            'mrr': None,
            'ndcg@10': None,
        }

    metrics = {
        'has_ground_truth': True,

        # Recall metrics (both thresholds)
        'recall@5_any': calculate_recall_at_k(results, relevance_map, k=5, min_relevance='relevant'),
        'recall@5_high': calculate_recall_at_k(results, relevance_map, k=5, min_relevance='highly_relevant'),
        'recall@10_any': calculate_recall_at_k(results, relevance_map, k=10, min_relevance='relevant'),

        # Precision metrics
        'precision@5_any': calculate_precision_at_k(results, relevance_map, k=5, min_relevance='relevant'),
        'precision@5_high': calculate_precision_at_k(results, relevance_map, k=5, min_relevance='highly_relevant'),

        # MRR
        'mrr_any': calculate_mrr(results, relevance_map, min_relevance='relevant'),
        'mrr_high': calculate_mrr(results, relevance_map, min_relevance='highly_relevant'),

        # nDCG
        'ndcg@10': calculate_ndcg(results, relevance_map, k=10),
    }

    # Count relevant docs in results for analysis
    metrics['highly_relevant_in_top5'] = sum(
        1 for r in results[:5]
        if relevance_map.get(r['chunk_id']) == 'highly_relevant'
    )
    metrics['relevant_in_top5'] = sum(
        1 for r in results[:5]
        if relevance_map.get(r['chunk_id']) in ['relevant', 'highly_relevant']
    )

    return metrics


def format_metrics_report(metrics: Dict[str, float]) -> str:
    """Format metrics into readable report string."""
    if not metrics.get('has_ground_truth'):
        return "No ground truth available"

    lines = []
    lines.append(f"  Recall@5:      {metrics['recall@5_any']:.1%} (any relevant), {metrics['recall@5_high']:.1%} (highly relevant)")
    lines.append(f"  Precision@5:   {metrics['precision@5_any']:.1%} (any relevant), {metrics['precision@5_high']:.1%} (highly relevant)")
    lines.append(f"  MRR:           {metrics['mrr_any']:.3f} (any relevant), {metrics['mrr_high']:.3f} (highly relevant)")
    lines.append(f"  nDCG@10:       {metrics['ndcg@10']:.3f}")
    lines.append(f"  Top 5 counts:  {metrics['highly_relevant_in_top5']} highly relevant, {metrics['relevant_in_top5']} total relevant")

    return "\n".join(lines)
