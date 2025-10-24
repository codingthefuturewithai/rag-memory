#!/usr/bin/env python3
"""
RAG Memory environment wrapper - cross-platform (Windows, Mac, Linux)

Usage:
    python scripts/rag.py cli [--env dev|test|prod] <command> [options]
    python scripts/rag.py mcp [--env dev|test|prod]

Examples:
    python scripts/rag.py cli search "query"                     # CLI with dev
    python scripts/rag.py cli --env test ingest-text "content"  # CLI with test
    python scripts/rag.py mcp --env dev                         # MCP server with dev
    python scripts/rag.py mcp --env prod                        # MCP server with prod
"""

import os
import sys
import subprocess
from pathlib import Path

def load_env_vars(env):
    """Load environment variables from .env.{env} and return env dict."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Check that required files exist
    env_file = repo_root / f".env.{env}"
    config_file = repo_root / "config" / f"config.{env}.yaml"

    if not env_file.exists():
        print(f"Error: {env_file} not found")
        sys.exit(1)

    if not config_file.exists():
        print(f"Error: {config_file} not found")
        sys.exit(1)

    # Load environment variables from .env.{env}
    env_vars = os.environ.copy()
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    env_vars[key] = value
    except Exception as e:
        print(f"Error reading {env_file}: {e}")
        sys.exit(1)

    # Set config path to use config.{env}.yaml
    env_vars["RAG_CONFIG_PATH"] = str(repo_root / "config")
    env_vars["RAG_CONFIG_FILE"] = f"config.{env}.yaml"

    return env_vars, repo_root

def run_cli(args):
    """Run CLI command."""
    env = "dev"

    # Parse --env flag if present
    if args and args[0] == "--env":
        if len(args) < 2:
            print("Error: --env requires an argument (dev, test, prod)")
            sys.exit(1)
        env = args[1]
        args = args[2:]

    if env not in ("dev", "test", "prod"):
        print(f"Error: Invalid environment '{env}'. Must be dev, test, or prod")
        sys.exit(1)

    env_vars, repo_root = load_env_vars(env)

    try:
        result = subprocess.run(
            ["uv", "run", "rag"] + args,
            env=env_vars,
            cwd=str(repo_root)
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def run_mcp(args):
    """Run MCP server."""
    env = "dev"

    # Parse --env flag if present
    if args and args[0] == "--env":
        if len(args) < 2:
            print("Error: --env requires an argument (dev, test, prod)")
            sys.exit(1)
        env = args[1]
        args = args[2:]

    if env not in ("dev", "test", "prod"):
        print(f"Error: Invalid environment '{env}'. Must be dev, test, or prod")
        sys.exit(1)

    env_vars, repo_root = load_env_vars(env)

    try:
        result = subprocess.run(
            ["uv", "run", "mcp", "dev", "src/mcp/server.py"],
            env=env_vars,
            cwd=str(repo_root)
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    args = sys.argv[1:]

    if not args:
        print("Usage: python scripts/rag.py cli|mcp [--env dev|test|prod] [options]")
        print("Examples:")
        print("  python scripts/rag.py cli search 'query'")
        print("  python scripts/rag.py cli --env test ingest-text 'content'")
        print("  python scripts/rag.py mcp --env dev")
        sys.exit(1)

    command = args[0]
    remaining_args = args[1:]

    if command == "cli":
        run_cli(remaining_args)
    elif command == "mcp":
        run_mcp(remaining_args)
    else:
        print(f"Error: Unknown command '{command}'. Must be 'cli' or 'mcp'")
        sys.exit(1)

if __name__ == "__main__":
    main()
