#!/usr/bin/env python3
"""
RAG Memory environment wrapper - cross-platform (Windows, Mac, Linux)

Developer tool for managing dev/test/staging environments within the repository.
Container commands (status, logs, start, stop, restart) are intercepted and
handled based on what's actually deployed in each environment.

IMPORTANT: This script is for DEVELOPMENT ONLY. For production, use the
system-installed CLI (installed via setup).

Usage:
    python scripts/rag.py cli --env <environment> <command> [options]
    python scripts/rag.py mcp --env <environment>

Examples:
    python scripts/rag.py cli --env dev status                   # Dev status
    python scripts/rag.py cli --env test ingest-text "content"   # CLI with test
    python scripts/rag.py cli --env dev logs --service postgres  # Dev logs
    python scripts/rag.py mcp --env dev                          # MCP server with dev

Supported environments are auto-discovered based on these files:
    - config/config.{env}.yaml
    - .env.{env}
    - deploy/docker/compose/docker-compose.{env}.yml
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path

# Commands that manage containers (environment-specific, intercepted by this script)
CONTAINER_COMMANDS = {'status', 'logs', 'start', 'stop', 'restart'}


def validate_environment(env):
    """
    Validate environment by checking required files exist.

    Required files for an environment:
    - config/config.{env}.yaml
    - .env.{env}
    - deploy/docker/compose/docker-compose.{env}.yml

    Returns:
        (bool, list): (is_valid, missing_files)
    """
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    required_files = [
        repo_root / "config" / f"config.{env}.yaml",
        repo_root / f".env.{env}",
        repo_root / "deploy/docker/compose" / f"docker-compose.{env}.yml"
    ]

    missing = [str(f.relative_to(repo_root)) for f in required_files if not f.exists()]

    return len(missing) == 0, missing


def load_env_vars(env):
    """Load environment variables from .env.{env} and return env dict."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    # Validate environment first
    is_valid, missing_files = validate_environment(env)
    if not is_valid:
        print(f"Error: Environment '{env}' not supported")
        print(f"Missing required files:")
        for file in missing_files:
            print(f"  - {file}")
        print(f"\nSupported environments have these files:")
        print(f"  - config/config.{{env}}.yaml")
        print(f"  - .env.{{env}}")
        print(f"  - deploy/docker/compose/docker-compose.{{env}}.yml")
        sys.exit(1)

    # Load environment variables from .env.{env}
    env_file = repo_root / f".env.{env}"
    config_file = repo_root / "config" / f"config.{env}.yaml"

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


def get_environment_context(env):
    """
    Get environment-specific context by reading compose file.

    Uses convention: deploy/docker/compose/docker-compose.{env}.yml

    Returns:
        {
            'env': str (e.g., 'dev', 'test', 'staging'),
            'compose_file': Path,
            'services': ['postgres-dev', 'neo4j-dev', ...],
            'containers': {'postgres': 'rag-memory-postgres-dev', ...}
        }
    """
    repo_root = Path(__file__).parent.parent

    # Use convention: docker-compose.{env}.yml
    compose_file = repo_root / 'deploy/docker/compose' / f'docker-compose.{env}.yml'

    if not compose_file.exists():
        print(f"Error: Compose file not found for environment '{env}'")
        print(f"Expected: {compose_file.relative_to(repo_root)}")
        sys.exit(1)

    # Parse compose file to discover services
    try:
        with open(compose_file) as f:
            compose_data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error parsing {compose_file}: {e}")
        sys.exit(1)

    services_config = compose_data.get('services', {})
    services = list(services_config.keys())

    # Build container name mapping (read actual container_name from compose)
    containers = {}
    for service_name, service_config in services_config.items():
        container_name = service_config.get('container_name', f'rag-memory-{service_name}')
        # Normalize service names (postgres-dev → postgres, neo4j-test → neo4j)
        normalized_name = service_name.replace('-dev', '').replace('-test', '').replace('-local', '')
        containers[normalized_name] = container_name

    return {
        'env': env,
        'compose_file': compose_file,
        'services': services,
        'containers': containers
    }


def check_docker_running():
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def handle_status_command(env_context):
    """Handle 'rag status' command with environment awareness."""
    env = env_context['env']
    containers = env_context['containers']

    # Check Docker is running
    if not check_docker_running():
        print("✗ Docker daemon is not running")
        print("  Start Docker Desktop and try again")
        sys.exit(1)

    # Print banner
    env_label = f" [{env.upper()} environment]" if env != 'prod' else ""
    print(f"\nRAG Memory Status{env_label}\n")

    if env != 'prod':
        print(f"Note: Running in {env} environment.")
        print(f"      Only checking containers deployed in this environment.\n")

    # Run docker ps for each container
    for service, container_name in sorted(containers.items()):
        result = subprocess.run(
            ['docker', 'ps', '-a', '--filter', f'name=^{container_name}$', '--format', '{{.Status}}'],
            capture_output=True,
            text=True
        )

        status = result.stdout.strip()

        if not status:
            print(f"  {service}: [NOT FOUND]")
        elif "Up" in status:
            if "healthy" in status.lower():
                print(f"  ✓ {service}: {status}")
            else:
                print(f"  ⚠ {service}: {status}")
        else:
            print(f"  ✗ {service}: {status}")

    print()


def handle_logs_command(env_context, args):
    """Handle 'rag logs' command with environment awareness."""
    containers = env_context['containers']
    env = env_context['env']

    # Parse args to find --service, --tail, --follow
    service = None
    tail = 50
    follow = False

    i = 0
    while i < len(args):
        if args[i] == '--service' and i + 1 < len(args):
            service = args[i + 1]
            i += 2
        elif args[i] == '--tail' and i + 1 < len(args):
            tail = int(args[i + 1])
            i += 2
        elif args[i] in ['--follow', '-f']:
            follow = True
            i += 1
        elif args[i] == '--help':
            # Pass through to CLI for help
            return False
        else:
            i += 1

    # Validate service exists in this environment
    if service and service not in containers:
        available = ', '.join(sorted(containers.keys()))
        print(f"Error: Service '{service}' not available in {env} environment")
        print(f"Available services: {available}")
        sys.exit(1)

    # Determine which containers to show
    if service:
        targets = {service: containers[service]}
    else:
        targets = containers

    # Check follow mode with multiple containers
    if follow and len(targets) > 1:
        available = ', '.join(sorted(containers.keys()))
        print("Error: Cannot follow logs from multiple containers")
        print(f"Use --service to specify which container to follow")
        print(f"Available services: {available}")
        sys.exit(1)

    # Show logs
    for service_name, container_name in sorted(targets.items()):
        # Check if container exists
        check_result = subprocess.run(
            ['docker', 'ps', '-a', '--filter', f'name=^{container_name}$', '--format', '{{.Names}}'],
            capture_output=True,
            text=True
        )

        if not check_result.stdout.strip():
            if len(targets) == 1:
                print(f"Error: Container '{container_name}' not found")
                print(f"Run 'python scripts/rag.py cli --env {env} start' to start services")
                sys.exit(1)
            else:
                print(f"Skipping {service_name} (container not found)")
                continue

        cmd = ['docker', 'logs']
        if follow:
            cmd.append('--follow')
        cmd.extend(['--tail', str(tail)])
        cmd.append(container_name)

        if follow:
            print(f"Following logs for {service_name} (Ctrl+C to stop)...\n")
        elif len(targets) > 1:
            print(f"\n{'='*60}")
            print(f"{service_name.upper()} ({container_name})")
            print(f"{'='*60}\n")

        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\nStopped following logs")
            break

    return True


def handle_container_lifecycle(env_context, command):
    """Handle start/stop/restart commands using docker-compose."""
    compose_file = env_context['compose_file']
    env = env_context['env']

    # Check Docker is running
    if not check_docker_running():
        print("✗ Docker daemon is not running")
        print("  Start Docker Desktop and try again")
        sys.exit(1)

    print(f"[{env.upper()}] Running docker-compose {command}...\n")

    # Map to docker-compose commands
    dc_command = {
        'start': 'up',
        'stop': 'down',
        'restart': 'restart'
    }.get(command, command)

    cmd = ['docker-compose', '-f', str(compose_file)]

    if dc_command == 'up':
        cmd.extend(['up', '-d'])
    else:
        cmd.append(dc_command)

    result = subprocess.run(cmd, cwd=str(compose_file.parent))
    sys.exit(result.returncode)


def handle_service_command(env_context, args):
    """Handle 'rag service start/stop/restart/status' commands."""
    if not args:
        print("Error: service command requires subcommand (start, stop, restart, status)")
        sys.exit(1)

    subcommand = args[0]
    remaining_args = args[1:]

    if subcommand == 'status':
        handle_status_command(env_context)
    elif subcommand in ['start', 'stop', 'restart']:
        handle_container_lifecycle(env_context, subcommand)
    else:
        print(f"Error: Unknown service subcommand: {subcommand}")
        print("Valid subcommands: start, stop, restart, status")
        sys.exit(1)


def run_cli(args):
    """Run CLI command with environment awareness."""
    # Parse --env flag (required)
    if not args or args[0] != "--env":
        print("Error: --env flag is required")
        print("Usage: python scripts/rag.py cli --env <environment> <command> [options]")
        print("Example: python scripts/rag.py cli --env dev status")
        sys.exit(1)

    if len(args) < 2:
        print("Error: --env requires an environment name")
        print("Example: python scripts/rag.py cli --env dev status")
        sys.exit(1)

    env = args[1]
    args = args[2:]

    # Validate environment and load config first (validates all required files)
    env_vars, repo_root = load_env_vars(env)

    # Get environment context (reads compose file to discover containers)
    env_context = get_environment_context(env)

    # Intercept container management commands
    if args and args[0] in CONTAINER_COMMANDS:
        command = args[0]
        remaining_args = args[1:]

        if command == 'status':
            handle_status_command(env_context)
            return
        elif command == 'logs':
            handled = handle_logs_command(env_context, remaining_args)
            if handled:
                return
            # If not handled (e.g., --help), fall through to CLI
        elif command in ['start', 'stop', 'restart']:
            handle_container_lifecycle(env_context, command)
            return

    elif args and args[0] == 'service':
        handle_service_command(env_context, args[1:])
        return

    # All other commands: pass through to production CLI
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
    # Parse --env flag (required)
    if not args or args[0] != "--env":
        print("Error: --env flag is required")
        print("Usage: python scripts/rag.py mcp --env <environment>")
        print("Example: python scripts/rag.py mcp --env dev")
        sys.exit(1)

    if len(args) < 2:
        print("Error: --env requires an environment name")
        print("Example: python scripts/rag.py mcp --env dev")
        sys.exit(1)

    env = args[1]
    args = args[2:]

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
        print("Usage: python scripts/rag.py cli|mcp --env <environment> [options]")
        print("\nExamples:")
        print("  python scripts/rag.py cli --env dev status")
        print("  python scripts/rag.py cli --env test search 'query'")
        print("  python scripts/rag.py cli --env dev logs --service postgres")
        print("  python scripts/rag.py mcp --env dev")
        print("\nNote: --env flag is required. This script is for development only.")
        print("      For production, use the system-installed 'rag' CLI.")
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
