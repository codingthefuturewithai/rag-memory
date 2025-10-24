#!/usr/bin/env python3
"""
Knowledge Graph Relationship Search Benchmarking Tool

This script uses ONLY the RAG Memory CLI to:
1. Create collections
2. Ingest test documents
3. Run relationship search queries
4. Compare results against expected outcomes
5. Generate structured benchmark reports

Usage:
    cd /Users/timkitchens/projects/ai-projects/rag-memory
    uv run python benchmarking/scripts/run_benchmark.py --threshold 0.35
    uv run python benchmarking/scripts/run_benchmark.py --threshold 0.35 --env test
    uv run python benchmarking/scripts/run_benchmark.py --threshold 0.5 --output my_report.json
"""

import asyncio
import json
import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime
import argparse
from typing import Dict, List, Any
import yaml

from dotenv import load_dotenv

# Add project to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.unified.graph_store import GraphStore
from graphiti_core import Graphiti
from openai import OpenAI
import psycopg


# ============================================================================
# Configuration Loading
# ============================================================================

def load_config(env: str = "dev") -> Dict[str, Any]:
    """
    Load configuration from YAML and environment files using the standard convention.

    Args:
        env: Environment name (dev, test, prod). Looks for:
            - config/config.{env}.yaml
            - .env.{env}

    Returns:
        Dictionary with database credentials and configuration
    """
    benchmark_dir = Path(__file__).parent.parent
    repo_root = benchmark_dir.parent
    config_dir = repo_root / "config"

    # Load .env.{env} file
    env_file = repo_root / f".env.{env}"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        print(f"⚠️  Warning: {env_file} not found, using environment defaults")

    # Load config.{env}.yaml file
    config_file = config_dir / f"config.{env}.yaml"
    if not config_file.exists():
        print(f"❌ Error: Config file not found: {config_file}")
        print(f"   Expected environment: {env} (dev/test/prod)")
        sys.exit(1)

    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)

    # Extract database credentials
    server_config = config.get("server", {})
    database_url = server_config.get("database_url")
    neo4j_uri = server_config.get("neo4j_uri")
    neo4j_user = server_config.get("neo4j_user", "neo4j")
    neo4j_password = server_config.get("neo4j_password")

    if not database_url:
        print(f"❌ Error: database_url not found in {config_file}")
        sys.exit(1)

    if not neo4j_uri or not neo4j_password:
        print(f"❌ Error: neo4j_uri or neo4j_password not found in {config_file}")
        sys.exit(1)

    return {
        "postgres_url": database_url,
        "neo4j_uri": neo4j_uri,
        "neo4j_user": neo4j_user,
        "neo4j_password": neo4j_password,
        "config_path": config_dir,
        "config_file": f"config.{env}.yaml",
        "env": env,
    }


# ============================================================================
# Database Cleanup Functions
# ============================================================================

async def clean_postgresql(database_url: str) -> bool:
    """
    Delete all data from PostgreSQL while preserving the schema.

    Returns True if successful, False otherwise.
    """
    try:
        # Parse connection string
        conn = psycopg.connect(database_url)
        cursor = conn.cursor()

        try:
            # Delete data from all tables in dependency order
            # This respects foreign key constraints
            cursor.execute("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename DESC
            """)
            tables = cursor.fetchall()

            for (table,) in tables:
                cursor.execute(f"TRUNCATE TABLE {table} CASCADE")

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"      Error truncating tables: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"      Connection error: {e}")
        return False


async def clean_neo4j(neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> bool:
    """
    Delete all data from Neo4j while preserving indexes and schema.

    Returns True if successful, False otherwise.
    """
    try:
        graphiti = Graphiti(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)

        try:
            # Delete all nodes and relationships (preserves indexes)
            async with graphiti.driver.session() as session:
                await session.run("MATCH (n) DETACH DELETE n")

            return True
        except Exception as e:
            print(f"      Error deleting Neo4j data: {e}")
            return False
        finally:
            await graphiti.close()
    except Exception as e:
        print(f"      Connection error: {e}")
        return False


async def confirm_database_cleanup(postgres_url: str, neo4j_uri: str, env: str = "dev") -> bool:
    """
    Prompt user to confirm database cleanup with warning message showing actual connection details.

    Args:
        postgres_url: PostgreSQL connection URL
        neo4j_uri: Neo4j connection URI
        env: Environment name (for display)

    Returns True if user confirms, False otherwise.
    """
    print()
    print("⚠️  WARNING: Database Cleanup")
    print("=" * 60)
    print(f"The benchmark will delete ALL existing data from ({env} environment):")
    print(f"  1. PostgreSQL: {postgres_url}")
    print(f"  2. Neo4j:      {neo4j_uri}")
    print()
    print("This ensures clean, noise-free benchmark results.")
    print("Database schemas and indexes will be preserved.")
    print("=" * 60)
    print()

    while True:
        response = input("Continue with data deletion? (yes/no): ").strip().lower()
        if response in ["yes", "y"]:
            return True
        elif response in ["no", "n"]:
            print("❌ Benchmark cancelled by user")
            return False
        else:
            print("Please enter 'yes' or 'no'")


# ============================================================================
# LLM Judge System Prompt
# ============================================================================

JUDGE_SYSTEM_PROMPT = """You are an expert evaluator specializing in assessing the relevance and utility of knowledge graph relationship search results.

Your task is to evaluate whether a given set of relationship search results would reliably help an AI agent answer a specific user question.

Consider:
1. **Direct relevance**: Do the relationships directly address the question?
2. **Completeness**: Are key concepts and connections present?
3. **Usability**: Could an AI agent confidently use these to formulate an answer?
4. **False positives**: Are there irrelevant or misleading relationships?

Provide your assessment on a scale of 1-5:
- **5**: Definitely helpful. These relationships directly answer the question with high confidence.
- **4**: Very likely helpful. Strong relevance with minor gaps.
- **3**: Possibly helpful. Could work with inference, but some ambiguity or missing context.
- **2**: Unlikely helpful. Tangentially related or significant gaps.
- **1**: Not helpful. Irrelevant or misleading relationships.

Respond ONLY with valid JSON in this exact format:
{
  "score": 5,
  "reasoning": "Brief explanation of your assessment"
}"""


async def judge_results(
    query: str,
    relationships: List[Dict[str, Any]],
    sample_size: int = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Use GPT-5 Nano to judge whether search results would help answer the query.

    Args:
        query: The user's question/search query
        relationships: List of relationship objects returned from search
        sample_size: If set, only judge when within first N queries (for sampling)
        verbose: If True, print raw LLM response and request details

    Returns:
        Dictionary with judge score (1-5), reasoning, raw_response, and confidence
    """
    try:
        # Initialize OpenAI client from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {
                "score": None,
                "reasoning": "OPENAI_API_KEY not set",
                "error": "Missing API key",
                "judged": False,
                "raw_response": None
            }

        client = OpenAI(api_key=api_key)

        # Format relationships for the judge
        if not relationships:
            relationships_text = "No relationships found."
        else:
            relationships_text = "\n".join([
                f"- {rel.get('relationship_type', 'UNKNOWN')}: {rel.get('fact', '')}"
                for rel in relationships[:5]  # Limit to top 5 for clarity
            ])

        # Build user message
        user_message = f"""Question: {query}

Relationships Found:
{relationships_text}

Evaluate whether these results would reliably help answer the question."""

        if verbose:
            print()
            print("      📤 LLM Judge Request:")
            print(f"         Query: {query}")
            print(f"         Results: {len(relationships)} relationships")

        # Call GPT-5 Nano with low reasoning effort
        # Note: GPT-5 Nano only supports temperature=1.0 (the default), so we omit the parameter
        response = client.chat.completions.create(
            model="gpt-5-nano",
            reasoning_effort="low",
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            max_completion_tokens=300
        )

        # Parse response
        response_text = response.choices[0].message.content.strip()

        if verbose:
            print("      📥 LLM Judge Response:")
            print(f"         {response_text[:200]}..." if len(response_text) > 200 else f"         {response_text}")

        # Try to extract JSON
        try:
            result = json.loads(response_text)
            result["judged"] = True
            result["raw_response"] = response_text
            return result
        except json.JSONDecodeError:
            # If not valid JSON, still return what we got
            return {
                "score": None,
                "reasoning": response_text[:500],
                "error": "Response was not valid JSON",
                "judged": False,
                "raw_response": response_text  # Always capture raw response
            }

    except Exception as e:
        return {
            "score": None,
            "reasoning": str(e),
            "error": type(e).__name__,
            "judged": False,
            "raw_response": None
        }


def run_cli_command(args: List[str], cwd: Path, env_override: dict = None) -> tuple[str, str, int]:
    """
    Run a RAG CLI command and return stdout, stderr, and return code.

    Args:
        args: Command arguments (e.g., ["rag", "status"])
        cwd: Working directory
        env_override: Environment variables to override/set

    Returns:
        Tuple of (stdout, stderr, returncode)
    """
    try:
        env = os.environ.copy()
        if env_override:
            env.update(env_override)
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1
    except Exception as e:
        return "", str(e), -1


def ingest_test_data(project_root: Path, data_dir: Path, config_dir: Path) -> bool:
    """
    Ingest test documents using ONLY the RAG CLI.

    Uses:
    - rag collection create <name> <description>
    - rag ingest file <path> --collection <name>

    Returns:
        True if all documents ingested successfully, False otherwise
    """
    print("🔄 Ingesting test data via RAG CLI...")

    collections_config = {
        "AI-ML": {
            "description": "Artificial Intelligence and Machine Learning concepts, models, and techniques",
            "documents": ["ai_ml_comprehensive.txt"],
        },
        "Cloud-DevOps": {
            "description": "Cloud computing platforms, DevOps practices, and infrastructure technologies",
            "documents": ["cloud_computing_comprehensive.txt"],
        },
        "Ancient-History": {
            "description": "Ancient civilizations, archaeological discoveries, and historical relationships",
            "documents": ["ancient_history_comprehensive.txt"],
        }
    }

    env_vars = {
        "RAG_CONFIG_PATH": str(config_dir),
        "RAG_CONFIG_FILE": "config.dev.yaml"
    }
    all_success = True

    for collection_name, config in collections_config.items():
        print(f"  📚 Creating collection: {collection_name}")

        # Create collection via CLI
        cmd = ["rag", "collection", "create", collection_name, "--description", config["description"]]
        stdout, stderr, returncode = run_cli_command(cmd, project_root, env_vars)

        if returncode == 0:
            print(f"    ✓ Collection created")
        else:
            print(f"    ⚠️  Collection: {stderr.strip() if stderr else 'unknown error'}")
            all_success = False

        # Ingest documents via CLI
        for doc_filename in config["documents"]:
            doc_path = data_dir / doc_filename
            if not doc_path.exists():
                print(f"    ⚠️  Document not found: {doc_path}")
                all_success = False
                continue

            print(f"    📄 Ingesting: {doc_filename}")
            print(f"      [Starting at {datetime.now().strftime('%H:%M:%S')}...]")

            cmd = ["rag", "ingest", "file", str(doc_path), "--collection", collection_name]
            start_time = datetime.now()
            stdout, stderr, returncode = run_cli_command(cmd, project_root, env_vars)
            elapsed = (datetime.now() - start_time).total_seconds()

            if returncode == 0:
                print(f"      ✓ Ingested successfully in {elapsed:.1f}s")
                # Try to extract stats from stdout
                if "entities_extracted" in stdout.lower() or "chunks" in stdout.lower():
                    for line in stdout.split('\n'):
                        if 'entities' in line.lower() or 'chunks' in line.lower():
                            print(f"      {line.strip()}")
            else:
                print(f"      ⚠️  Failed after {elapsed:.1f}s: {stderr.strip() if stderr else stdout.strip()}")
                all_success = False

    print()
    return all_success


async def run_test_queries(
    graph_store: GraphStore,
    queries: List[Dict[str, Any]],
    threshold: float,
    sample_size: int = None
) -> Dict[str, Any]:
    """
    Run test queries using the Python GraphStore API with LLM judgment.

    Args:
        graph_store: GraphStore instance for searching
        queries: List of test query dicts
        threshold: Reranker threshold for search
        sample_size: If set, only run first N queries (for quick testing); if None, run all

    Returns:
        Dictionary with query results, pass/fail metrics, and judge scores
    """
    queries_to_run = queries if sample_size is None else queries[:sample_size]
    total_available = len(queries)

    print(f"🔍 Running {len(queries_to_run)} test queries (threshold={threshold})...")
    if sample_size:
        print(f"   (Quick test mode: first {sample_size} of {total_available} available queries)")

    results = {
        "queries_passed": 0,
        "queries_failed": 0,
        "judge_scores": [],
        "query_results": []
    }

    for test in queries_to_run:
        query_id = test["id"]
        query_text = test["query"]
        expected_min = test["expected_min_results"]
        expected_max = test["expected_max_results"]

        actual_count = 0
        edge_dicts = []
        error = None
        judge_result = None

        try:
            # Run query via Python API
            edges = await graph_store.search_relationships(
                query=query_text,
                num_results=10,
                reranker_min_score=threshold
            )

            actual_count = len(edges) if edges else 0

            # Convert edges to serializable dicts
            if edges:
                for edge in edges:
                    edge_dicts.append({
                        "id": str(getattr(edge, 'uuid', '')),
                        "relationship_type": getattr(edge, 'name', 'UNKNOWN'),
                        "fact": getattr(edge, 'fact', ''),
                        "score": getattr(edge, 'reranker_score', None)
                    })

            # Get LLM judge evaluation (with verbose output)
            judge_result = await judge_results(query_text, edge_dicts, verbose=True)
            if judge_result.get("judged"):
                results["judge_scores"].append({
                    "query_id": query_id,
                    "score": judge_result.get("score"),
                    "reasoning": judge_result.get("reasoning"),
                    "raw_response": judge_result.get("raw_response")
                })
            else:
                # Log errors from judge
                if judge_result.get("error"):
                    judge_error = judge_result.get("reasoning", judge_result.get("error", "Unknown error"))
                    print(f"      ⚠️  Judge error: {judge_error}")
                    if judge_result.get("raw_response"):
                        print(f"      Raw response: {judge_result.get('raw_response')[:500]}")

        except Exception as e:
            error = str(e)
            actual_count = 0

        # Determine pass/fail (based on expected result count AND successful judge evaluation)
        count_valid = expected_min <= actual_count <= expected_max
        judge_succeeded = judge_result and judge_result.get("judged") == True
        passed = count_valid and judge_succeeded

        result = {
            "query_id": query_id,
            "query_text": query_text,
            "category": test["category"],
            "expected_min": expected_min,
            "expected_max": expected_max,
            "actual_results": actual_count,
            "passed": passed,
            "results": edge_dicts
        }

        # Add judge score and raw response if available
        if judge_result and judge_result.get("judged"):
            result["judge_score"] = judge_result.get("score")
            result["judge_reasoning"] = judge_result.get("reasoning")
            result["judge_raw_response"] = judge_result.get("raw_response")
        elif judge_result and judge_result.get("raw_response"):
            # Even if judge failed, save the raw response for debugging
            result["judge_raw_response"] = judge_result.get("raw_response")
            result["judge_error"] = judge_result.get("error")

        if error:
            result["error"] = error

        results["query_results"].append(result)

        if passed:
            results["queries_passed"] += 1
            status = "✓"
        else:
            results["queries_failed"] += 1
            status = "✗"

        judge_info = ""
        if judge_result and judge_result.get("judged"):
            judge_info = f" [Judge: {judge_result.get('score')}/5]"
            print(f"  {status} Query {query_id}: {actual_count} results (expected {expected_min}-{expected_max}){judge_info}")
            # Print judge reasoning on next line for better visibility
            reasoning = judge_result.get("reasoning", "")
            if reasoning:
                print(f"      Reasoning: {reasoning}")
        else:
            print(f"  {status} Query {query_id}: {actual_count} results (expected {expected_min}-{expected_max}){judge_info}")

    return results


def calculate_metrics(test_results: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate performance metrics from test results."""
    total = len(test_results["query_results"])
    passed = test_results["queries_passed"]
    failed = test_results["queries_failed"]

    # Calculate by category
    by_category = {}
    for result in test_results["query_results"]:
        category = result.get("category", "unknown")
        if category not in by_category:
            by_category[category] = {"passed": 0, "failed": 0}
        if result.get("passed"):
            by_category[category]["passed"] += 1
        else:
            by_category[category]["failed"] += 1

    # Calculate judge scores if available
    judge_scores = test_results.get("judge_scores", [])
    judge_metrics = {}
    if judge_scores:
        scores = [j["score"] for j in judge_scores if j.get("score") is not None]
        if scores:
            judge_metrics = {
                "total_judged": len(scores),
                "average_score": round(sum(scores) / len(scores), 2),
                "distribution": {
                    1: sum(1 for s in scores if s == 1),
                    2: sum(1 for s in scores if s == 2),
                    3: sum(1 for s in scores if s == 3),
                    4: sum(1 for s in scores if s == 4),
                    5: sum(1 for s in scores if s == 5),
                }
            }

    metrics = {
        "total_queries": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total * 100, 2) if total > 0 else 0,
        "by_category": by_category
    }

    if judge_metrics:
        metrics["judge_metrics"] = judge_metrics

    return metrics


async def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Graph Relationship Search Benchmark with LLM Judging"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.35,
        help="Reranker threshold (0.0-1.0, default 0.35)"
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Run only first N queries (quick test mode, default: run all 30)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output report filename (default: benchmarking/reports/report_THRESHOLD_TIMESTAMP.json)"
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip data ingestion (use existing data)"
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Skip database cleanup (use existing data without cleaning)"
    )
    parser.add_argument(
        "--env",
        type=str,
        default="dev",
        choices=["dev", "test", "prod"],
        help="Environment to use (dev/test/prod, default: dev)"
    )

    args = parser.parse_args()

    # Setup paths
    benchmark_dir = Path(__file__).parent.parent
    project_root = benchmark_dir.parent
    data_dir = benchmark_dir / "data" / "test_documents"
    queries_file = benchmark_dir / "data" / "test_queries.json"
    reports_dir = benchmark_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    # Load test queries
    try:
        with open(queries_file, 'r') as f:
            queries_data = json.load(f)
        test_queries = queries_data["tests"]
    except Exception as e:
        print(f"❌ Failed to load test queries: {e}")
        sys.exit(1)

    print(f"📊 Knowledge Graph Relationship Search Benchmark")
    print(f"⚙️  Threshold: {args.threshold}")
    print(f"📁 Test queries: {len(test_queries)}")
    print(f"🌍 Environment: {args.env}")
    print()

    try:
        # Load configuration from YAML and environment files
        print(f"📋 Loading configuration for environment '{args.env}'...")
        config = load_config(args.env)
        postgres_url = config["postgres_url"]
        neo4j_uri = config["neo4j_uri"]
        neo4j_user = config["neo4j_user"]
        neo4j_password = config["neo4j_password"]
        config_dir = config["config_path"]
        print(f"✓ Configuration loaded from {config['config_file']}")
        print()

        # Check RAG CLI is available
        print("🔗 Checking RAG CLI...")
        env_vars = {
            "RAG_CONFIG_PATH": str(config_dir),
            "RAG_CONFIG_FILE": config["config_file"]
        }
        _, stderr, returncode = run_cli_command(["rag", "status"], project_root, env_vars)
        if returncode != 0:
            print(f"❌ RAG CLI not available or not working")
            print(f"   Error: {stderr}")
            sys.exit(1)
        print("✓ RAG CLI is ready")
        print()

        # Clean databases (unless --skip-clean is specified)
        if not args.skip_clean:
            if not await confirm_database_cleanup(postgres_url, neo4j_uri, args.env):
                sys.exit(0)

            print("🧹 Cleaning databases...")

            # Clean PostgreSQL
            print("  Cleaning PostgreSQL...")
            pg_success = await clean_postgresql(postgres_url)
            if pg_success:
                print("    ✓ PostgreSQL cleaned")
            else:
                print("    ✗ PostgreSQL cleanup failed")

            # Clean Neo4j
            print("  Cleaning Neo4j...")
            neo4j_success = await clean_neo4j(neo4j_uri, neo4j_user, neo4j_password)
            if neo4j_success:
                print("    ✓ Neo4j cleaned")
            else:
                print("    ✗ Neo4j cleanup failed")

            if not (pg_success and neo4j_success):
                print("⚠️  Some databases failed to clean, but continuing...")

            print()
        else:
            print("⏭️  Skipping database cleanup (using existing data)")
            print()

        # Ingest test data
        if not args.skip_ingest:
            success = ingest_test_data(project_root, data_dir, config_dir)
            if not success:
                print("⚠️  Some data ingestion failed, continuing with partial data...")
        else:
            print("⏭️  Skipping data ingestion (using existing data)")
            print()

        # Setup Neo4j connection for queries (using credentials from above)
        graphiti = Graphiti(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)
        graph_store = GraphStore(graphiti)

        # Run tests
        test_results = await run_test_queries(
            graph_store,
            test_queries,
            args.threshold,
            sample_size=args.sample_size
        )

        # Calculate metrics
        metrics = calculate_metrics(test_results)

        # Generate report
        report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "threshold": args.threshold,
                "test_data_ingested": not args.skip_ingest,
                "query_count": len(test_queries)
            },
            "summary": {
                "total_queries": metrics["total_queries"],
                "passed": metrics["passed"],
                "failed": metrics["failed"],
                "pass_rate_percent": metrics["pass_rate"]
            },
            "by_category": metrics["by_category"],
            "query_results": test_results["query_results"]
        }

        # Add judge metrics if available
        if "judge_metrics" in metrics:
            report["judge_metrics"] = metrics["judge_metrics"]

        # Save report
        if args.output:
            report_path = Path(args.output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = reports_dir / f"report_threshold_{args.threshold}_{timestamp}.json"

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        # Print summary
        print()
        print("=" * 60)
        print("📈 BENCHMARK RESULTS")
        print("=" * 60)
        print(f"Threshold: {args.threshold}")
        print(f"Total queries: {metrics['total_queries']}")
        print(f"Passed: {metrics['passed']} ({metrics['pass_rate']}%)")
        print(f"Failed: {metrics['failed']}")
        print()
        print("By category:")
        for category, counts in metrics["by_category"].items():
            total_cat = counts["passed"] + counts["failed"]
            rate = round(counts["passed"] / total_cat * 100, 1) if total_cat > 0 else 0
            print(f"  {category}: {counts['passed']}/{total_cat} ({rate}%)")

        # Print judge metrics if available
        if "judge_metrics" in metrics:
            judge = metrics["judge_metrics"]
            print()
            print("LLM Judge Results (1-5 scale):")
            print(f"  Total judged: {judge['total_judged']}")
            print(f"  Average score: {judge['average_score']}")
            print(f"  Distribution:")
            dist = judge["distribution"]
            for score in [5, 4, 3, 2, 1]:
                count = dist.get(score, 0)
                bar = "█" * count
                print(f"    {score}/5: {count} {bar}")

        print()
        print(f"✅ Report saved to: {report_path}")
        print("=" * 60)

        # Close graphiti connection
        await graphiti.close()

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
