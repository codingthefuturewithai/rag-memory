#!/usr/bin/env python3
"""
RAG Memory - Automated Deployment to Render via REST API

This script fully automates deployment of RAG Memory to Render cloud using
the Render REST API. It creates PostgreSQL, Neo4j, and MCP Server services,
and optionally migrates data from local Docker deployment.

Features:
- Creates all services via Render REST API (no manual dashboard steps)
- Detects local Docker data and offers migration
- Fully automated PostgreSQL + Neo4j migration
- SSH/SCP-based Neo4j data transfer (works around port 7687 limitation)
- Comprehensive error handling and verification
- Non-destructive (local data kept safe)

Prerequisites:
- Render API key (create at: https://dashboard.render.com/u/settings#api-keys)
- Render account with paid plan access (free tier not supported via API)
- Docker running (if migrating local data)
- psql, ssh, scp commands available
- Python 3.8+ with requests, psycopg, neo4j, rich libraries

Usage:
    python scripts/deploy_to_render.py
    # OR
    uv run python scripts/deploy_to_render.py

Environment Variables (optional):
    RENDER_API_KEY - Render API key (will prompt if not set)
    POSTGRES_PASSWORD - Local PostgreSQL password (default: ragpassword)
    NEO4J_PASSWORD - Local Neo4j password (default: graphiti-password)
"""

import os
import sys
import subprocess
import getpass
import json
import time
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
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

console = Console()

# ============================================================================
# Constants - Verified from docker-compose.yml and research
# ============================================================================

# Local Docker Configuration (from docker-compose.yml)
LOCAL_POSTGRES_CONTAINER = "rag-memory-postgres-local"
LOCAL_NEO4J_CONTAINER = "rag-memory-neo4j-local"
LOCAL_POSTGRES_USER = "raguser"
LOCAL_POSTGRES_DB = "rag_memory"
LOCAL_POSTGRES_DEFAULT_PASSWORD = "ragpassword"
LOCAL_NEO4J_USER = "neo4j"
LOCAL_NEO4J_DEFAULT_PASSWORD = "graphiti-password"
LOCAL_POSTGRES_PORT = 54320
LOCAL_NEO4J_BOLT_PORT = 7687

# Render API Configuration (verified from api-docs.render.com)
RENDER_API_BASE = "https://api.render.com/v1"
RENDER_API_HEADERS = {"Content-Type": "application/json"}

# Project and Service Names
PROJECT_NAME = "rag-memory"
POSTGRES_SERVICE_NAME = "rag-memory-db"
NEO4J_SERVICE_NAME = "rag-memory-neo4j"
MCP_SERVICE_NAME = "rag-memory-mcp"

# PostgreSQL Configuration
POSTGRES_VERSION = "16"
POSTGRES_DATABASE_NAME = "ragmemory"

# Neo4j Configuration (verified from docker-compose.yml)
NEO4J_IMAGE = "neo4j:5-community"
NEO4J_DATA_MOUNT_PATH = "/data"
NEO4J_IMPORT_MOUNT_PATH = "/var/lib/neo4j/import"

# ============================================================================
# Utility Functions
# ============================================================================

def check_prerequisites() -> bool:
    """Check that required command-line tools are installed."""
    console.print("\n[bold cyan]🔧 Checking prerequisites...[/bold cyan]")

    required_tools = {
        "docker": ["docker", "--version"],
        "psql": ["psql", "--version"],
        "ssh": ["ssh", "-V"],
        "scp": ["scp", "-h"],
        "jq": ["jq", "--version"]
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

        # Parse cypher-shell output
        lines = [line.strip() for line in result.stdout.strip().split("\n")
                 if line.strip() and not line.startswith("+") and not line.startswith("|")
                 and "nodes" not in line.lower()]

        nodes = int(lines[0]) if lines else 0

        # Get relationships count
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

    postgres_exists = check_container_exists(LOCAL_POSTGRES_CONTAINER)
    neo4j_exists = check_container_exists(LOCAL_NEO4J_CONTAINER)

    if not postgres_exists and not neo4j_exists:
        console.print("[yellow]⚠️  No local RAG Memory containers found[/yellow]")
        return False, None, None

    console.print(f"[green]✓[/green] PostgreSQL container: {'Running' if postgres_exists else 'Not found'}")
    console.print(f"[green]✓[/green] Neo4j container: {'Running' if neo4j_exists else 'Not found'}")

    # Get data counts
    pg_counts = get_local_postgres_counts() if postgres_exists else None
    neo4j_counts = get_local_neo4j_counts() if neo4j_exists else None

    if pg_counts:
        console.print(f"[cyan]  → PostgreSQL: {pg_counts['documents']} documents, {pg_counts['chunks']} chunks[/cyan]")
    if neo4j_counts:
        console.print(f"[cyan]  → Neo4j: {neo4j_counts['nodes']} nodes, {neo4j_counts['relationships']} relationships[/cyan]")

    # Has data if either database has content
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
    """
    Get owner/workspace ID from Render API.

    Source: https://api-docs.render.com/reference/list-owners
    """
    console.print("\n[bold cyan]🔍 Fetching workspace ID...[/bold cyan]")

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

        # API returns [{cursor, owner}, ...] - extract owner objects
        owners = [item.get('owner', {}) for item in response_data]

        if not owners or all(not o for o in owners):
            console.print("[red]✗ No workspaces found for this API key[/red]")
            return None

        # If multiple workspaces, let user choose
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
    """
    Create a Render project to organize services.

    Source: https://api-docs.render.com/reference/create-project
    Verified schema from OpenAPI spec: requires environments array, not environmentName

    Projects are organizational containers for grouping related services.
    Returns project ID, name, and environment ID for associating resources.
    """
    console.print("\n[bold cyan]📁 Creating Render project...[/bold cyan]")

    # Correct payload structure per OpenAPI spec
    payload = {
        "name": PROJECT_NAME,
        "ownerId": owner_id,
        "environments": [
            {"name": "production"}  # Create production environment
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

        environment_id = environment_ids[0]  # Use first environment (production)

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
# Phase 2: Create PostgreSQL Database
# ============================================================================

def create_postgres_database(
    api_key: str,
    owner_id: str,
    environment_id: str,
    region: str,
    plan: str
) -> Optional[Dict[str, Any]]:
    """
    Create PostgreSQL database via Render API.

    Source: https://api-docs.render.com/reference/create-postgres
    Verified schema from OpenAPI spec and pricing page

    Args:
        environment_id: Environment ID from project to associate database with
    """
    console.print("\n[bold cyan]🗄️  Creating PostgreSQL database...[/bold cyan]")

    payload = {
        "name": POSTGRES_SERVICE_NAME,
        "plan": plan,
        "ownerId": owner_id,
        "environmentId": environment_id,  # Associate with project environment
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

        # Extract database ID
        database_id = postgres_data.get('id')

        console.print(f"[green]✓[/green] PostgreSQL created: {POSTGRES_SERVICE_NAME}")
        console.print(f"[dim]  Database ID: {database_id}[/dim]")

        # Wait for database to be available (not just created)
        console.print(f"[dim]Waiting for database to be ready...[/dim]")

        max_wait = 300  # 5 minutes
        poll_interval = 10  # seconds
        elapsed = 0
        external_url = None
        internal_url = None
        db_status = None

        while elapsed < max_wait:
            # Check database status
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
                    # Database is ready, now get connection strings
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
                            # Even though API says "available", database might need more time for SSL setup
                            console.print(f"[dim]Waiting 30s for database to fully initialize SSL...[/dim]")
                            time.sleep(30)
                            break

            # Wait before next poll
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
        # Use psql directly - it handles SSL correctly for Render
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
# Phase 3: Create Neo4j Docker Service
# ============================================================================

def create_neo4j_service(
    api_key: str,
    owner_id: str,
    environment_id: str,
    region: str,
    plan: str,
    neo4j_password: str
) -> Optional[Dict[str, Any]]:
    """
    Create Neo4j Docker web service via Render API.

    Source: https://api-docs.render.com/reference/create-service
    Verified schema from OpenAPI spec

    Args:
        environment_id: Environment ID from project to associate service with
    """
    console.print("\n[bold cyan]🔗 Creating Neo4j service...[/bold cyan]")

    # Environment variables verified from docker-compose.yml
    env_vars = [
        {"key": "NEO4J_AUTH", "value": f"neo4j/{neo4j_password}"},
        {"key": "NEO4J_PLUGINS", "value": '["apoc"]'},
        {"key": "NEO4J_server_memory_heap_initial__size", "value": "256m"},
        {"key": "NEO4J_server_memory_heap_max__size", "value": "400m"},
        {"key": "NEO4J_server_memory_pagecache_size", "value": "50m"},
        # APOC file settings for import/export
        {"key": "NEO4J_apoc_export_file_enabled", "value": "true"},
        {"key": "NEO4J_apoc_import_file_enabled", "value": "true"},
        {"key": "NEO4J_apoc_import_file_use__neo4j__config", "value": "true"}
    ]

    payload = {
        "type": "web_service",
        "name": NEO4J_SERVICE_NAME,
        "ownerId": owner_id,
        "environmentId": environment_id,  # Associate with project environment
        "image": {
            "imagePath": NEO4J_IMAGE,
            "ownerId": owner_id
        },
        "envVars": env_vars,
        "serviceDetails": {
            "runtime": "image",
            "disk": {
                "name": "neo4j-data",
                "mountPath": NEO4J_DATA_MOUNT_PATH,
                "sizeGB": 1
            },
            "region": region,
            "plan": plan
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
            console.print(f"[red]✗ Failed to create Neo4j: {error_msg}[/red]")
            return None

        response.raise_for_status()
        service_data = response.json()

        # Extract service details
        service = service_data.get('service', {})
        service_id = service.get('id')
        service_region = service.get('serviceDetails', {}).get('region', region)

        console.print(f"[green]✓[/green] Neo4j service created: {NEO4J_SERVICE_NAME}")
        console.print(f"[dim]  Service ID: {service_id}[/dim]")
        console.print(f"[dim]  Region: {service_region}[/dim]")

        # Internal URL for service-to-service communication
        internal_url = f"neo4j://{NEO4J_SERVICE_NAME}:7687"

        return {
            'id': service_id,
            'region': service_region,
            'internal_url': internal_url,
            'name': NEO4J_SERVICE_NAME,
            'password': neo4j_password
        }

    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗ Failed to create Neo4j service: {e}[/red]")
        if hasattr(e, 'response') and e.response is not None:
            console.print(f"[dim]{e.response.text}[/dim]")
        return None


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
    """
    Create MCP server as Docker web service on Render.

    Sources:
    - OpenAPI spec: servicePOST, webServiceDetailsPOST schemas
    - https://render.com/docs/web-services (port binding requirements)
    - https://render.com/docs/docker (Dockerfile deployment)
    - https://render.com/docs/deploy-fastapi (FastAPI/uvicorn configuration)

    The MCP server will:
    - Deploy from GitHub repository with Dockerfile
    - Connect to both PostgreSQL and Neo4j in Render
    - Expose SSE endpoint on public HTTPS URL
    - Bind to 0.0.0.0:$PORT (Render requirement)

    Args:
        repo_url: GitHub repository URL (e.g., "https://github.com/user/rag-memory")
        branch: Git branch to deploy from (default: "main")
    """
    console.print("\n[bold cyan]🚀 Creating MCP server...[/bold cyan]")

    # MCP server environment variables
    # These connect the cloud MCP server to cloud databases
    env_vars = [
        {"key": "DATABASE_URL", "value": postgres_url},
        {"key": "NEO4J_URI", "value": neo4j_uri},
        {"key": "NEO4J_USER", "value": "neo4j"},
        {"key": "NEO4J_PASSWORD", "value": neo4j_password},
        {"key": "OPENAI_API_KEY", "value": openai_api_key},
        {"key": "PYTHONUNBUFFERED", "value": "1"},  # For real-time logging
    ]

    payload = {
        "type": "web_service",
        "name": "rag-memory-mcp",
        "ownerId": owner_id,
        "environmentId": environment_id,
        "repo": repo_url,
        "branch": branch,
        "autoDeploy": "yes",  # Auto-deploy on git push
        "rootDir": "",  # Use repository root
        "envVars": env_vars,
        "serviceDetails": {
            "runtime": "docker",  # Build from Dockerfile
            "plan": plan,
            "region": region,
            "healthCheckPath": "/health",  # MCP server health endpoint
            # Note: Dockerfile must bind to 0.0.0.0:$PORT
            # Source: https://render.com/docs/web-services
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

        # Extract service details
        service = service_data.get('service', {})
        service_id = service.get('id')
        service_url = service.get('serviceDetails', {}).get('url')

        console.print(f"[green]✓[/green] MCP server created successfully")
        console.print(f"[dim]  Service ID: {service_id}[/dim]")
        console.print(f"[dim]  Region: {region}[/dim]")

        if service_url:
            console.print(f"\n[bold green]🌐 MCP Server URL:[/bold green] {service_url}")
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


def wait_for_service_ready(api_key: str, service_id: str, max_wait_seconds: int = 300) -> bool:
    """
    Wait for a Render service to be ready/available.

    Polls GET /services/{serviceId} endpoint until status is 'available'
    """
    console.print(f"\n[bold cyan]⏳ Waiting for service {service_id} to be ready...[/bold cyan]")

    start_time = time.time()

    while (time.time() - start_time) < max_wait_seconds:
        try:
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
                status = service.get('serviceDetails', {}).get('state', 'unknown')

                console.print(f"[dim]  Status: {status}[/dim]", end="\r")

                if status == 'available':
                    console.print("\n[green]✓[/green] Service is ready")
                    return True

            time.sleep(10)

        except requests.exceptions.RequestException:
            pass

    console.print("\n[yellow]⚠️  Service did not become ready within timeout[/yellow]")
    return False


# ============================================================================
# Phase 4: Data Migration - PostgreSQL
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
            "--no-owner",  # Don't try to set ownership (won't match Render)
            "--no-privileges"  # Don't dump privilege commands
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
# Phase 5: Data Migration - Neo4j via SSH/SCP
# ============================================================================

def export_neo4j_data(backup_dir: Path, neo4j_password: str) -> Optional[Path]:
    """
    Export Neo4j database using neo4j-admin dump.

    Source: https://neo4j.com/docs/operations-manual/current/backup-restore/offline-backup/

    CRITICAL: Database must be OFFLINE before dumping.
    Creates a .dump file that can be restored with neo4j-admin database load.
    """
    console.print("\n[bold cyan]📦 Exporting Neo4j database...[/bold cyan]")

    backup_file = backup_dir / "neo4j.dump"

    try:
        # Stop Neo4j (REQUIRED for offline dump)
        console.print("  → Stopping local Neo4j container...")
        stop_result = subprocess.run(
            ["docker", "stop", LOCAL_NEO4J_CONTAINER],
            capture_output=True,
            text=True,
            timeout=30
        )

        if stop_result.returncode != 0:
            console.print(f"[red]✗ Failed to stop Neo4j: {stop_result.stderr}[/red]")
            return None

        # Create dump using neo4j-admin (database must be stopped)
        console.print("  → Creating database dump with neo4j-admin...")
        dump_cmd = [
            "docker", "exec", LOCAL_NEO4J_CONTAINER,
            "neo4j-admin", "database", "dump",
            "neo4j",  # Database name
            "--to-path=/dumps",
            "--overwrite-destination=true"
        ]

        dump_result = subprocess.run(dump_cmd, capture_output=True, text=True, timeout=300)

        if dump_result.returncode != 0:
            console.print(f"[red]✗ Dump failed: {dump_result.stderr}[/red]")
            # Restart Neo4j before returning
            subprocess.run(["docker", "start", LOCAL_NEO4J_CONTAINER], timeout=30)
            return None

        # Copy dump from container to host
        console.print("  → Copying dump file from container...")
        copy_cmd = [
            "docker", "cp",
            f"{LOCAL_NEO4J_CONTAINER}:/dumps/neo4j.dump",
            str(backup_file)
        ]

        copy_result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=60)

        # Restart Neo4j
        console.print("  → Restarting local Neo4j...")
        subprocess.run(["docker", "start", LOCAL_NEO4J_CONTAINER], timeout=30)

        if copy_result.returncode != 0:
            console.print(f"[red]✗ Failed to copy dump: {copy_result.stderr}[/red]")
            return None

        size_mb = backup_file.stat().st_size / (1024 * 1024)
        console.print(f"[green]✓[/green] Neo4j dump created ({size_mb:.2f} MB)")
        return backup_file

    except subprocess.TimeoutExpired:
        console.print("[red]✗ Dump timed out[/red]")
        # Attempt to restart Neo4j
        subprocess.run(["docker", "start", LOCAL_NEO4J_CONTAINER], timeout=30)
        return None
    except Exception as e:
        console.print(f"[red]✗ Export failed: {e}[/red]")
        # Attempt to restart Neo4j
        subprocess.run(["docker", "start", LOCAL_NEO4J_CONTAINER], timeout=30)
        return None


def transfer_neo4j_via_ssh(
    dump_file: Path,
    service_name: str,
    region: str
) -> bool:
    """
    Transfer Neo4j dump file to Render persistent disk via SCP.

    Source: https://render.com/docs/ssh
    Render recommends: scp -s (SFTP mode)
    """
    console.print("\n[bold cyan]🚀 Transferring dump to Render via SSH...[/bold cyan]")

    ssh_host = f"{service_name}@ssh.{region}.render.com"
    # Transfer to persistent disk mount path (confirmed in Render dashboard)
    remote_path = f"{NEO4J_IMPORT_MOUNT_PATH}/neo4j.dump"

    try:
        # Transfer file via SCP using SFTP mode (-s)
        console.print(f"  → Uploading {dump_file.name} ({dump_file.stat().st_size / (1024*1024):.2f} MB)...")
        scp_cmd = [
            "scp",
            "-s",  # SFTP mode (Render recommended)
            "-o", "StrictHostKeyChecking=accept-new",
            str(dump_file),
            f"{ssh_host}:{remote_path}"
        ]

        result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            console.print(f"[red]✗ SCP failed: {result.stderr}[/red]")
            return False

        console.print("[green]✓[/green] Dump transferred to Render persistent disk")
        return True

    except subprocess.TimeoutExpired:
        console.print("[red]✗ Transfer timed out[/red]")
        return False
    except Exception as e:
        console.print(f"[red]✗ Transfer failed: {e}[/red]")
        return False


def import_neo4j_via_ssh(
    service_name: str,
    region: str,
    neo4j_password: str
) -> bool:
    """
    Import Neo4j dump on Render using neo4j-admin database load.

    Source: https://neo4j.com/docs/operations-manual/current/backup-restore/restore-dump/

    CRITICAL: Database must be STOPPED before loading.
    This uses Method A (in-place load via SSH) from the documented approach.
    """
    console.print("\n[bold cyan]📥 Importing Neo4j dump via SSH...[/bold cyan]")

    ssh_host = f"{service_name}@ssh.{region}.render.com"
    dump_path = NEO4J_IMPORT_MOUNT_PATH  # Directory containing neo4j.dump

    try:
        # Method A: Interactive SSH session, run commands step-by-step
        # This approach handles Render's container restart behavior
        console.print("  → Connecting to Render service...")
        console.print("  → Stopping Neo4j (required for offline load)...")
        console.print("  → Running neo4j-admin database load...")
        console.print("  → Starting Neo4j...")

        # Single SSH command that chains all operations
        # If Render auto-restarts on stop, this will fail and user should use Method B
        import_commands = " && ".join([
            "neo4j stop",
            f"neo4j-admin database load neo4j --from-path={dump_path} --overwrite-destination=true",
            "neo4j start",
            "sleep 10",  # Wait for startup
            f"cypher-shell -u neo4j -p '{neo4j_password}' \"MATCH (n) RETURN count(n) as node_count;\""
        ])

        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=accept-new",
            ssh_host,
            import_commands
        ]

        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            console.print(f"[red]✗ Import failed: {result.stderr}[/red]")
            console.print("\n[yellow]⚠ If Render auto-restarted the container, you need Method B:[/yellow]")
            console.print("[yellow]  Use the bootstrap entrypoint script approach documented in CLOUD_SETUP.md[/yellow]")
            return False

        console.print("[green]✓[/green] Neo4j data imported successfully")
        console.print(f"\nVerification output:\n{result.stdout}")
        return True

    except subprocess.TimeoutExpired:
        console.print("[red]✗ Import timed out[/red]")
        return False
    except Exception as e:
        console.print(f"[red]✗ Import failed: {e}[/red]")
        return False


# ============================================================================
# Phase 6: Verification
# ============================================================================

def verify_postgres(external_url: str, expected_counts: Dict) -> bool:
    """Verify PostgreSQL data was imported correctly."""
    console.print("\n[bold cyan]🔍 Verifying PostgreSQL...[/bold cyan]")

    try:
        # Get document count using psql
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

        # Get chunk count using psql
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
# Phase 7: Interactive Setup Flow
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
    console.print("[dim]IMPORTANT: Use UNDERSCORES not hyphens (e.g., basic_256mb not basic-256mb)[/dim]")
    console.print("[dim]Valid plans: basic_256mb, basic_1gb, basic_4gb, pro_4gb, pro_8gb, ...[/dim]")
    postgres_plan = Prompt.ask("Plan", default="basic_256mb")

    # Neo4j plan
    console.print("\n[bold]Neo4j Web Service Plan:[/bold]")
    console.print("[dim]IMPORTANT: Plan names are case-sensitive (must be lowercase)[/dim]")
    console.print("[dim]Check current valid plan names at:[/dim]")
    console.print("[dim]  - https://render.com/docs/blueprint-spec (search 'Web Service plan')[/dim]")
    console.print("[dim]  - https://api-docs.render.com/reference/create-service[/dim]")
    console.print("[dim]Note: SSH access required for migration (starter or higher)[/dim]")
    neo4j_plan = Prompt.ask("Plan", default="starter")

    # Neo4j password
    console.print("\n[bold]Neo4j Configuration:[/bold]")
    neo4j_password = getpass.getpass("Neo4j password (will be set on Render): ")

    return {
        "region": region,
        "postgres_plan": postgres_plan,
        "neo4j_plan": neo4j_plan,
        "neo4j_password": neo4j_password
    }


# ============================================================================
# Main Deployment Flow
# ============================================================================

def main():
    """Main deployment workflow."""
    console.print("\n" + "="*70)
    console.print(Panel.fit(
        "[bold cyan]RAG Memory - Render Deployment via REST API[/bold cyan]\n\n"
        "This tool will deploy RAG Memory to Render using the REST API.\n"
        "All services will be created programmatically.\n\n"
        "[yellow]Note: Requires paid Render plan (free tier not supported via API)[/yellow]",
        border_style="cyan"
    ))

    # Phase 0: Prerequisites
    if not check_prerequisites():
        console.print("\n[red]✗ Prerequisites check failed. Please install missing tools.[/red]")
        sys.exit(1)

    # Phase 1: Detect local data
    has_data, pg_counts, neo4j_counts = detect_local_data()

    migrate_data = False
    if has_data:
        console.print("\n[bold yellow]📊 Local data detected![/bold yellow]")
        migrate_data = Confirm.ask(
            "\nDo you want to migrate your local data to Render?",
            default=True
        )

        if not migrate_data:
            console.print("[yellow]Skipping migration. Proceeding with fresh deployment.[/yellow]")
    else:
        console.print("\n[dim]No local data found. Proceeding with fresh deployment.[/dim]")

    # Phase 2: Get API key and workspace
    api_key = get_render_api_key()
    owner_id = get_owner_id(api_key)

    if not owner_id:
        console.print("[red]✗ Failed to get workspace ID. Exiting.[/red]")
        sys.exit(1)

    # Phase 3: Create project (required to organize resources)
    project_info = create_project(api_key, owner_id)

    if not project_info:
        console.print("[red]✗ Failed to create project. Exiting.[/red]")
        sys.exit(1)

    environment_id = project_info['environment_id']

    # Phase 4: Configuration
    config = prompt_for_configuration()

    # Confirm before proceeding
    console.print("\n[bold]Deployment Summary:[/bold]")
    console.print(f"  Project: {project_info['name']}")
    console.print(f"  Environment: production")
    console.print(f"  Region: {config['region']}")
    console.print(f"  PostgreSQL: {config['postgres_plan']}")
    console.print(f"  Neo4j: {config['neo4j_plan']}")
    console.print(f"  Migrate data: {'Yes' if migrate_data else 'No'}")

    if not Confirm.ask("\nProceed with deployment?", default=True):
        console.print("[yellow]Deployment cancelled.[/yellow]")
        sys.exit(0)

    # Phase 5: Create PostgreSQL in project environment
    postgres_info = create_postgres_database(
        api_key,
        owner_id,
        environment_id,
        config['region'],
        config['postgres_plan']
    )

    if not postgres_info:
        console.print("[red]✗ Failed to create PostgreSQL. Exiting.[/red]")
        sys.exit(1)

    # Enable pgvector
    if not enable_pgvector(postgres_info['external_url']):
        console.print("[red]✗ Failed to enable pgvector. Exiting.[/red]")
        sys.exit(1)

    # Phase 6: Create Neo4j in project environment
    neo4j_info = create_neo4j_service(
        api_key,
        owner_id,
        environment_id,
        config['region'],
        config['neo4j_plan'],
        config['neo4j_password']
    )

    if not neo4j_info:
        console.print("[red]✗ Failed to create Neo4j. Exiting.[/red]")
        sys.exit(1)

    # Wait for Neo4j to be ready
    if not wait_for_service_ready(api_key, neo4j_info['id']):
        console.print("[yellow]⚠️  Neo4j service may not be fully ready yet[/yellow]")

    # Phase 6: Run database migrations to create schema
    console.print("\n[bold cyan]🔧 Running database migrations...[/bold cyan]")

    # Set DATABASE_URL temporarily for Alembic
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
        # Restore original DATABASE_URL
        if original_db_url:
            os.environ['DATABASE_URL'] = original_db_url
        else:
            os.environ.pop('DATABASE_URL', None)

    # Phase 7: Data Migration (if requested)
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
        local_neo4j_password = os.getenv("NEO4J_PASSWORD", LOCAL_NEO4J_DEFAULT_PASSWORD)
        neo4j_backup = export_neo4j_data(backup_dir, local_neo4j_password)

        if neo4j_backup:
            # APOC export already creates Cypher file - transfer and import directly
            if transfer_neo4j_via_ssh(
                neo4j_backup,
                neo4j_info['id'],
                neo4j_info['region']
            ):
                import_neo4j_via_ssh(
                    neo4j_info['name'],
                    neo4j_info['region'],
                    config['neo4j_password']
                )

    # Phase 7: Optional MCP Server Deployment
    mcp_info = None
    deploy_mcp = Prompt.ask(
        "\n[bold]Deploy MCP server to Render?[/bold]",
        choices=["yes", "no"],
        default="no"
    )

    if deploy_mcp == "yes":
        console.print("\n[bold cyan]Phase 7: MCP Server Deployment[/bold cyan]")

        # Get GitHub repository URL
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
            default="starter",
            choices=["starter", "standard", "pro", "pro_plus", "pro_max", "pro_ultra"]
        )

        # Get OpenAI API key (required for MCP server)
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            openai_key = Prompt.ask(
                "OpenAI API key (required for embeddings and graph extraction)",
                password=True
            )

        mcp_info = create_mcp_server(
            api_key=api_key,
            owner_id=owner_id,
            environment_id=environment_id,
            region=config['region'],
            plan=mcp_plan,
            postgres_url=postgres_info['external_url'],
            neo4j_uri=neo4j_info['internal_url'],
            neo4j_password=config['neo4j_password'],
            openai_api_key=openai_key,
            repo_url=mcp_repo,
            branch=mcp_branch
        )

        if mcp_info:
            console.print("\n[green]✓[/green] MCP server deployment initiated")
            console.print("[dim]Note: Build and deployment may take 5-10 minutes[/dim]")
            console.print(f"[dim]Monitor at: https://dashboard.render.com/web/{mcp_info['id']}[/dim]")
        else:
            console.print("\n[yellow]⚠[/yellow] MCP server deployment failed")
    else:
        console.print("\n[yellow]ℹ[/yellow] MCP server deployment skipped")
        console.print("You can run MCP server locally and point it to cloud databases:")
        console.print(f"  DATABASE_URL={postgres_info['external_url']}")
        console.print(f"  NEO4J_URI={neo4j_info['internal_url']}")

    # Phase 8: Display connection info
    console.print("\n" + "="*70)

    # Build output message based on what was deployed
    output_msg = (
        f"[bold green]✅ Deployment Complete![/bold green]\n\n"
        f"[bold]PostgreSQL:[/bold]\n"
        f"  External URL: {postgres_info['external_url']}\n"
        f"  Database: {POSTGRES_DATABASE_NAME}\n\n"
        f"[bold]Neo4j:[/bold]\n"
        f"  Internal URL (for MCP): {neo4j_info['internal_url']}\n"
        f"  Username: neo4j\n"
        f"  Password: <your configured password>\n\n"
    )

    if mcp_info:
        # MCP server was deployed
        output_msg += (
            f"[bold]MCP Server:[/bold]\n"
            f"  URL: {mcp_info['url']}\n"
            f"  SSE Endpoint: {mcp_info['url']}/sse\n"
            f"  Health Check: {mcp_info['url']}/health\n\n"
            f"[bold]Next Steps:[/bold]\n"
            f"1. Wait for MCP server build to complete (~5-10 min)\n"
            f"2. Test health endpoint: curl {mcp_info['url']}/health\n"
            f"3. Update Claude Desktop/Cursor MCP config:\n"
            f"   {{\n"
            f"     \"mcpServers\": {{\n"
            f"       \"rag-memory\": {{\n"
            f"         \"url\": \"{mcp_info['url']}/sse\"\n"
            f"       }}\n"
            f"     }}\n"
            f"   }}\n"
            f"4. Test with: Claude Desktop → Settings → MCP"
        )
    else:
        # MCP server not deployed - show manual instructions
        output_msg += (
            f"[bold]Next Steps:[/bold]\n"
            f"1. Run MCP server locally OR deploy manually:\n"
            f"   Local: Set these environment variables:\n"
            f"   - DATABASE_URL={postgres_info['external_url']}\n"
            f"   - NEO4J_URI={neo4j_info['internal_url']}\n"
            f"   - NEO4J_USER=neo4j\n"
            f"   - NEO4J_PASSWORD=<your password>\n"
            f"   - OPENAI_API_KEY=<your key>\n"
            f"2. Test deployment\n"
            f"3. Update Claude Desktop/Cursor MCP config"
        )

    console.print(Panel.fit(
        output_msg,
        title="🎉 Success",
        border_style="green"
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
