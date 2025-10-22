"""Configuration loader for RAG Memory with OS-standard locations.

This module provides cross-platform configuration loading that checks:
1. Environment variables (highest priority)
2. OS-standard config file (user-specific, platform-aware)

Config locations:
- macOS: ~/Library/Application Support/rag-memory/config.yaml
- Linux: ~/.config/rag-memory/config.yaml
- Windows: %LOCALAPPDATA%\rag-memory\config.yaml

The configuration file is YAML format containing:
- server settings (API keys, database URLs)
- mount configuration (read-only directories for file ingestion)
"""

import os
import stat
from pathlib import Path
from typing import Optional, Any

import platformdirs
import yaml

# List of required configuration keys in server section
REQUIRED_SERVER_KEYS = [
    'openai_api_key',
    'database_url',
    'neo4j_uri',
    'neo4j_user',
    'neo4j_password',
]


def get_config_dir() -> Path:
    """
    Get the configuration directory for RAG Memory.

    Detection logic (in order of priority):
    1. If RAG_CONFIG_PATH env var is set: use that directory
    2. If repo-local config exists (./config/): use that (dev/test scenarios)
    3. If running in Docker container: use /app/.config/rag-memory
    4. Otherwise (system CLI): use platformdirs for OS-standard locations:
       - macOS: ~/Library/Application Support/rag-memory
       - Linux: ~/.config/rag-memory (respects $XDG_CONFIG_HOME)
       - Windows: %LOCALAPPDATA%\rag-memory

    Returns:
        Path to configuration directory
    """
    # 1. Check environment variable override
    if env_override := os.getenv('RAG_CONFIG_PATH'):
        config_dir = Path(env_override)
    # 2. Check for repo-local config (when running from within repo)
    elif (repo_local := Path('./config')).exists():
        config_dir = repo_local
    # 3. Check if running in Docker container (MCP server scenario)
    elif Path('/.dockerenv').exists():
        # Inside Docker: config mounted at /app/.config/rag-memory
        config_dir = Path('/app/.config/rag-memory')
    else:
        # 4. System-level CLI: use OS-standard locations
        config_dir = Path(platformdirs.user_config_dir('rag-memory', appauthor=False))

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """
    Get the path to the RAG Memory configuration file.

    Returns:
        Path to config.yaml in OS-appropriate location
    """
    return get_config_dir() / 'config.yaml'


def load_config(file_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        file_path: Path to config file. Defaults to OS-standard location.

    Returns:
        Dictionary with 'server' and 'mounts' sections, or empty dict if not found.
    """
    if file_path is None:
        file_path = get_config_path()

    if not file_path.exists():
        return {}

    try:
        with open(file_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        return config
    except Exception as e:
        # Log error but don't crash - config loading shouldn't break the app
        return {}


def save_config(config: dict[str, Any], file_path: Optional[Path] = None) -> bool:
    """
    Save configuration to YAML file.

    Args:
        config: Configuration dictionary with 'server' and 'mounts' sections
        file_path: Path to config file. Defaults to OS-standard location.

    Returns:
        True if saved successfully, False otherwise.
    """
    if file_path is None:
        file_path = get_config_path()

    try:
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write YAML config
        with open(file_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        # Set restrictive permissions on Unix-like systems (chmod 0o600)
        try:
            if os.name != 'nt':
                os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

        return True
    except Exception:
        return False


def load_environment_variables():
    """
    Load environment variables using two-tier priority system.

    Priority order (highest to lowest):
    1. Environment variables (already set in shell)
    2. Config file in OS-standard location

    Reads from 'server' section of config.yaml and sets environment variables.
    """
    # Load config from OS-standard location
    config = load_config()
    server_config = config.get('server', {})

    # Map config keys to environment variable names
    key_mapping = {
        'openai_api_key': 'OPENAI_API_KEY',
        'database_url': 'DATABASE_URL',
        'neo4j_uri': 'NEO4J_URI',
        'neo4j_user': 'NEO4J_USER',
        'neo4j_password': 'NEO4J_PASSWORD',
    }

    for config_key, env_var in key_mapping.items():
        if config_key in server_config and env_var not in os.environ:
            os.environ[env_var] = str(server_config[config_key])


def get_mounts() -> list[dict[str, Any]]:
    """
    Get the list of read-only directory mounts from config.

    Returns:
        List of mount configurations, each with 'path' and 'read_only' keys.
        Empty list if no mounts configured.
    """
    config = load_config()
    mounts = config.get('mounts', [])
    return mounts if isinstance(mounts, list) else []


def ensure_config_exists() -> bool:
    """
    Check if config file exists and contains all required server settings.

    Returns:
        True if config exists and has all required keys
    """
    config_path = get_config_path()
    if not config_path.exists():
        return False

    config = load_config(config_path)
    server_config = config.get('server', {})

    # Check if all required keys are present (either in file or in environment)
    for key in REQUIRED_SERVER_KEYS:
        env_var = _config_key_to_env_var(key)
        if key not in server_config and env_var not in os.environ:
            return False

    return True


def get_missing_config_keys() -> list[str]:
    """
    Get list of required configuration keys that are missing.

    Returns:
        List of missing key names. Empty list if all keys present.
    """
    config_path = get_config_path()
    config = load_config(config_path) if config_path.exists() else {}
    server_config = config.get('server', {})

    missing = []
    for key in REQUIRED_SERVER_KEYS:
        env_var = _config_key_to_env_var(key)
        if key not in server_config and env_var not in os.environ:
            missing.append(key)

    return missing


def _config_key_to_env_var(config_key: str) -> str:
    """Convert config key to environment variable name."""
    mapping = {
        'openai_api_key': 'OPENAI_API_KEY',
        'database_url': 'DATABASE_URL',
        'neo4j_uri': 'NEO4J_URI',
        'neo4j_user': 'NEO4J_USER',
        'neo4j_password': 'NEO4J_PASSWORD',
    }
    return mapping.get(config_key, config_key.upper())


def is_path_in_mounts(file_path: str) -> tuple[bool, str]:
    """
    Check if a file path is within one of the configured mount directories.

    This is used by the MCP server running in Docker to validate that tools
    like ingest_file and ingest_directory only access paths that were
    explicitly mounted and made available at setup time.

    Args:
        file_path: Absolute or relative path to check

    Returns:
        Tuple of (is_valid, message) where:
        - is_valid (bool): True if path is within a configured mount
        - message (str): Explanation of why path is valid/invalid
    """
    try:
        # Resolve path to absolute, canonical form
        requested_path = Path(file_path).expanduser().resolve()

        # Get configured mounts
        mounts = get_mounts()

        # If no mounts configured, reject all file access
        if not mounts:
            return False, (
                "No directories are currently mounted for file access. "
                "Run 'python scripts/update-config.py' to configure mounts."
            )

        # Check if path is within any mounted directory
        for mount in mounts:
            mount_path = mount.get('path')
            if not mount_path:
                continue

            try:
                mount_path_resolved = Path(mount_path).expanduser().resolve()

                # Check if requested path is under the mount
                # This will succeed if requested_path == mount_path or is a descendant
                requested_path.relative_to(mount_path_resolved)
                return True, f"Path is within configured mount: {mount_path}"

            except ValueError:
                # relative_to() raises ValueError if path is not relative
                # This means requested_path is not under this mount
                continue

        # Path is not under any mount
        mounted_dirs = [m.get('path') for m in mounts if m.get('path')]
        return False, (
            f"Path is not within configured mounts. "
            f"Mounted directories: {', '.join(mounted_dirs)}"
        )

    except Exception as e:
        return False, f"Error validating path: {str(e)}"
