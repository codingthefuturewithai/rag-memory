#!/usr/bin/env python3
"""
RAG Memory - Hybrid Cloud Deployment (Render + Neo4j Aura)

This script deploys RAG Memory to cloud using:
- Render: PostgreSQL database and MCP server
- Neo4j Aura: Graph database

Features:
- Creates all services via REST APIs (no manual dashboard steps)
- Detects local Docker data and offers migration
- Fully automated PostgreSQL + Neo4j migration
- Remote Graphiti schema initialization via Bolt
- Comprehensive error handling and verification
- Non-destructive (local data kept safe)

Prerequisites:
- Render API key (create at: https://dashboard.render.com/u/settings#api-keys)
- Neo4j Aura API credentials (create at: https://console.neo4j.io/ → Account → API Credentials)
- Docker running (if migrating local data)
- psql command available
- Python 3.8+ with requests, psycopg, neo4j, graphiti-core, rich libraries

Usage:
    python scripts/deploy_to_cloud.py
    # OR
    uv run python scripts/deploy_to_cloud.py

Environment Variables (optional):
    RENDER_API_KEY - Render API key (will prompt if not set)
    AURA_CLIENT_ID - Aura API client ID (will prompt if not set)
    AURA_CLIENT_SECRET - Aura API client secret (will prompt if not set)
    POSTGRES_PASSWORD - Local PostgreSQL password (default: ragpassword)
    NEO4J_PASSWORD - Local Neo4j password (default: graphiti-password)
"""

import os
import sys
import subprocess
import getpass
import json
import time
import tarfile
import platformdirs
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

# ============================================================================
# Dependency Management
# ============================================================================

def check_and_install_dependencies():
    """Check and install required Python libraries."""
    required = {
        'requests': 'requests',
        'psycopg': 'psycopg[binary]',
        'neo4j': 'neo4j',
        'graphiti_core': 'graphiti-core',
        'rich': 'rich'
    }

    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

check_and_install_dependencies()

import requests
import psycopg
from neo4j import GraphDatabase
from graphiti_core import Graphiti
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

console = Console()

# ============================================================================
# Constants
# ============================================================================

# Local Docker Configuration (from docker-compose.yml)
LOCAL_POSTGRES_CONTAINER = "rag-memory-postgres-local"
LOCAL_NEO4J_CONTAINER = "rag-memory-neo4j-local"
LOCAL_POSTGRES_USER = "raguser"
LOCAL_POSTGRES_DB = "rag_memory"
LOCAL_POSTGRES_DEFAULT_PASSWORD = "ragpassword"
LOCAL_NEO4J_USER = "neo4j"
LOCAL_NEO4J_DEFAULT_PASSWORD = "graphiti-password"

# Render API Configuration
RENDER_API_BASE = "https://api.render.com/v1"
RENDER_API_HEADERS = {"Content-Type": "application/json"}

# Neo4j Aura API Configuration
AURA_API_BASE = "https://api.neo4j.io"
AURA_TOKEN_ENDPOINT = f"{AURA_API_BASE}/oauth/token"
AURA_INSTANCES_ENDPOINT = f"{AURA_API_BASE}/v1/instances"

# Project and Service Names
PROJECT_NAME = "rag-memory"
POSTGRES_SERVICE_NAME = "rag-memory-db"
MCP_SERVICE_NAME = "rag-memory-mcp"

# PostgreSQL Configuration
POSTGRES_VERSION = "16"
POSTGRES_DATABASE_NAME = "ragmemory"

# ============================================================================
# Utility Functions
# ============================================================================

def check_prerequisites() -> bool:
    """Check that required command-line tools are installed."""
    console.print("\n[bold cyan]🔧 Checking prerequisites...[/bold cyan]")

    required_tools = {
        "docker": ["docker", "--version"],
        "psql": ["psql", "--version"],
    }

    all_good = True
    for tool, command in required_tools.items():
        try:
            subprocess.run(
                command,
                capture_output=True,
                check=False
            )
            console.print(f"[green]✓[/green] {tool} installed")
        except FileNotFoundError:
            console.print(f"[red]✗[/red] {tool} not found")
            all_good = False

    return all_good


def check_docker_running() -> bool:
    """Check if Docker is running."""
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            check=False
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_container_exists(container_name: str) -> bool:
    """Check if a specific Docker container exists and is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False
        )
        return container_name in result.stdout
    except Exception:
        return False


# ============================================================================
# Phase 0: Detect Local Data
# ============================================================================

def get_local_postgres_counts() -> Optional[Dict[str, int]]:
    """Get document/chunk counts from local PostgreSQL."""
    try:
        result = subprocess.run(
            [
                "docker", "exec", LOCAL_POSTGRES_CONTAINER,
                "psql", "-U", LOCAL_POSTGRES_USER, "-d", LOCAL_POSTGRES_DB,
                "-t", "-c",
                "SELECT COUNT(*) FROM source_documents; SELECT COUNT(*) FROM document_chunks;"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        if len(lines) >= 2:
            return {
                "documents": int(lines[0]),
                "chunks": int(lines[1])
            }
    except Exception as e:
        console.print(f"[yellow]Warning: Could not get PostgreSQL counts: {e}[/yellow]")

    return None


def get_local_neo4j_counts() -> Optional[Dict[str, int]]:
    """Get node/relationship counts from local Neo4j."""
    try:
        neo4j_password = os.getenv("NEO4J_PASSWORD", LOCAL_NEO4J_DEFAULT_PASSWORD)

        result = subprocess.run(
            [
                "docker", "exec", LOCAL_NEO4J_CONTAINER,
                "cypher-shell", "-u", LOCAL_NEO4J_USER, "-p", neo4j_password,
                "MATCH (n) RETURN count(n) as nodes;"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        lines = [line.strip() for line in result.stdout.strip().split("\n")
                 if line.strip() and not line.startswith("+") and not line.startswith("|")
                 and "nodes" not in line.lower()]

        nodes = int(lines[0]) if lines else 0

        result = subprocess.run(
            [
                "docker", "exec", LOCAL_NEO4J_CONTAINER,
                "cypher-shell", "-u", LOCAL_NEO4J_USER, "-p", neo4j_password,
                "MATCH ()-[r]->() RETURN count(r) as relationships;"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        lines = [line.strip() for line in result.stdout.strip().split("\n")
                 if line.strip() and not line.startswith("+") and not line.startswith("|")
                 and "relationships" not in line.lower()]

        relationships = int(lines[0]) if lines else 0

        return {
            "nodes": nodes,
            "relationships": relationships
        }
    except Exception as e:
        console.print(f"[yellow]Warning: Could not get Neo4j counts: {e}[/yellow]")

    return None


def detect_local_data() -> Tuple[bool, Optional[Dict], Optional[Dict]]:
    """
    Detect if local Docker containers have data.

    Returns:
        (has_data, postgres_counts, neo4j_counts)
    """
    console.print("\n[bold cyan]🔍 Detecting local Docker deployment...[/bold cyan]")

    if not check_docker_running():
        console.print("[yellow]⚠️  Docker is not running[/yellow]")
        return False, None, None

    has_postgres = check_container_exists(LOCAL_POSTGRES_CONTAINER)
    has_neo4j = check_container_exists(LOCAL_NEO4J_CONTAINER)

    if not has_postgres and not has_neo4j:
        console.print("[yellow]⚠️  No local RAG Memory containers found[/yellow]")
        return False, None, None

    console.print(f"[green]✓[/green] PostgreSQL container: {LOCAL_POSTGRES_CONTAINER if has_postgres else 'Not found'}")
    console.print(f"[green]✓[/green] Neo4j container: {LOCAL_NEO4J_CONTAINER if has_neo4j else 'Not found'}")

    pg_counts = get_local_postgres_counts() if has_postgres else None
    neo4j_counts = get_local_neo4j_counts() if has_neo4j else None

    if pg_counts:
        console.print(f"[cyan]  → PostgreSQL: {pg_counts['documents']} documents, {pg_counts['chunks']} chunks[/cyan]")
    if neo4j_counts:
        console.print(f"[cyan]  → Neo4j: {neo4j_counts['nodes']} nodes, {neo4j_counts['relationships']} relationships[/cyan]")

    has_data = (pg_counts and pg_counts['documents'] > 0) or (neo4j_counts and neo4j_counts['nodes'] > 0)

    return has_data, pg_counts, neo4j_counts


# ============================================================================
# Phase 1: Render API - Authentication & Setup
# ============================================================================

def get_render_api_key() -> str:
    """Get Render API key from environment or user input."""
    api_key = os.getenv("RENDER_API_KEY")

    if not api_key:
        console.print("\n[bold yellow]📋 Render API Key Required[/bold yellow]")
        console.print("[dim]Create one at: https://dashboard.render.com/u/settings#api-keys[/dim]\n")
        api_key = getpass.getpass("Enter your Render API key: ")

    return api_key.strip()


def get_owner_id(api_key: str) -> Optional[str]:
    """Get owner/workspace ID from Render API."""
    console.print("\n[bold cyan]🔍 Fetching Render workspace ID...[/bold cyan]")

    try:
        response = requests.get(
            f"{RENDER_API_BASE}/owners",
            headers={
                **RENDER_API_HEADERS,
                "Authorization": f"Bearer {api_key}"
            },
            timeout=30
        )

        if response.status_code == 401:
            console.print("[red]✗ Authentication failed - invalid API key[/red]")
            return None

        response.raise_for_status()
        response_data = response.json()

        owners = [item.get('owner', {}) for item in response_data]

        if not owners or all(not o for o in owners):
            console.print("[red]✗ No workspaces found for this API key[/red]")
            return None

        if len(owners) > 1:
            console.print("\n[bold]Available workspaces:[/bold]")
            for i, owner in enumerate(owners, 1):
                console.print(f"  {i}. {owner.get('name', owner.get('email', 'Unnamed'))}")

            choice = int(Prompt.ask("Select workspace", default="1")) - 1
            selected_owner = owners[choice]
        else:
            selected_owner = owners[0]

        owner_id = selected_owner.get('id')
        owner_name = selected_owner.get('name', selected_owner.get('email', 'Unknown'))
        console.print(f"[green]✓[/green] Using workspace: {owner_name} ({owner_id})")

        return owner_id

    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ Failed to fetch workspace ID: {e}[/red]")
        return None


def create_project(api_key: str, owner_id: str) -> Optional[Dict[str, Any]]:
    """Create a Render project to organize services."""
    console.print("\n[bold cyan]📁 Creating Render project...[/bold cyan]")

    payload = {
        "name": PROJECT_NAME,
        "ownerId": owner_id,
        "environments": [
            {"name": "production"}
        ]
    }

    try:
        response = requests.post(
            f"{RENDER_API_BASE}/projects",
            headers={
                **RENDER_API_HEADERS,
                "Authorization": f"Bearer {api_key}"
            },
            json=payload,
            timeout=30
        )

        if response.status_code == 400:
            error_msg = response.json().get('message', 'Bad request')
            console.print(f"[red]✗ Failed to create project: {error_msg}[/red]")
            return None

        response.raise_for_status()
        project_data = response.json()

        project_id = project_data.get('id')
        project_name = project_data.get('name', PROJECT_NAME)
        environment_ids = project_data.get('environmentIds', [])

        if not environment_ids:
            console.print(f"[red]✗ Project created but no environment ID returned[/red]")
            return None

        environment_id = environment_ids[0]

        console.print(f"[green]✓[/green] Project created: {project_name}")
        console.print(f"[dim]  Project ID: {project_id}[/dim]")
        console.print(f"[dim]  Environment ID: {environment_id}[/dim]")

        return {
            'id': project_id,
            'name': project_name,
            'environment_id': environment_id
        }

    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ Failed to create project: {e}[/red]")
        if hasattr(e, 'response') and e.response is not None:
            console.print(f"[dim]{e.response.text}[/dim]")
        return None


# ============================================================================
# Phase 2: Create PostgreSQL Database (Render)
# ============================================================================

def create_postgres_database(
    api_key: str,
    owner_id: str,
    environment_id: str,
    region: str,
    plan: str
) -> Optional[Dict[str, Any]]:
    """Create PostgreSQL database via Render API."""
    console.print("\n[bold cyan]🗄️  Creating PostgreSQL database on Render...[/bold cyan]")

    payload = {
        "name": POSTGRES_SERVICE_NAME,
        "plan": plan,
        "ownerId": owner_id,
        "environmentId": environment_id,
        "version": POSTGRES_VERSION,
        "databaseName": POSTGRES_DATABASE_NAME,
        "region": region,
        "ipAllowList": [
            {
                "cidrBlock": "0.0.0.0/0",
                "description": "Allow all external connections"
            }
        ]
    }

    try:
        response = requests.post(
            f"{RENDER_API_BASE}/postgres",
            headers={
                **RENDER_API_HEADERS,
                "Authorization": f"Bearer {api_key}"
            },
            json=payload,
            timeout=60
        )

        if response.status_code == 400:
            error_msg = response.json().get('message', 'Bad request')
            console.print(f"[red]✗ Failed to create PostgreSQL: {error_msg}[/red]")
            return None

        response.raise_for_status()
        postgres_data = response.json()

        database_id = postgres_data.get('id')

        console.print(f"[green]✓[/green] PostgreSQL created: {POSTGRES_SERVICE_NAME}")
        console.print(f"[dim]  Database ID: {database_id}[/dim]")

        console.print(f"[dim]Waiting for database to be ready...[/dim]")

        max_wait = 300
        poll_interval = 10
        elapsed = 0
        external_url = None
        internal_url = None
        db_status = None

        while elapsed < max_wait:
            status_response = requests.get(
                f"{RENDER_API_BASE}/postgres/{database_id}",
                headers={
                    **RENDER_API_HEADERS,
                    "Authorization": f"Bearer {api_key}"
                },
                timeout=30
            )

            if status_response.status_code == 200:
                db_data = status_response.json()
                db_status = db_data.get('status')

                if db_status == 'available':
                    conn_response = requests.get(
                        f"{RENDER_API_BASE}/postgres/{database_id}/connection-info",
                        headers={
                            **RENDER_API_HEADERS,
                            "Authorization": f"Bearer {api_key}"
                        },
                        timeout=30
                    )

                    if conn_response.status_code == 200:
                        conn_data = conn_response.json()
                        external_url = conn_data.get('externalConnectionString')
                        internal_url = conn_data.get('internalConnectionString')

                        if external_url and internal_url:
                            console.print(f"[green]✓[/green] Database ready and connection strings available")
                            console.print(f"[dim]Waiting 30s for database to fully initialize SSL...[/dim]")
                            time.sleep(30)
                            break

            console.print(f"[dim]  Status: {db_status or 'unknown'}, waiting... ({elapsed}s)[/dim]", end="\r")
            time.sleep(poll_interval)
            elapsed += poll_interval

        if not external_url or not internal_url:
            console.print(f"\n[red]✗ Database not ready after {max_wait}s (status: {db_status})[/red]")
            console.print(f"[yellow]Check status in Render dashboard[/yellow]")
            return None

        return {
            'id': database_id,
            'external_url': external_url,
            'internal_url': internal_url,
            'name': POSTGRES_SERVICE_NAME
        }

    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ Failed to create PostgreSQL: {e}[/red]")
        if hasattr(e, 'response') and e.response is not None:
            console.print(f"[dim]{e.response.text}[/dim]")
        return None


def enable_pgvector(external_url: str) -> bool:
    """Enable pgvector extension on PostgreSQL database using psql."""
    console.print("\n[bold cyan]🔌 Enabling pgvector extension...[/bold cyan]")

    try:
        result = subprocess.run(
            ["psql", external_url, "-c", "CREATE EXTENSION IF NOT EXISTS vector;"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            console.print("[green]✓[/green] pgvector extension enabled")
            return True
        else:
            console.print(f"[red]✗ Failed to enable pgvector: {result.stderr}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Failed to enable pgvector: {e}[/red]")
        return False


# ============================================================================
# Phase 3: Create Neo4j Aura Instance
# ============================================================================

def get_aura_credentials() -> Tuple[Optional[str], Optional[str]]:
    """Get Aura API credentials from environment or user input."""
    client_id = os.getenv("AURA_CLIENT_ID")
    client_secret = os.getenv("AURA_CLIENT_SECRET")

    if not client_id or not client_secret:
        console.print("\n[bold yellow]📋 Neo4j Aura API Credentials Required[/bold yellow]")
        console.print("[dim]Create at: https://console.neo4j.io/ → Account → API Credentials[/dim]\n")

        if not client_id:
            client_id = Prompt.ask("Enter Aura Client ID")
        if not client_secret:
            client_secret = Prompt.ask("Enter Aura Client Secret", password=True)

    return client_id.strip(), client_secret.strip()


def get_aura_oauth_token(client_id: str, client_secret: str) -> Optional[str]:
    """Get OAuth bearer token for Aura API."""
    console.print("\n[bold cyan]🔑 Getting Aura OAuth token...[/bold cyan]")

    try:
        response = requests.post(
            AURA_TOKEN_ENDPOINT,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            timeout=30
        )

        if response.status_code != 200:
            console.print(f"[red]✗ Failed to get token: {response.status_code}[/red]")
            console.print(f"[dim]{response.text}[/dim]")
            return None

        token = response.json()["access_token"]
        console.print(f"[green]✓[/green] OAuth token obtained")
        return token

    except Exception as e:
        console.print(f"[red]✗ Failed to get OAuth token: {e}[/red]")
        return None


def create_aura_instance(
    token: str,
    region: str,
    memory: str,
    cloud_provider: str,
    instance_name: str = "rag-memory-graph"
) -> Optional[Dict[str, Any]]:
    """Create Neo4j Aura instance via API."""
    console.print("\n[bold cyan]🔗 Creating Neo4j Aura instance...[/bold cyan]")

    # Get tenant ID
    try:
        tenants_response = requests.get(
            f"{AURA_API_BASE}/v1/tenants",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=30
        )

        if tenants_response.status_code != 200:
            console.print(f"[red]✗ Failed to get tenants: {tenants_response.status_code}[/red]")
            return None

        tenants = tenants_response.json()["data"]
        if not tenants:
            console.print("[red]✗ No tenants found in account[/red]")
            return None

        tenant_id = tenants[0]["id"]

    except Exception as e:
        console.print(f"[red]✗ Failed to get tenant ID: {e}[/red]")
        return None

    # Create instance
    payload = {
        "version": "5",
        "region": region,
        "memory": memory,
        "name": instance_name,
        "type": "professional-db",
        "tenant_id": tenant_id,
        "cloud_provider": cloud_provider
    }

    try:
        response = requests.post(
            AURA_INSTANCES_ENDPOINT,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            json=payload,
            timeout=60
        )

        if response.status_code not in [200, 201, 202]:
            console.print(f"[red]✗ Failed to create instance: {response.status_code}[/red]")
            console.print(f"[dim]{response.text}[/dim]")
            return None

        result = response.json()
        data = result.get("data", result)

        instance_id = data.get('id')
        connection_url = data.get('connection_url')
        username = data.get('username')
        password = data.get('password')

        console.print(f"[green]✓[/green] Aura instance created")
        console.print(f"[dim]  Instance ID: {instance_id}[/dim]")
        console.print(f"[dim]  Connection URL: {connection_url}[/dim]")

        return {
            'id': instance_id,
            'connection_url': connection_url,
            'username': username,
            'password': password,
            'name': instance_name
        }

    except Exception as e:
        console.print(f"[red]✗ Failed to create Aura instance: {e}[/red]")
        return None


def wait_for_aura_instance_ready(token: str, instance_id: str, max_wait: int = 300) -> bool:
    """Wait for Aura instance to be ready."""
    console.print(f"\n[bold cyan]⏳ Waiting for Aura instance to be ready...[/bold cyan]")

    start_time = time.time()

    while (time.time() - start_time) < max_wait:
        try:
            response = requests.get(
                f"{AURA_INSTANCES_ENDPOINT}/{instance_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json().get("data", {})
                status = data.get('status', 'unknown')

                console.print(f"[dim]  Status: {status}[/dim]", end="\r")

                if status == 'running':
                    console.print("\n[green]✓[/green] Aura instance is ready")
                    return True

            time.sleep(5)

        except Exception:
            pass

    console.print("\n[yellow]⚠️  Instance did not become ready within timeout[/yellow]")
    return False


def initialize_aura_graphiti_schema(
    connection_url: str,
    password: str,
    openai_api_key: str
) -> bool:
    """Initialize Graphiti schema on Aura via remote Bolt connection."""
    console.print("\n[bold cyan]🔧 Initializing Graphiti schema on Aura...[/bold cyan]")

    try:
        # Set OpenAI API key
        os.environ["OPENAI_API_KEY"] = openai_api_key

        # Initialize Graphiti with remote connection
        graphiti = Graphiti(
            uri=connection_url,
            user="neo4j",
            password=password
        )

        console.print("[green]✓[/green] Graphiti schema initialized")
        return True

    except Exception as e:
        console.print(f"[red]✗ Schema initialization failed: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return False


# ============================================================================
# Phase 4: Create MCP Server (Render)
# ============================================================================

def wait_for_service_ready(api_key: str, service_id: str, max_wait_seconds: int = 900) -> bool:
    """
    Wait for a Render service to be ready/available.

    Polls GET /services/{serviceId}/deploys endpoint to check latest deploy status.
    Returns True when deploy status is 'live', False on failure states.
    Default timeout: 900 seconds (15 minutes) to accommodate MCP server build time (7-10 min)
    """
    console.print(f"\n[bold cyan]⏳ Waiting for service to build and deploy...[/bold cyan]")

    start_time = time.time()

    while (time.time() - start_time) < max_wait_seconds:
        try:
            # Get the latest deploy for this service
            response = requests.get(
                f"{RENDER_API_BASE}/services/{service_id}/deploys",
                headers={
                    **RENDER_API_HEADERS,
                    "Authorization": f"Bearer {api_key}"
                },
                params={"limit": 1},  # Only get the most recent deploy
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                # Response is array of {cursor, deploy} objects
                if data and len(data) > 0:
                    latest_deploy = data[0].get('deploy', data[0])
                    status = latest_deploy.get('status', 'unknown')

                    console.print(f"[dim]  Deploy status: {status}[/dim]", end="\r")

                    if status == 'live':
                        console.print("\n[green]✓[/green] Service is live and ready")
                        return True
                    elif status in ['build_failed', 'deploy_failed', 'failed', 'canceled']:
                        console.print(f"\n[red]✗ Deployment failed with status: {status}[/red]")
                        return False

            time.sleep(10)

        except requests.exceptions.RequestException:
            pass

    console.print("\n[yellow]⚠️  Service did not become ready within timeout[/yellow]")
    return False


def create_mcp_server(
    api_key: str,
    owner_id: str,
    environment_id: str,
    region: str,
    plan: str,
    postgres_url: str,
    neo4j_uri: str,
    neo4j_password: str,
    openai_api_key: str,
    repo_url: str,
    branch: str = "main"
) -> Optional[Dict[str, Any]]:
    """Create MCP server as Docker web service on Render."""
    console.print("\n[bold cyan]🚀 Creating MCP server on Render...[/bold cyan]")

    repo_url = repo_url.rstrip('.git')

    if not repo_url.startswith(('https://github.com/', 'https://gitlab.com/')):
        console.print("[red]✗ Invalid repository URL format[/red]")
        console.print("[dim]  Expected: https://github.com/username/repository[/dim]")
        console.print(f"[dim]  Received: {repo_url}[/dim]")
        return None

    env_vars = [
        {"key": "DATABASE_URL", "value": postgres_url},
        {"key": "NEO4J_URI", "value": neo4j_uri},
        {"key": "NEO4J_USER", "value": "neo4j"},
        {"key": "NEO4J_PASSWORD", "value": neo4j_password},
        {"key": "OPENAI_API_KEY", "value": openai_api_key},
        {"key": "PYTHONUNBUFFERED", "value": "1"},
    ]

    payload = {
        "type": "web_service",
        "name": "rag-memory-mcp",
        "ownerId": owner_id,
        "environmentId": environment_id,
        "repo": repo_url,
        "branch": branch,
        "autoDeploy": "yes",
        "envVars": env_vars,
        "serviceDetails": {
            "runtime": "docker",
            "plan": plan,
            "region": region,
            "healthCheckPath": "/health",
            "envSpecificDetails": {
                "dockerfilePath": "deploy/docker/Dockerfile",
                "dockerContext": "."
            }
        }
    }

    try:
        response = requests.post(
            f"{RENDER_API_BASE}/services",
            headers={
                **RENDER_API_HEADERS,
                "Authorization": f"Bearer {api_key}"
            },
            json=payload,
            timeout=60
        )

        if response.status_code == 400:
            error_msg = response.json().get('message', 'Bad request')
            console.print(f"[red]✗ Failed to create MCP server: {error_msg}[/red]")
            return None

        response.raise_for_status()
        service_data = response.json()

        service = service_data.get('service', {})
        service_id = service.get('id')
        service_url = service.get('serviceDetails', {}).get('url')

        console.print(f"[green]✓[/green] MCP server creation request accepted")
        console.print(f"[dim]  Service ID: {service_id}[/dim]")
        console.print(f"[dim]  Region: {region}[/dim]")

        # Wait for build and deployment to complete
        if not wait_for_service_ready(api_key, service_id):
            console.print("[red]✗ MCP server build/deployment failed[/red]")
            console.print("[yellow]  Check Render dashboard for build logs[/yellow]")
            return None

        # Get updated service info with URL
        response = requests.get(
            f"{RENDER_API_BASE}/services/{service_id}",
            headers={
                **RENDER_API_HEADERS,
                "Authorization": f"Bearer {api_key}"
            },
            timeout=30
        )
        if response.status_code == 200:
            service = response.json()
            service_url = service.get('serviceDetails', {}).get('url')

        console.print(f"\n[bold green]🌐 MCP Server Deployed Successfully:[/bold green]")
        console.print(f"[green]  URL: {service_url}[/green]")
        console.print(f"[dim]  SSE endpoint: {service_url}/sse[/dim]")
        console.print(f"[dim]  Health check: {service_url}/health[/dim]")

        return {
            'id': service_id,
            'url': service_url,
            'region': region
        }

    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ Failed to create MCP server: {e}[/red]")
        if hasattr(e, 'response') and e.response is not None:
            console.print(f"[dim]{e.response.text}[/dim]")
        return None


# ============================================================================
# Phase 5: Data Migration - PostgreSQL
# ============================================================================

def export_postgres_data(backup_dir: Path) -> Optional[Path]:
    """Export PostgreSQL database using pg_dump."""
    console.print("\n[bold cyan]📦 Exporting PostgreSQL data...[/bold cyan]")

    backup_file = backup_dir / "postgres_export.sql"

    try:
        cmd = [
            "docker", "exec", LOCAL_POSTGRES_CONTAINER,
            "pg_dump",
            "-U", LOCAL_POSTGRES_USER,
            "-d", LOCAL_POSTGRES_DB,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges"
        ]

        with open(backup_file, "w") as f:
            subprocess.run(cmd, stdout=f, check=True, text=True)

        size_mb = backup_file.stat().st_size / (1024 * 1024)
        console.print(f"[green]✓[/green] PostgreSQL exported ({size_mb:.2f} MB)")
        return backup_file

    except Exception as e:
        console.print(f"[red]✗ Export failed: {e}[/red]")
        return None


def import_postgres_data(backup_file: Path, external_url: str) -> bool:
    """Import PostgreSQL data to Render."""
    console.print("\n[bold cyan]📤 Importing PostgreSQL to Render...[/bold cyan]")

    try:
        cmd = ["psql", external_url, "--single-transaction"]

        with open(backup_file, "r") as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                capture_output=True,
                text=True,
                check=False
            )

        if result.returncode != 0:
            if "already exists" in result.stderr:
                console.print("[yellow]  ⚠ Some objects already existed (expected)[/yellow]")
            else:
                console.print(f"[red]✗ Import failed:\n{result.stderr}[/red]")
                return False

        console.print("[green]✓[/green] PostgreSQL data imported successfully")
        return True

    except Exception as e:
        console.print(f"[red]✗ Import failed: {e}[/red]")
        return False


# ============================================================================
# Phase 6: Data Migration - Neo4j to Aura
# ============================================================================

def export_neo4j_dump(backup_dir: Path) -> Optional[Path]:
    """
    Export Neo4j database using neo4j-admin database dump.

    IMPORTANT: Must stop Neo4j first (dump requires offline database).
    Uses temporary container approach to dump from stopped database volume.
    """
    console.print("\n[bold cyan]📦 Exporting Neo4j database...[/bold cyan]")

    dump_file = backup_dir / "neo4j.dump"

    # Get system-installed docker-compose path
    config_dir = Path(platformdirs.user_config_dir('rag-memory', appauthor=False))
    docker_compose_file = config_dir / "docker-compose.yml"

    if not docker_compose_file.exists():
        console.print(f"[red]✗ Docker compose file not found at: {docker_compose_file}[/red]")
        console.print("[yellow]  Have you run the RAG Memory setup? (uv run rag init)[/yellow]")
        return None

    try:
        # Stop Neo4j container
        console.print("  → Stopping Neo4j container...")
        subprocess.run(
            ["docker", "compose", "-f", str(docker_compose_file),
             "stop", "neo4j-local"],
            check=True,
            capture_output=True
        )

        # Create dump using temporary container with mounted volume
        # This avoids trying to exec into a stopped container
        console.print("  → Creating dump via temporary container...")
        volume_name = "rag-memory_neo4j_data_local"
        # Docker requires ABSOLUTE path for volume mounts
        absolute_backup_dir = backup_dir.resolve()
        subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{volume_name}:/data",
                "-v", f"{absolute_backup_dir}:/dumps",
                "neo4j:5-community",
                "neo4j-admin", "database", "dump", "neo4j",
                "--to-path=/dumps"
            ],
            check=True,
            capture_output=True
        )

        # Restart Neo4j container
        console.print("  → Restarting Neo4j container...")
        subprocess.run(
            ["docker", "compose", "-f", str(docker_compose_file),
             "start", "neo4j-local"],
            check=True,
            capture_output=True
        )

        size_mb = dump_file.stat().st_size / (1024 * 1024)
        console.print(f"[green]✓[/green] Neo4j dump created ({size_mb:.2f} MB)")
        return dump_file

    except Exception as e:
        console.print(f"[red]✗ Export failed: {e}[/red]")
        # Ensure Neo4j is restarted even if dump fails
        config_dir = Path(platformdirs.user_config_dir('rag-memory', appauthor=False))
        docker_compose_file = config_dir / "docker-compose.yml"
        subprocess.run(
            ["docker", "compose", "-f", str(docker_compose_file),
             "start", "neo4j-local"],
            check=False,
            capture_output=True
        )
        return None


def upload_neo4j_to_aura(
    dump_file: Path,
    aura_connection_url: str,
    aura_password: str
) -> bool:
    """Upload Neo4j dump to Aura using neo4j-admin database upload."""
    console.print("\n[bold cyan]📤 Uploading Neo4j data to Aura...[/bold cyan]")

    try:
        # Copy dump into container
        console.print("  → Copying dump into local container...")
        subprocess.run(
            ["docker", "cp",
             str(dump_file),
             f"{LOCAL_NEO4J_CONTAINER}:/dumps/neo4j.dump"],
            check=True
        )

        # Upload via neo4j-admin
        console.print("  → Uploading to Aura via Bolt protocol...")
        console.print("  → This may take several minutes for large databases...")

        subprocess.run(
            [
                "docker", "exec",
                "-e", f"NEO4J_USERNAME=neo4j",
                "-e", f"NEO4J_PASSWORD={aura_password}",
                LOCAL_NEO4J_CONTAINER,
                "neo4j-admin", "database", "upload", "neo4j",
                "--from-path=/dumps",
                f"--to-uri={aura_connection_url}",
                "--overwrite-destination=true"
            ],
            check=True,
            timeout=600
        )

        console.print("[green]✓[/green] Neo4j data uploaded to Aura successfully")
        return True

    except subprocess.TimeoutExpired:
        console.print("[red]✗ Upload timed out (may still be processing)[/red]")
        return False
    except Exception as e:
        console.print(f"[red]✗ Upload failed: {e}[/red]")
        return False


# ============================================================================
# Phase 7: Verification
# ============================================================================

def verify_postgres(external_url: str, expected_counts: Dict) -> bool:
    """Verify PostgreSQL data was imported correctly."""
    console.print("\n[bold cyan]🔍 Verifying PostgreSQL...[/bold cyan]")

    try:
        result = subprocess.run(
            ["psql", external_url, "-t", "-c", "SELECT COUNT(*) FROM source_documents"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            console.print(f"[red]✗ Failed to query documents: {result.stderr}[/red]")
            return False
        doc_count = int(result.stdout.strip())

        result = subprocess.run(
            ["psql", external_url, "-t", "-c", "SELECT COUNT(*) FROM document_chunks"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            console.print(f"[red]✗ Failed to query chunks: {result.stderr}[/red]")
            return False
        chunk_count = int(result.stdout.strip())

        docs_match = doc_count == expected_counts.get("documents", 0)
        chunks_match = chunk_count == expected_counts.get("chunks", 0)

        console.print(
            f"  Documents: {doc_count} (expected {expected_counts.get('documents', 0)}) "
            f"[{'green' if docs_match else 'red'}]{'✓' if docs_match else '✗'}[/]"
        )
        console.print(
            f"  Chunks: {chunk_count} (expected {expected_counts.get('chunks', 0)}) "
            f"[{'green' if chunks_match else 'red'}]{'✓' if chunks_match else '✗'}[/]"
        )

        return docs_match and chunks_match

    except Exception as e:
        console.print(f"[red]✗ Verification failed: {e}[/red]")
        return False


# ============================================================================
# Phase 8: Configuration Prompts
# ============================================================================

def prompt_for_configuration() -> Dict[str, str]:
    """Interactively gather deployment configuration from user."""
    console.print("\n[bold cyan]⚙️  Deployment Configuration[/bold cyan]")

    # Region selection
    console.print("\n[bold]Select region:[/bold]")
    regions = ["oregon", "ohio", "virginia", "frankfurt", "singapore"]
    for i, r in enumerate(regions, 1):
        console.print(f"  {i}. {r}")

    region_idx = int(Prompt.ask("Region", default="1")) - 1
    region = regions[region_idx]

    # PostgreSQL plan
    console.print("\n[bold]PostgreSQL Plan:[/bold]")
    console.print("[dim]Valid plans: basic_256mb, basic_1gb, basic_4gb, pro_4gb, etc.[/dim]")
    postgres_plan = Prompt.ask("Plan", default="basic_256mb")

    # Aura configuration
    console.print("\n[bold]Neo4j Aura Configuration:[/bold]")

    aura_regions_map = {
        "oregon": "us-west-2",
        "ohio": "us-east-2",
        "virginia": "us-east-1",
        "frankfurt": "eu-central-1",
        "singapore": "ap-southeast-1"
    }
    aura_region = aura_regions_map.get(region, "us-east-1")

    console.print(f"[dim]Using Aura region: {aura_region} (matched to Render region)[/dim]")

    console.print("\n[bold]Aura Instance Size:[/bold]")
    console.print("[dim]Valid sizes: 1GB, 2GB, 4GB, 8GB, 16GB, etc.[/dim]")
    aura_memory = Prompt.ask("Memory", default="2GB")

    console.print("\n[bold]Cloud Provider for Aura:[/bold]")
    console.print("[dim]Options: aws, gcp, azure[/dim]")
    aura_cloud = Prompt.ask("Provider", default="aws")

    return {
        "region": region,
        "postgres_plan": postgres_plan,
        "aura_region": aura_region,
        "aura_memory": aura_memory,
        "aura_cloud": aura_cloud
    }


# ============================================================================
# Main Deployment Flow
# ============================================================================

def main():
    """Main deployment workflow."""
    console.print("\n" + "="*70)
    console.print(Panel.fit(
        "[bold cyan]RAG Memory - Hybrid Cloud Deployment[/bold cyan]\n\n"
        "Render: PostgreSQL + MCP Server\n"
        "Neo4j Aura: Graph Database\n\n"
        "[yellow]Note: Requires paid Render plan (free tier not supported via API)[/yellow]",
        border_style="cyan"
    ))

    # Prerequisites
    if not check_prerequisites():
        console.print("\n[red]✗ Prerequisites check failed. Please install missing tools.[/red]")
        sys.exit(1)

    # Detect local data
    has_data, pg_counts, neo4j_counts = detect_local_data()

    migrate_data = False
    if has_data:
        console.print("\n[bold yellow]📊 Local data detected![/bold yellow]")
        migrate_data = Confirm.ask(
            "\nDo you want to migrate your local data to cloud?",
            default=True
        )

        if not migrate_data:
            console.print("[yellow]Skipping migration. Proceeding with fresh deployment.[/yellow]")
    else:
        console.print("\n[dim]No local data found. Proceeding with fresh deployment.[/dim]")

    # Get Render API key
    render_api_key = get_render_api_key()
    owner_id = get_owner_id(render_api_key)

    if not owner_id:
        console.print("[red]✗ Failed to get workspace ID. Exiting.[/red]")
        sys.exit(1)

    # Get Aura credentials
    aura_client_id, aura_client_secret = get_aura_credentials()

    # Create project
    project_info = create_project(render_api_key, owner_id)

    if not project_info:
        console.print("[red]✗ Failed to create project. Exiting.[/red]")
        sys.exit(1)

    environment_id = project_info['environment_id']

    # Configuration
    config = prompt_for_configuration()

    # Get OpenAI API key
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        console.print("\n[bold cyan]OpenAI API Key Required[/bold cyan]")
        console.print("This is needed for:")
        console.print("  • Neo4j Graphiti schema initialization")
        console.print("  • MCP server embeddings and graph extraction")
        console.print()
        openai_api_key = Prompt.ask(
            "Enter your OpenAI API key (sk-...)",
            password=True
        )

    # Confirm
    console.print("\n[bold]Deployment Summary:[/bold]")
    console.print(f"  Project: {project_info['name']}")
    console.print(f"  Region: {config['region']}")
    console.print(f"  PostgreSQL (Render): {config['postgres_plan']}")
    console.print(f"  Neo4j (Aura): {config['aura_memory']} on {config['aura_cloud']}")
    console.print(f"  Migrate data: {'Yes' if migrate_data else 'No'}")

    if not Confirm.ask("\nProceed with deployment?", default=True):
        console.print("[yellow]Deployment cancelled.[/yellow]")
        sys.exit(0)

    # Create PostgreSQL
    postgres_info = create_postgres_database(
        render_api_key,
        owner_id,
        environment_id,
        config['region'],
        config['postgres_plan']
    )

    if not postgres_info:
        console.print("[red]✗ Failed to create PostgreSQL. Exiting.[/red]")
        sys.exit(1)

    if not enable_pgvector(postgres_info['external_url']):
        console.print("[red]✗ Failed to enable pgvector. Exiting.[/red]")
        sys.exit(1)

    # Wait for database to fully initialize SSL and be ready
    console.print("Waiting 30s for database to fully stabilize...")
    time.sleep(30)

    # Run PostgreSQL migrations
    console.print("\n[bold cyan]🔧 Running database migrations...[/bold cyan]")

    original_db_url = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = postgres_info['external_url']

    try:
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            console.print("[green]✓[/green] Database schema created")
        else:
            console.print(f"[red]✗ Migration failed: {result.stderr}[/red]")
            console.print("[yellow]Continuing anyway - tables might already exist[/yellow]")
    finally:
        if original_db_url:
            os.environ['DATABASE_URL'] = original_db_url
        else:
            os.environ.pop('DATABASE_URL', None)

    # Create Aura instance
    aura_token = get_aura_oauth_token(aura_client_id, aura_client_secret)

    if not aura_token:
        console.print("[red]✗ Failed to get Aura token. Exiting.[/red]")
        sys.exit(1)

    aura_info = create_aura_instance(
        aura_token,
        config['aura_region'],
        config['aura_memory'],
        config['aura_cloud']
    )

    if not aura_info:
        console.print("[red]✗ Failed to create Aura instance. Exiting.[/red]")
        sys.exit(1)

    # Wait for Aura ready
    if not wait_for_aura_instance_ready(aura_token, aura_info['id']):
        console.print("[yellow]⚠️  Aura instance may not be fully ready yet[/yellow]")

    # Initialize Graphiti schema
    if not initialize_aura_graphiti_schema(
        aura_info['connection_url'],
        aura_info['password'],
        openai_api_key
    ):
        console.print("[red]✗ Graphiti schema initialization failed - this is REQUIRED[/red]")
        console.print("[yellow]  Aura will not work without Graphiti schema[/yellow]")
        sys.exit(1)

    # Data migration
    neo4j_migrated = False

    if migrate_data:
        backup_dir = Path("backups") / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"\n[dim]Backup directory: {backup_dir}[/dim]")

        # PostgreSQL migration
        pg_backup = export_postgres_data(backup_dir)
        if pg_backup:
            import_postgres_data(pg_backup, postgres_info['external_url'])
            verify_postgres(postgres_info['external_url'], pg_counts or {})

        # Neo4j migration
        neo4j_dump = export_neo4j_dump(backup_dir)
        if neo4j_dump:
            neo4j_migrated = upload_neo4j_to_aura(
                neo4j_dump,
                aura_info['connection_url'],
                aura_info['password']
            )

    # Optional MCP deployment
    mcp_info = None
    deploy_mcp = Prompt.ask(
        "\n[bold]Deploy MCP server to Render?[/bold]",
        choices=["yes", "no"],
        default="no"
    )

    if deploy_mcp == "yes":
        mcp_repo = Prompt.ask(
            "GitHub repository URL for RAG Memory",
            default="https://github.com/yourusername/rag-memory"
        )

        mcp_branch = Prompt.ask(
            "Git branch to deploy",
            default="main"
        )

        mcp_plan = Prompt.ask(
            "MCP server plan",
            default="starter"
        )

        mcp_info = create_mcp_server(
            api_key=render_api_key,
            owner_id=owner_id,
            environment_id=environment_id,
            region=config['region'],
            plan=mcp_plan,
            postgres_url=postgres_info['external_url'],
            neo4j_uri=aura_info['connection_url'],
            neo4j_password=aura_info['password'],
            openai_api_key=openai_api_key,
            repo_url=mcp_repo,
            branch=mcp_branch
        )

    # Display results
    console.print("\n" + "="*70)

    all_succeeded = True
    status_details = []

    if migrate_data and not neo4j_migrated:
        all_succeeded = False
        status_details.append("Neo4j data migration failed")

    if deploy_mcp == "yes" and not mcp_info:
        all_succeeded = False
        status_details.append("MCP server deployment failed")

    if all_succeeded:
        status_line = f"[bold green]✅ Deployment Complete![/bold green]\n\n"
    else:
        status_line = f"[bold yellow]⚠️  Deployment Partially Complete[/bold yellow]\n"
        status_line += f"[yellow]Issues: {', '.join(status_details)}[/yellow]\n\n"

    output_msg = (
        status_line +
        f"[bold]PostgreSQL (Render):[/bold]\n"
        f"  External URL: {postgres_info['external_url']}\n"
        f"  Database: {POSTGRES_DATABASE_NAME}\n"
    )

    if migrate_data:
        output_msg += f"  [green]✓[/green] Data migrated successfully\n"

    output_msg += (
        f"\n[bold]Neo4j (Aura):[/bold]\n"
        f"  Connection URL: {aura_info['connection_url']}\n"
        f"  Username: {aura_info['username']}\n"
        f"  Password: {aura_info['password'][:20]}...\n"
        f"  Console: https://console.neo4j.io/\n"
    )

    if migrate_data:
        if neo4j_migrated:
            output_msg += f"  [green]✓[/green] Data migrated successfully\n"
        else:
            output_msg += f"  [red]✗[/red] Data migration failed\n"

    output_msg += "\n"

    if mcp_info:
        output_msg += (
            f"[bold]MCP Server (Render):[/bold]\n"
            f"  URL: {mcp_info['url']}\n"
            f"  SSE Endpoint: {mcp_info['url']}/sse\n"
            f"  Health Check: {mcp_info['url']}/health\n"
        )

    panel_title = "🎉 Success" if all_succeeded else "⚠️  Partial Success"
    panel_style = "green" if all_succeeded else "yellow"

    console.print(Panel.fit(
        output_msg,
        title=panel_title,
        border_style=panel_style
    ))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Deployment cancelled by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ Unexpected error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)
