"""Configuration loader for RAG Memory with two-tier priority system.

This module provides cross-platform configuration loading that checks:
1. Environment variables (highest priority)
2. Global user config file ~/.rag-memory-env (fallback)

For local development, developers should set environment variables in their shell
or use the global config file. The CLI does not use .env files.
"""

import os
import stat
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def get_global_config_path() -> Path:
    """
    Get the path to the global user configuration file.

    Returns:
        Path to ~/.rag-memory-env (cross-platform)
    """
    return Path.home() / ".rag-memory-env"


def load_env_file(file_path: Optional[Path] = None) -> dict[str, str]:
    """
    Load and parse environment variables from a KEY=VALUE file.

    Args:
        file_path: Path to config file. Defaults to global config.

    Returns:
        Dictionary of environment variables from the file.
    """
    if file_path is None:
        file_path = get_global_config_path()

    env_vars = {}

    if not file_path.exists():
        return env_vars

    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Parse KEY=VALUE format
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    env_vars[key] = value
    except Exception as e:
        # Fail silently - config loading shouldn't break the app
        pass

    return env_vars


def save_env_var(key: str, value: str, file_path: Optional[Path] = None) -> bool:
    """
    Save or update an environment variable in the global config file.

    Args:
        key: Environment variable name
        value: Environment variable value
        file_path: Path to config file. Defaults to global config.

    Returns:
        True if saved successfully, False otherwise.
    """
    if file_path is None:
        file_path = get_global_config_path()

    try:
        # Load existing vars
        existing_vars = load_env_file(file_path)

        # Update or add the new variable
        existing_vars[key] = value

        # Write all variables back
        with open(file_path, 'w') as f:
            f.write("# RAG Memory - Configuration File\n")
            f.write("# This file is automatically managed by rag-memory\n")
            f.write("# You can edit or delete this file anytime\n\n")

            for k, v in existing_vars.items():
                f.write(f"{k}={v}\n")

        # Set restrictive permissions on Unix-like systems (chmod 0o600)
        # Windows handles file permissions differently through the OS
        try:
            if os.name != 'nt':  # Not Windows
                os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass  # Permissions not critical, continue anyway

        return True
    except Exception as e:
        return False


def get_env_var_from_file(key: str, file_path: Optional[Path] = None) -> Optional[str]:
    """
    Retrieve a specific environment variable from the global config file.

    Args:
        key: Environment variable name
        file_path: Path to config file. Defaults to global config.

    Returns:
        Value if found, None otherwise.
    """
    env_vars = load_env_file(file_path)
    return env_vars.get(key)


def load_environment_variables():
    """
    Load environment variables using two-tier priority system.

    Priority order (highest to lowest):
    1. Environment variables (already set in shell)
    2. Global ~/.rag-memory-env file (user-specific)

    Note: For local development, set environment variables in your shell or use
    the global config file. The CLI should not depend on .env files in arbitrary
    directories.
    """
    # 1. Environment variables - highest priority, already in os.environ

    # 2. Global user config file - only fallback
    global_config = get_global_config_path()
    if global_config.exists():
        env_vars = load_env_file(global_config)
        for key, value in env_vars.items():
            # Only set if not already in environment
            if key not in os.environ:
                os.environ[key] = value


def ensure_config_exists() -> bool:
    """
    Check if global config file exists and contains required variables.

    Returns:
        True if config exists and has DATABASE_URL and OPENAI_API_KEY
    """
    config_path = get_global_config_path()
    if not config_path.exists():
        return False

    env_vars = load_env_file(config_path)
    return 'DATABASE_URL' in env_vars and 'OPENAI_API_KEY' in env_vars


def create_default_config() -> bool:
    """
    Create a default global config file with placeholder values.

    Returns:
        True if created successfully
    """
    config_path = get_global_config_path()

    try:
        with open(config_path, 'w') as f:
            f.write("# RAG Memory - Configuration File\n")
            f.write("# This file is automatically managed by rag-memory\n")
            f.write("# You can edit or delete this file anytime\n\n")
            f.write("# PostgreSQL connection for RAG Memory (default Docker setup)\n")
            f.write("DATABASE_URL=postgresql://raguser:ragpass@localhost:54320/rag_poc\n\n")
            f.write("# OpenAI API key for embeddings\n")
            f.write("OPENAI_API_KEY=your-api-key-here\n")

        # Set restrictive permissions on Unix-like systems
        try:
            if os.name != 'nt':
                os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

        return True
    except Exception:
        return False


# Note: Environment variables are NOT loaded at module import.
# For CLI usage: load_environment_variables() is called by first_run.py (ensure_config_or_exit)
# For MCP usage: Environment variables are provided by the MCP client in JSON config
