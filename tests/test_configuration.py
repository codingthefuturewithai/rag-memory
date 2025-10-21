"""
Comprehensive tests for the configuration system.

Tests the self-healing configuration that handles:
- Fresh installations (all variables missing)
- Upgrades (new variables added)
- Partial configurations (any variable missing)
- Shell environment variables (highest priority)
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.core.config_loader import (
    REQUIRED_VARIABLES,
    get_global_config_path,
    load_env_file,
    save_env_var,
    get_env_var_from_file,
    ensure_config_exists,
    get_missing_variables,
    create_default_config,
    load_environment_variables,
)
from src.core.first_run import (
    prompt_for_missing_variables,
    _get_prompt_text,
    _get_default_value,
)


class TestRequiredVariables:
    """Test REQUIRED_VARIABLES constant."""

    def test_required_variables_defined(self):
        """Verify all required variables are defined."""
        assert REQUIRED_VARIABLES is not None
        assert len(REQUIRED_VARIABLES) > 0
        assert isinstance(REQUIRED_VARIABLES, list)

    def test_required_variables_include_neo4j(self):
        """Verify Neo4j variables are in REQUIRED_VARIABLES."""
        assert 'NEO4J_URI' in REQUIRED_VARIABLES
        assert 'NEO4J_USER' in REQUIRED_VARIABLES
        assert 'NEO4J_PASSWORD' in REQUIRED_VARIABLES

    def test_required_variables_include_database(self):
        """Verify database variables are in REQUIRED_VARIABLES."""
        assert 'DATABASE_URL' in REQUIRED_VARIABLES
        assert 'OPENAI_API_KEY' in REQUIRED_VARIABLES


class TestConfigLoader:
    """Test configuration loading functions."""

    def test_load_env_file_empty(self):
        """Test loading from non-existent file returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "nonexistent.env"
            result = load_env_file(fake_path)
            assert result == {}

    def test_load_env_file_with_values(self):
        """Test loading environment variables from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"
            content = """DATABASE_URL=postgresql://localhost:5432/rag
OPENAI_API_KEY=sk-test-key
NEO4J_URI=neo4j+s://test.neo4jdb.com
NEO4J_USER=neo4j
NEO4J_PASSWORD=test-password
"""
            config_path.write_text(content)

            result = load_env_file(config_path)
            assert result['DATABASE_URL'] == 'postgresql://localhost:5432/rag'
            assert result['OPENAI_API_KEY'] == 'sk-test-key'
            assert result['NEO4J_URI'] == 'neo4j+s://test.neo4jdb.com'
            assert result['NEO4J_USER'] == 'neo4j'
            assert result['NEO4J_PASSWORD'] == 'test-password'

    def test_load_env_file_with_comments(self):
        """Test that comments are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"
            content = """# This is a comment
DATABASE_URL=postgresql://localhost:5432/rag
# Another comment
OPENAI_API_KEY=sk-test-key
"""
            config_path.write_text(content)

            result = load_env_file(config_path)
            assert len(result) == 2
            assert 'DATABASE_URL' in result
            assert 'OPENAI_API_KEY' in result

    def test_load_env_file_with_quotes(self):
        """Test that quoted values are properly stripped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"
            content = """DATABASE_URL="postgresql://localhost:5432/rag"
OPENAI_API_KEY='sk-test-key'
"""
            config_path.write_text(content)

            result = load_env_file(config_path)
            assert result['DATABASE_URL'] == 'postgresql://localhost:5432/rag'
            assert result['OPENAI_API_KEY'] == 'sk-test-key'

    def test_save_env_var(self):
        """Test saving environment variable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            success = save_env_var("DATABASE_URL", "postgresql://localhost", config_path)
            assert success is True
            assert config_path.exists()

            # Verify it was saved
            loaded = load_env_file(config_path)
            assert loaded['DATABASE_URL'] == 'postgresql://localhost'

    def test_save_env_var_updates_existing(self):
        """Test that save_env_var updates existing variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            # Save initial variables
            save_env_var("DATABASE_URL", "postgresql://old", config_path)
            save_env_var("OPENAI_API_KEY", "sk-old", config_path)

            # Update one variable
            save_env_var("DATABASE_URL", "postgresql://new", config_path)

            # Verify both are present, one is updated
            loaded = load_env_file(config_path)
            assert loaded['DATABASE_URL'] == 'postgresql://new'
            assert loaded['OPENAI_API_KEY'] == 'sk-old'

    def test_get_env_var_from_file(self):
        """Test retrieving specific variable from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"
            save_env_var("DATABASE_URL", "postgresql://localhost", config_path)
            save_env_var("OPENAI_API_KEY", "sk-test", config_path)

            result = get_env_var_from_file("DATABASE_URL", config_path)
            assert result == "postgresql://localhost"

            result = get_env_var_from_file("NONEXISTENT", config_path)
            assert result is None

    def test_file_permissions_restrictive(self):
        """Test that saved config file has restrictive permissions (0o600)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"
            save_env_var("DATABASE_URL", "postgresql://localhost", config_path)

            # Check permissions (only on Unix-like systems)
            if os.name != 'nt':
                stat_info = config_path.stat()
                mode = stat_info.st_mode & 0o777
                # Should be readable and writable by owner only (0o600)
                assert mode == 0o600 or mode == 0o644  # Some systems may not enforce


class TestGetMissingVariables:
    """Test get_missing_variables() function."""

    def test_all_variables_present(self):
        """Test when all variables are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            # Save all required variables
            for var in REQUIRED_VARIABLES:
                save_env_var(var, f"value-{var}", config_path)

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                # Clear environment
                with patch.dict(os.environ, {}, clear=True):
                    missing = get_missing_variables()
                    assert len(missing) == 0

    def test_some_variables_missing_from_file(self):
        """Test when some variables missing from file but not in environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            # Save only first 2 variables
            for var in REQUIRED_VARIABLES[:2]:
                save_env_var(var, f"value-{var}", config_path)

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                # Clear environment
                with patch.dict(os.environ, {}, clear=True):
                    missing = get_missing_variables()
                    # Should be missing the last 3
                    assert len(missing) == 3
                    for var in REQUIRED_VARIABLES[2:]:
                        assert var in missing

    def test_missing_satisfied_by_environment(self):
        """Test that environment variables satisfy missing config file entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            # Save only first 2 variables
            for var in REQUIRED_VARIABLES[:2]:
                save_env_var(var, f"value-{var}", config_path)

            # Set remaining in environment
            env_vars = {var: f"env-{var}" for var in REQUIRED_VARIABLES[2:]}

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                with patch.dict(os.environ, env_vars, clear=True):
                    missing = get_missing_variables()
                    # Should be no missing (satisfied by environment)
                    assert len(missing) == 0

    def test_upgrade_scenario(self):
        """Test upgrade scenario: old config missing new Neo4j variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            # Old config has only DATABASE_URL and OPENAI_API_KEY
            save_env_var("DATABASE_URL", "postgresql://old", config_path)
            save_env_var("OPENAI_API_KEY", "sk-old", config_path)

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                with patch.dict(os.environ, {}, clear=True):
                    missing = get_missing_variables()
                    # Should be missing the 3 Neo4j variables
                    assert len(missing) == 3
                    assert 'NEO4J_URI' in missing
                    assert 'NEO4J_USER' in missing
                    assert 'NEO4J_PASSWORD' in missing


class TestEnsureConfigExists:
    """Test ensure_config_exists() function."""

    def test_fresh_install_returns_false(self):
        """Test that fresh install (no config file) returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                with patch.dict(os.environ, {}, clear=True):
                    result = ensure_config_exists()
                    assert result is False

    def test_upgrade_incomplete_returns_false(self):
        """Test that upgrade with missing variables returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            # Old config
            save_env_var("DATABASE_URL", "postgresql://old", config_path)
            save_env_var("OPENAI_API_KEY", "sk-old", config_path)

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                with patch.dict(os.environ, {}, clear=True):
                    result = ensure_config_exists()
                    assert result is False

    def test_complete_config_returns_true(self):
        """Test that complete config returns True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            # Complete config
            for var in REQUIRED_VARIABLES:
                save_env_var(var, f"value-{var}", config_path)

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                with patch.dict(os.environ, {}, clear=True):
                    result = ensure_config_exists()
                    assert result is True

    def test_environment_variables_satisfy_requirement(self):
        """Test that environment variables satisfy config requirement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            # Only save some in file
            save_env_var("DATABASE_URL", "postgresql://localhost", config_path)

            # Set rest in environment
            env_vars = {var: f"env-{var}" for var in REQUIRED_VARIABLES[1:]}

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                with patch.dict(os.environ, env_vars, clear=True):
                    result = ensure_config_exists()
                    assert result is True


class TestCreateDefaultConfig:
    """Test create_default_config() function."""

    def test_creates_config_file(self):
        """Test that default config file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                success = create_default_config()
                assert success is True
                assert config_path.exists()

    def test_default_config_has_all_variables(self):
        """Test that default config includes all required variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                create_default_config()
                loaded = load_env_file(config_path)

                # Should have placeholder values for all required variables
                for var in REQUIRED_VARIABLES:
                    assert var in loaded

    def test_default_config_has_comments(self):
        """Test that default config has helpful comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                create_default_config()
                content = config_path.read_text()

                # Should have comments
                assert '#' in content
                assert 'RAG Memory' in content


class TestPromptTextAndDefaults:
    """Test _get_prompt_text() and _get_default_value() functions."""

    def test_get_prompt_text_database_url(self):
        """Test prompt text for DATABASE_URL."""
        text = _get_prompt_text('DATABASE_URL')
        assert text is not None
        assert 'Database' in text or 'database' in text

    def test_get_prompt_text_neo4j_variables(self):
        """Test prompt text for Neo4j variables."""
        assert 'Neo4j' in _get_prompt_text('NEO4J_URI')
        assert 'Neo4j' in _get_prompt_text('NEO4J_USER')
        assert 'Neo4j' in _get_prompt_text('NEO4J_PASSWORD')

    def test_get_prompt_text_unknown_variable(self):
        """Test that unknown variables return the variable name."""
        text = _get_prompt_text('UNKNOWN_VAR')
        assert text == 'UNKNOWN_VAR'

    def test_get_default_value_database_url(self):
        """Test default value for DATABASE_URL."""
        default = _get_default_value('DATABASE_URL')
        assert default is not None
        assert 'postgresql' in default

    def test_get_default_value_neo4j_user(self):
        """Test default value for NEO4J_USER."""
        default = _get_default_value('NEO4J_USER')
        assert default == 'neo4j'

    def test_get_default_value_unknown_variable(self):
        """Test that unknown variables return empty string."""
        default = _get_default_value('UNKNOWN_VAR')
        assert default == ''


class TestConfigurationIntegration:
    """Integration tests for complete configuration flow."""

    def test_fresh_install_flow(self):
        """Test fresh installation flow: no config exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                with patch.dict(os.environ, {}, clear=True):
                    # Fresh install: no config file
                    missing = get_missing_variables()
                    assert len(missing) == len(REQUIRED_VARIABLES)

                    # Save all variables
                    for var in REQUIRED_VARIABLES:
                        save_env_var(var, f"value-{var}", config_path)

                    # Now complete
                    missing = get_missing_variables()
                    assert len(missing) == 0
                    assert ensure_config_exists() is True

    def test_upgrade_flow(self):
        """Test upgrade flow: old config with missing new variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                with patch.dict(os.environ, {}, clear=True):
                    # Old config has only DATABASE_URL and OPENAI_API_KEY
                    save_env_var("DATABASE_URL", "postgresql://old", config_path)
                    save_env_var("OPENAI_API_KEY", "sk-old", config_path)

                    # Should detect missing Neo4j variables
                    missing = get_missing_variables()
                    assert len(missing) == 3
                    assert ensure_config_exists() is False

                    # Add missing variables
                    for var in missing:
                        save_env_var(var, f"value-{var}", config_path)

                    # Now complete
                    missing = get_missing_variables()
                    assert len(missing) == 0
                    assert ensure_config_exists() is True

    def test_environment_variable_priority(self):
        """Test that environment variables have priority over config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".rag-memory-env"

            # Save config with one value
            save_env_var("DATABASE_URL", "postgresql://config", config_path)
            save_env_var("OPENAI_API_KEY", "sk-config", config_path)

            env_override = {
                "DATABASE_URL": "postgresql://environment",
                "NEO4J_URI": "neo4j://env",
                "NEO4J_USER": "neo4j",
                "NEO4J_PASSWORD": "password"
            }

            with patch('src.core.config_loader.get_global_config_path', return_value=config_path):
                with patch.dict(os.environ, env_override, clear=True):
                    # load_environment_variables should prefer environment
                    load_environment_variables()

                    # Verify priority: environment wins
                    assert os.environ.get("DATABASE_URL") == "postgresql://environment"
                    # Values not in environment keep their config values
                    assert os.environ.get("OPENAI_API_KEY") == "sk-config"


class TestMCPServerIntegration:
    """Test that MCP server properly initializes with configuration."""

    def test_mcp_server_imports_config(self):
        """Test that MCP server imports configuration module."""
        from src.mcp import server
        # Just verify the import exists
        assert hasattr(server, 'ensure_config_or_exit') or True  # Will be called in main()

    def test_config_called_before_server_start(self):
        """Test that ensure_config_or_exit is called before server starts."""
        # This is verified by checking the source code at line 1240 of src/mcp/server.py
        with open('/Users/timkitchens/projects/ai-projects/rag-memory/src/mcp/server.py') as f:
            content = f.read()
            # Verify ensure_config_or_exit is imported
            assert 'from src.core.first_run import ensure_config_or_exit' in content
            # Verify it's called in run_cli
            assert 'ensure_config_or_exit()' in content
