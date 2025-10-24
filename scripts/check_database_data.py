#!/usr/bin/env python3
"""
Quick database data verification script.

Check if data exists in PostgreSQL and Neo4j across different environments.
Loads database connection parameters from config/config.{env}.yaml files.

Useful for verifying test databases are clean or for quick data snapshots.

Usage:
    uv run scripts/check_database_data.py --env test
    uv run scripts/check_database_data.py --env dev
    uv run scripts/check_database_data.py --env all
    uv run scripts/check_database_data.py --env test --verbose
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Optional

import yaml
import psycopg
from neo4j import AsyncGraphDatabase


class DatabaseChecker:
    """Check data existence across PostgreSQL and Neo4j databases."""

    def __init__(self, env: str = "test", verbose: bool = False):
        self.env = env
        self.verbose = verbose
        self.configs = self._load_configs()

    def _load_configs(self) -> dict:
        """Load database configurations from YAML files in config/ directory."""
        config_dir = Path(__file__).parent.parent / "config"
        configs = {}

        # Find all config.*.yaml files (excluding config.example.yaml)
        for config_file in sorted(config_dir.glob("config.*.yaml")):
            if "example" in config_file.name:
                continue

            # Extract environment name from filename (config.{env}.yaml)
            env_name = config_file.stem.replace("config.", "")

            try:
                with open(config_file, 'r') as f:
                    yaml_config = yaml.safe_load(f)

                # Extract database connection details from YAML
                server_config = yaml_config.get("server", {})
                db_url = server_config.get("database_url")
                neo4j_uri = server_config.get("neo4j_uri")
                neo4j_user = server_config.get("neo4j_user")
                neo4j_password = server_config.get("neo4j_password")

                if db_url and neo4j_uri:
                    # Extract ports from URLs for label
                    pg_port = db_url.split(":")[3].split("/")[0] if ":" in db_url else "?"
                    neo4j_port = neo4j_uri.split(":")[2] if ":" in neo4j_uri else "?"

                    configs[env_name] = {
                        "pg_url": db_url,
                        "neo4j_uri": neo4j_uri,
                        "neo4j_user": neo4j_user,
                        "neo4j_password": neo4j_password,
                        "label": f"{env_name.capitalize()} ({pg_port}/{neo4j_port})",
                        "config_file": config_file,
                    }
                    if self.verbose:
                        print(f"✓ Loaded config for '{env_name}' from {config_file.name}", file=sys.stderr)

            except Exception as e:
                if self.verbose:
                    print(f"✗ Failed to load config from {config_file.name}: {e}", file=sys.stderr)
                continue

        return configs

    async def check_postgresql(self, config: dict) -> dict:
        """Check PostgreSQL for data."""
        try:
            async with await psycopg.AsyncConnection.connect(config["pg_url"]) as conn:
                async with conn.cursor() as cur:
                    # Get document count
                    await cur.execute("SELECT COUNT(*) FROM source_documents")
                    doc_count = (await cur.fetchone())[0]

                    # Get chunk count
                    await cur.execute("SELECT COUNT(*) FROM document_chunks")
                    chunk_count = (await cur.fetchone())[0]

                    # Try to get crawl history count if table exists
                    try:
                        await cur.execute("SELECT COUNT(*) FROM crawl_history")
                        crawl_count = (await cur.fetchone())[0]
                    except:
                        crawl_count = None

                    return {
                        "success": True,
                        "documents": doc_count,
                        "chunks": chunk_count,
                        "crawls": crawl_count,
                        "total": doc_count + chunk_count + (crawl_count or 0),
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def check_neo4j(self, config: dict) -> dict:
        """Check Neo4j for data."""
        try:
            driver = AsyncGraphDatabase.driver(
                config["neo4j_uri"],
                auth=(config["neo4j_user"], config["neo4j_password"])
            )

            async with driver.session() as session:
                # Count all nodes
                result = await session.run("MATCH (n) RETURN count(n) as count")
                records = await result.data()
                node_count = records[0]['count'] if records else 0

                # Count Entity nodes
                result = await session.run("MATCH (e:Entity) RETURN count(e) as count")
                records = await result.data()
                entity_count = records[0]['count'] if records else 0

                return {
                    "success": True,
                    "nodes": node_count,
                    "entities": entity_count,
                }

            await driver.close()
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def check_environment(self, env_name: str) -> dict:
        """Check both databases for a given environment."""
        if env_name not in self.configs:
            available = ', '.join(sorted(self.configs.keys())) if self.configs else "None found (no config/*.yaml files)"
            return {
                "env": env_name,
                "error": f"Unknown environment '{env_name}'. Available: {available}"
            }

        config = self.configs[env_name]

        pg_result = await self.check_postgresql(config)
        neo4j_result = await self.check_neo4j(config)

        return {
            "env": env_name,
            "label": config["label"],
            "postgresql": pg_result,
            "neo4j": neo4j_result,
        }

    def print_result(self, result: dict) -> None:
        """Pretty print the results."""
        if "error" in result:
            print(f"❌ ERROR: {result['error']}")
            return

        env = result.get("env", "unknown")
        label = result.get("label", env)

        print(f"\n{'=' * 80}")
        print(f"DATABASE STATUS: {label}")
        print(f"{'=' * 80}")

        # PostgreSQL section
        pg = result.get("postgresql", {})
        if pg.get("success"):
            print(f"\n📊 PostgreSQL")
            print(f"  Documents:     {pg['documents']:>6}")
            print(f"  Chunks:        {pg['chunks']:>6}")
            if pg['crawls'] is not None:
                print(f"  Crawls:        {pg['crawls']:>6}")
            print(f"  Total rows:    {pg['total']:>6}")

            if pg['total'] == 0:
                print(f"  Status:        ✅ CLEAN")
            else:
                print(f"  Status:        ⚠️  HAS DATA")
        else:
            print(f"\n📊 PostgreSQL")
            print(f"  ❌ Connection failed: {pg.get('error', 'Unknown error')}")

        # Neo4j section
        neo4j = result.get("neo4j", {})
        if neo4j.get("success"):
            print(f"\n🔗 Neo4j")
            print(f"  Total nodes:   {neo4j['nodes']:>6}")
            print(f"  Entities:      {neo4j['entities']:>6}")

            if neo4j['nodes'] == 0:
                print(f"  Status:        ✅ CLEAN")
            else:
                print(f"  Status:        ⚠️  HAS DATA")
        else:
            print(f"\n🔗 Neo4j")
            print(f"  ❌ Connection failed: {neo4j.get('error', 'Unknown error')}")

        print()

    async def run(self) -> int:
        """Run the database checks."""
        if not self.configs:
            print(f"❌ ERROR: No configuration files found in config/ directory")
            print(f"Expected files like: config/config.test.yaml, config/config.dev.yaml, etc.")
            return 1

        if self.env == "all":
            environments = sorted(self.configs.keys())
        else:
            environments = [self.env]

        results = []
        for env in environments:
            result = await self.check_environment(env)
            results.append(result)

        # Print results
        for result in results:
            self.print_result(result)

        # Print summary
        if len(results) > 1:
            print(f"{'=' * 80}")
            print("SUMMARY")
            print(f"{'=' * 80}")
            for result in results:
                if "error" in result:
                    status = "❌ ERROR"
                else:
                    pg_clean = result["postgresql"].get("total", 1) == 0 if result["postgresql"].get("success") else False
                    neo4j_clean = result["neo4j"].get("nodes", 1) == 0 if result["neo4j"].get("success") else False

                    if pg_clean and neo4j_clean:
                        status = "✅ CLEAN"
                    elif not result["postgresql"].get("success") or not result["neo4j"].get("success"):
                        status = "❌ UNAVAILABLE"
                    else:
                        status = "⚠️  HAS DATA"

                label = result.get("label", result.get("env"))
                print(f"  {label:<30} {status}")
            print()

        # Return exit code based on findings
        return 0


async def main():
    # Create checker first to load available environments from config files
    temp_checker = DatabaseChecker(env="test", verbose=False)
    available_envs = sorted(temp_checker.configs.keys()) + ["all"]

    parser = argparse.ArgumentParser(
        description="Check data in PostgreSQL and Neo4j databases across environments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Dynamically loads database configurations from config/config.*.yaml files.

Available environments: {', '.join(available_envs)}

Examples:
  uv run scripts/check_database_data.py
  uv run scripts/check_database_data.py --env test
  uv run scripts/check_database_data.py --env dev
  uv run scripts/check_database_data.py --env all
  uv run scripts/check_database_data.py --env test --verbose
        """
    )

    parser.add_argument(
        "--env",
        choices=available_envs,
        default="test",
        help=f"Environment to check (default: test). Available: {', '.join(available_envs)}"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show verbose output including config file loading"
    )

    args = parser.parse_args()

    checker = DatabaseChecker(env=args.env, verbose=args.verbose)
    exit_code = await checker.run()

    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
