#!/usr/bin/env python3
"""
RAG Memory Local Setup Script

One-command setup for local development:
1. Checks Docker installed
2. Checks if containers already running
3. Prompts for OpenAI API key
4. Detects available ports
5. Creates .env.local with configuration
6. Builds and starts containers
7. Validates all services are healthy
8. Provides connection details for exploration

Cross-platform: macOS, Linux, Windows (with Docker Desktop)
"""

import os
import sys
import socket
import subprocess
import time
import signal
from pathlib import Path
from typing import Tuple, Optional
import json


class Colors:
    """ANSI color codes for terminal output"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"


def print_header(text: str):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def run_command(cmd: list, check: bool = True) -> Tuple[int, str, str]:
    """Run shell command and return exit code, stdout, stderr"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def check_docker_installed() -> bool:
    """Check if Docker is installed"""
    print_header("STEP 1: Checking Docker Installation")

    code, _, _ = run_command(["docker", "--version"])

    if code == 0:
        print_success("Docker is installed")
        return True

    print_error("Docker is not installed")
    print_info("Please install Docker Desktop from: https://www.docker.com/products/docker-desktop")
    print_info("After installation, run this script again")
    return False


def check_docker_running() -> bool:
    """Check if Docker daemon is running"""
    print_header("STEP 2: Checking Docker Daemon")

    code, _, _ = run_command(["docker", "ps"])

    if code == 0:
        print_success("Docker daemon is running")
        return True

    print_error("Docker daemon is not running")
    print_info("Start Docker Desktop and try again")
    return False


def check_existing_containers() -> bool:
    """Check if RAG Memory containers are already running"""
    print_header("STEP 3: Checking for Existing RAG Memory Containers")

    code, stdout, _ = run_command(["docker-compose", "-f", "docker-compose.local.yml", "ps"])

    if code != 0:
        print_info("No existing containers found")
        return False

    # Check if any RAG Memory containers are running
    if "rag-memory" in stdout and ("Up" in stdout or "running" in stdout):
        print_warning("Found existing RAG Memory containers")
        print_warning("This will destroy any data in PostgreSQL and Neo4j")

        response = input(f"\n{Colors.YELLOW}Proceed with setup? This will overwrite .env.local and rebuild containers (yes/no): {Colors.RESET}").strip().lower()

        if response != "yes":
            print_info("Setup cancelled")
            return True

        print_info("Stopping and removing existing containers...")
        run_command(["docker-compose", "-f", "docker-compose.local.yml", "down", "-v"])
        print_success("Existing containers removed")
        return False

    print_info("No existing RAG Memory containers running")
    return False


def check_env_local_exists() -> bool:
    """Check if .env.local already exists"""
    print_header("STEP 4: Checking Configuration")

    env_local = Path(".env.local")

    if not env_local.exists():
        print_info("No existing .env.local found")
        return False

    print_warning(".env.local already exists")
    response = input(f"\n{Colors.YELLOW}Overwrite and reconfigure? (yes/no): {Colors.RESET}").strip().lower()

    if response == "yes":
        env_local.unlink()
        print_success(".env.local removed")
        return False

    print_info("Setup cancelled")
    return True


def prompt_for_api_key() -> str:
    """Prompt user for OpenAI API key"""
    print_header("STEP 5: OpenAI API Key")

    print_info("You need an OpenAI API key to generate embeddings")
    print_info("Get one here: https://platform.openai.com/api/keys")
    print()

    while True:
        api_key = input(f"{Colors.CYAN}Enter your OpenAI API key (sk-...): {Colors.RESET}").strip()

        if api_key.startswith("sk-") and len(api_key) > 20:
            print_success(f"API key accepted: {api_key[:20]}...{api_key[-4:]}")
            return api_key

        print_error("Invalid API key format. Must start with 'sk-' and be at least 20 characters")


def is_port_available(port: int) -> bool:
    """Check if a port is available using a test HTTP server"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result != 0
    except Exception:
        return True


def find_available_ports() -> dict:
    """Find available ports for services"""
    print_header("STEP 6: Finding Available Ports")

    default_ports = {
        "postgres": 54320,
        "neo4j_http": 7474,
        "neo4j_bolt": 7687,
        "mcp": 8000,
    }

    available_ports = {}

    for service, port in default_ports.items():
        original_port = port
        max_attempts = 10
        attempt = 0

        while attempt < max_attempts:
            if is_port_available(port):
                available_ports[service] = port
                if port == original_port:
                    print_success(f"{service}: {port} (default)")
                else:
                    print_warning(f"{service}: {port} (default {original_port} was unavailable)")
                break

            port += 1
            attempt += 1

        if attempt >= max_attempts:
            print_error(f"Could not find available port for {service}")
            return None

    return available_ports


def configure_directory_mounts() -> list:
    """
    Prompt user for read-only directory mounts for file/directory ingestion.

    Returns:
        List of mount configurations with 'path' and 'read_only' keys
    """
    print_header("STEP 7: Configure Directory Access for File Ingestion")

    print_info("The MCP server needs read-only access to directories on your system")
    print_info("to ingest files and documents.\n")

    mounts = []

    # Detect home directory
    home_dir = str(Path.home())
    print_info(f"Detected home directory: {home_dir}")
    print_info("We recommend mounting your home directory as read-only.\n")

    use_home = input(f"{Colors.CYAN}Mount home directory as read-only? (yes/no, default: yes): {Colors.RESET}").strip().lower()
    if use_home != "no":
        mounts.append({
            "path": home_dir,
            "read_only": True
        })
        print_success(f"Added mount: {home_dir} (read-only)")

    # Option to add custom directories
    while True:
        add_more = input(f"\n{Colors.CYAN}Add additional directories? (yes/no, default: no): {Colors.RESET}").strip().lower()
        if add_more == "no" or add_more == "":
            break

        custom_path = input(f"{Colors.CYAN}Enter directory path: {Colors.RESET}").strip()

        # Validate directory exists and is readable
        try:
            path_obj = Path(custom_path).expanduser().resolve()
            if not path_obj.exists():
                print_error(f"Directory does not exist: {path_obj}")
                continue

            if not path_obj.is_dir():
                print_error(f"Not a directory: {path_obj}")
                continue

            # Try to list directory to verify readability
            try:
                list(path_obj.iterdir())
            except PermissionError:
                print_error(f"Directory is not readable: {path_obj}")
                continue

            mounts.append({
                "path": str(path_obj),
                "read_only": True
            })
            print_success(f"Added mount: {path_obj} (read-only)")
        except Exception as e:
            print_error(f"Invalid path: {e}")

    if not mounts:
        print_warning("No directories configured for file ingestion")
        print_warning("The MCP server will not be able to ingest files from your system")
        response = input(f"\n{Colors.YELLOW}Continue without any mounted directories? (yes/no): {Colors.RESET}").strip().lower()
        if response != "yes":
            print_info("Setup cancelled")
            return None

    return mounts


def create_config_yaml(api_key: str, ports: dict, mounts: list):
    """Create YAML configuration file in OS-standard location"""
    print_header("STEP 8: Creating Configuration File")

    import platformdirs
    import yaml

    # Get OS-appropriate config directory
    config_dir = Path(platformdirs.user_config_dir('rag-memory', appauthor=False))
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'config.yaml'

    config = {
        'server': {
            'openai_api_key': api_key,
            'database_url': f'postgresql://raguser:ragpassword@localhost:{ports["postgres"]}/rag_memory',
            'neo4j_uri': f'bolt://localhost:{ports["neo4j_bolt"]}',
            'neo4j_user': 'neo4j',
            'neo4j_password': 'graphiti-password'
        },
        'mounts': mounts if mounts else []
    }

    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print_success(f"Configuration created: {config_path}")
        return True
    except Exception as e:
        print_error(f"Failed to create configuration: {e}")
        return False


def build_and_start_containers() -> bool:
    """Build and start Docker containers"""
    print_header("STEP 8: Building and Starting Containers")

    print_info("Building Docker images...")
    code, _, stderr = run_command(["docker-compose", "-f", "docker-compose.local.yml", "build"])

    if code != 0:
        print_error(f"Build failed: {stderr}")
        return False

    print_success("Build completed")

    print_info("Starting containers...")
    code, _, stderr = run_command(["docker-compose", "-f", "docker-compose.local.yml", "up", "-d"])

    if code != 0:
        print_error(f"Failed to start containers: {stderr}")
        return False

    print_success("Containers started")
    return True


def wait_for_health_checks(ports: dict, timeout_seconds: int = 300, check_interval: int = 30) -> bool:
    """Wait for all services to be healthy with status updates"""
    print_header("STEP 9: Waiting for Services to Be Ready")

    print_info(f"Checking services every {check_interval} seconds (timeout: {timeout_seconds}s)")

    start_time = time.time()
    checks_performed = 0

    while time.time() - start_time < timeout_seconds:
        elapsed = int(time.time() - start_time)
        checks_performed += 1

        print_info(f"[{elapsed}s] Health check #{checks_performed}...")

        # Check PostgreSQL
        pg_code, _, _ = run_command([
            "docker", "exec", "rag-memory-postgres",
            "pg_isready", "-U", "raguser"
        ])
        pg_ready = pg_code == 0

        # Check Neo4j
        neo4j_code, _, _ = run_command([
            "docker", "exec", "rag-memory-neo4j",
            "curl", "-s", "-f", f"http://localhost:7474/browser"
        ])
        neo4j_ready = neo4j_code == 0

        # Check MCP
        mcp_code, _, _ = run_command(["docker", "ps", "-f", "name=rag-memory-mcp"])
        mcp_running = "rag-memory-mcp" in mcp_code

        if pg_ready and neo4j_ready and mcp_running:
            print_success("PostgreSQL is ready")
            print_success("Neo4j is ready")
            print_success("MCP server is running")
            return True

        if not pg_ready:
            print_info("  - PostgreSQL: waiting...")
        else:
            print_success("  - PostgreSQL: ready")

        if not neo4j_ready:
            print_info("  - Neo4j: waiting...")
        else:
            print_success("  - Neo4j: ready")

        if not mcp_running:
            print_info("  - MCP: waiting...")
        else:
            print_success("  - MCP: running")

        if time.time() - start_time < timeout_seconds:
            time.sleep(check_interval)

    print_error(f"Services did not become ready within {timeout_seconds} seconds")
    return False


def validate_schemas(ports: dict) -> bool:
    """Validate that database schemas were created correctly"""
    print_header("STEP 10: Validating Database Schemas")

    # Check PostgreSQL schema
    print_info("Checking PostgreSQL schema...")
    code, stdout, _ = run_command([
        "docker", "exec", "rag-memory-postgres",
        "psql", "-U", "raguser", "-d", "rag_memory", "-c",
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
    ])

    if code == 0 and "3" in stdout:
        print_success("PostgreSQL schema validated (3 tables found)")
    else:
        print_error("PostgreSQL schema validation failed")
        return False

    # Check Neo4j
    print_info("Checking Neo4j...")
    code, _, _ = run_command([
        "docker", "exec", "rag-memory-neo4j",
        "cypher-shell", "-u", "neo4j", "-p", "graphiti-password",
        "MATCH (n) RETURN COUNT(n)"
    ])

    if code == 0:
        print_success("Neo4j is accessible")
    else:
        print_warning("Could not verify Neo4j schema (may still be initializing)")

    return True


def print_connection_info(ports: dict):
    """Print connection details and URLs for exploration"""
    print_header("STEP 11: Connection Information")

    print_info("RAG Memory is now running! Here's how to explore your setup:")
    print()

    print(f"{Colors.BOLD}PostgreSQL{Colors.RESET}")
    print(f"  Connection String: postgresql://raguser:ragpassword@localhost:{ports['postgres']}/rag_memory")
    print(f"  Environment variables in .env.local:")
    print(f"    - DATABASE_URL")
    print(f"    - POSTGRES_HOST: localhost")
    print(f"    - POSTGRES_PORT: {ports['postgres']}")
    print(f"    - POSTGRES_USER: raguser")
    print(f"    - POSTGRES_PASSWORD: ragpassword")
    print(f"  Tools:")
    print(f"    - DBeaver (free): https://dbeaver.io")
    print(f"    - psql command line: psql -U raguser -h localhost -p {ports['postgres']} -d rag_memory")
    print(f"    - VS Code PostgreSQL extension")
    print()

    print(f"{Colors.BOLD}Neo4j Browser{Colors.RESET}")
    print(f"  URL: http://localhost:{ports['neo4j_http']}")
    print(f"  Username: neo4j")
    print(f"  Password: graphiti-password")
    print(f"  Environment variables in .env.local:")
    print(f"    - NEO4J_URI: bolt://localhost:{ports['neo4j_bolt']}")
    print(f"    - NEO4J_USER: neo4j")
    print(f"    - NEO4J_PASSWORD: graphiti-password")
    print()
    print(f"  Try this query in the browser to verify connection:")
    print(f"    {Colors.CYAN}MATCH (n) RETURN COUNT(n) as total_nodes{Colors.RESET}")
    print(f"  (Will return 0 until you populate your knowledge base)")
    print()

    print(f"{Colors.BOLD}MCP Server{Colors.RESET}")
    print(f"  Running on: localhost:{ports['mcp']}")
    print(f"  For Claude Code integration: Connect to http://localhost:{ports['mcp']}")
    print()

    print(f"{Colors.BOLD}Next Steps{Colors.RESET}")
    print(f"  1. Create a collection: Use the 'create_collection' MCP tool")
    print(f"  2. Ingest documents: Use the 'ingest_text' or 'ingest_file' tools")
    print(f"  3. Search: Use the 'search_documents' tool")
    print(f"  4. Explore in Neo4j: Run 'MATCH (n) RETURN n LIMIT 10'")
    print()


def main():
    """Main setup flow"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}RAG Memory Setup Script{Colors.RESET}")
    print(f"Cross-platform local development environment setup\n")

    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    print_info(f"Working directory: {project_root}")

    # Step 1: Check Docker
    if not check_docker_installed():
        sys.exit(1)

    # Step 2: Check Docker running
    if not check_docker_running():
        sys.exit(1)

    # Step 3: Check existing containers
    if check_existing_containers():
        sys.exit(0)

    # Step 4: Check if configuration already exists
    # (Check for both old .env.local and new YAML config for migration purposes)
    import platformdirs
    config_dir = Path(platformdirs.user_config_dir('rag-memory', appauthor=False))
    config_path = config_dir / 'config.yaml'
    if config_path.exists():
        print_warning("Configuration file already exists")
        response = input(f"\n{Colors.YELLOW}Overwrite and reconfigure? (yes/no): {Colors.RESET}").strip().lower()
        if response != "yes":
            print_info("Setup cancelled")
            sys.exit(0)

    # Step 5: Get API key
    api_key = prompt_for_api_key()

    # Step 6: Find ports
    ports = find_available_ports()
    if not ports:
        sys.exit(1)

    # Step 7: Configure directory mounts
    mounts = configure_directory_mounts()
    if mounts is None:
        sys.exit(1)

    # Step 8: Create YAML configuration
    if not create_config_yaml(api_key, ports, mounts):
        sys.exit(1)

    # Step 9: Build and start
    if not build_and_start_containers():
        sys.exit(1)

    # Step 10: Wait for health
    if not wait_for_health_checks(ports):
        print_error("Setup completed but services are not responding")
        print_info("Try: docker-compose -f docker-compose.local.yml logs")
        sys.exit(1)

    # Step 11: Validate schemas
    if not validate_schemas(ports):
        print_warning("Schema validation had issues, but setup may still work")

    # Step 12: Print connection info
    print_connection_info(ports)

    print_success("Setup complete! RAG Memory is ready for local development")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
