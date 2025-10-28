"""Path management for RAG Memory using platformdirs."""

import os
from pathlib import Path
import platformdirs


class Paths:
    """Centralized path management for RAG Memory."""

    @staticmethod
    def config_dir() -> Path:
        """Get config directory for the current OS.

        Returns:
            - macOS: ~/Library/Application Support/rag-memory/
            - Linux: ~/.config/rag-memory/
            - Windows: %LOCALAPPDATA%\\rag-memory\\
        """
        return Path(platformdirs.user_config_dir('rag-memory', appauthor=False))

    @staticmethod
    def log_dir() -> Path:
        """Get log directory for the current OS.

        Returns:
            - macOS: ~/Library/Logs/rag-memory/
            - Linux: ~/.local/state/rag-memory/
            - Windows: %LOCALAPPDATA%\\rag-memory\\Logs\\
        """
        return Path(platformdirs.user_log_dir('rag-memory', appauthor=False))

    @staticmethod
    def data_dir() -> Path:
        """Get data directory for the current OS.

        Returns:
            - macOS: ~/Library/Application Support/rag-memory/
            - Linux: ~/.local/share/rag-memory/
            - Windows: %LOCALAPPDATA%\\rag-memory\\
        """
        return Path(platformdirs.user_data_dir('rag-memory', appauthor=False))

    @staticmethod
    def docker_compose_file() -> Path:
        """Get path to docker-compose.yml."""
        return Paths.config_dir() / 'docker-compose.yml'

    @staticmethod
    def env_file() -> Path:
        """Get path to .env file."""
        return Paths.config_dir() / '.env'

    @staticmethod
    def config_yaml() -> Path:
        """Get path to config.yaml."""
        return Paths.config_dir() / 'config.yaml'

    @staticmethod
    def init_sql() -> Path:
        """Get path to init.sql."""
        return Paths.config_dir() / 'init.sql'

    @staticmethod
    def backup_dir() -> Path:
        """Get default backup directory."""
        return Paths.data_dir() / 'backups'

    @staticmethod
    def ensure_directories():
        """Ensure all required directories exist."""
        Paths.config_dir().mkdir(parents=True, exist_ok=True)
        Paths.log_dir().mkdir(parents=True, exist_ok=True)
        Paths.data_dir().mkdir(parents=True, exist_ok=True)
        Paths.backup_dir().mkdir(parents=True, exist_ok=True)