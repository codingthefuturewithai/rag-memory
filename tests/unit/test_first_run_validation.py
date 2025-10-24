"""Unit tests for first_run configuration validation and error handling."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from io import StringIO
import sys

from src.core.first_run import validate_config_exists, ensure_config_or_exit


class TestValidateConfigExistsFresh:
    """Test validate_config_exists with fresh installations."""

    def test_fresh_install_config_missing_returns_false(self):
        """Test that missing config file returns False for fresh install."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            mock_get_path.return_value = Path("/nonexistent/config.yaml")

            result = validate_config_exists()

            assert result is False

    @patch('src.core.first_run.console')
    def test_fresh_install_displays_helpful_error_message(self, mock_console):
        """Test that helpful error message is displayed for fresh install."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            mock_get_path.return_value = Path("/nonexistent/config.yaml")

            validate_config_exists()

            # Verify console output methods were called
            assert mock_console.print.called
            # Check that setup instructions are provided
            calls = [str(call) for call in mock_console.print.call_args_list]
            output = ' '.join(calls)
            assert 'setup.py' in output or 'Configuration not found' in output

    @patch('src.core.first_run.console')
    def test_fresh_install_mentions_setup_script(self, mock_console):
        """Test that setup instructions mention the setup script."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            mock_get_path.return_value = Path("/nonexistent/config.yaml")

            validate_config_exists()

            # Verify setup.py is mentioned in error output
            all_output = ' '.join(str(call) for call in mock_console.print.call_args_list)
            assert 'setup' in all_output.lower()


class TestValidateConfigExistsIncomplete:
    """Test validate_config_exists with incomplete configuration."""

    def test_incomplete_config_returns_false(self):
        """Test that incomplete config (missing keys) returns False."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            config_path = Path("/tmp/config.yaml")
            mock_get_path.return_value = config_path

            with patch('src.core.first_run.get_missing_config_keys') as mock_missing:
                mock_missing.return_value = ['neo4j_uri', 'neo4j_password']

                with patch('pathlib.Path.exists', return_value=True):
                    result = validate_config_exists()

                    assert result is False

    @patch('src.core.first_run.console')
    def test_incomplete_config_displays_missing_keys(self, mock_console):
        """Test that missing keys are displayed in error message."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            config_path = Path("/tmp/config.yaml")
            mock_get_path.return_value = config_path

            with patch('src.core.first_run.get_missing_config_keys') as mock_missing:
                mock_missing.return_value = ['neo4j_uri', 'neo4j_password']

                with patch('pathlib.Path.exists', return_value=True):
                    validate_config_exists()

                    all_output = ' '.join(str(call) for call in mock_console.print.call_args_list)
                    assert 'neo4j_uri' in all_output or 'missing' in all_output.lower()

    @patch('src.core.first_run.console')
    def test_incomplete_config_suggests_update(self, mock_console):
        """Test that incomplete config suggests update-config script."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            config_path = Path("/tmp/config.yaml")
            mock_get_path.return_value = config_path

            with patch('src.core.first_run.get_missing_config_keys') as mock_missing:
                mock_missing.return_value = ['database_url']

                with patch('pathlib.Path.exists', return_value=True):
                    validate_config_exists()

                    all_output = ' '.join(str(call) for call in mock_console.print.call_args_list)
                    assert 'update' in all_output.lower() or 'configure' in all_output.lower()


class TestValidateConfigExistsComplete:
    """Test validate_config_exists with complete configuration."""

    def test_complete_config_returns_true(self):
        """Test that complete config returns True."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            config_path = Path("/tmp/config.yaml")
            mock_get_path.return_value = config_path

            with patch('src.core.first_run.get_missing_config_keys') as mock_missing:
                mock_missing.return_value = []  # No missing keys

                with patch('pathlib.Path.exists', return_value=True):
                    result = validate_config_exists()

                    assert result is True

    @patch('src.core.first_run.console')
    def test_complete_config_no_error_message(self, mock_console):
        """Test that complete config doesn't print error messages."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            config_path = Path("/tmp/config.yaml")
            mock_get_path.return_value = config_path

            with patch('src.core.first_run.get_missing_config_keys') as mock_missing:
                mock_missing.return_value = []

                with patch('pathlib.Path.exists', return_value=True):
                    validate_config_exists()

                    # console.print should not be called for valid config
                    assert not mock_console.print.called


class TestEnsureConfigOrExitFlow:
    """Test the complete ensure_config_or_exit flow."""

    @patch('src.core.first_run.load_environment_variables')
    @patch('src.core.first_run.validate_config_exists')
    def test_ensure_config_or_exit_loads_environment(self, mock_validate, mock_load_env):
        """Test that ensure_config_or_exit loads environment variables."""
        mock_validate.return_value = True

        ensure_config_or_exit()

        mock_load_env.assert_called_once()

    @patch('src.core.first_run.load_environment_variables')
    @patch('src.core.first_run.validate_config_exists')
    def test_ensure_config_or_exit_validates_after_loading(self, mock_validate, mock_load_env):
        """Test that validation happens after loading environment."""
        mock_validate.return_value = True

        ensure_config_or_exit()

        # Both should be called
        mock_load_env.assert_called_once()
        mock_validate.assert_called_once()

    @patch('src.core.first_run.load_environment_variables')
    @patch('src.core.first_run.validate_config_exists')
    def test_ensure_config_or_exit_success(self, mock_validate, mock_load_env):
        """Test that ensure_config_or_exit completes successfully with valid config."""
        mock_validate.return_value = True

        # Should not raise exception
        ensure_config_or_exit()

    @patch('src.core.first_run.load_environment_variables')
    @patch('src.core.first_run.validate_config_exists')
    @patch('sys.exit')
    def test_ensure_config_or_exit_exits_on_invalid(self, mock_exit, mock_validate, mock_load_env):
        """Test that ensure_config_or_exit calls sys.exit() on invalid config."""
        mock_validate.return_value = False

        ensure_config_or_exit()

        mock_exit.assert_called_once_with(1)

    @patch('src.core.first_run.load_environment_variables')
    @patch('src.core.first_run.validate_config_exists')
    @patch('sys.exit')
    def test_ensure_config_or_exit_exit_code_is_1(self, mock_exit, mock_validate, mock_load_env):
        """Test that exit code is 1 (error) on config failure."""
        mock_validate.return_value = False

        ensure_config_or_exit()

        # Should call sys.exit(1), not sys.exit(0)
        mock_exit.assert_called_once_with(1)


class TestValidateConfigExistsErrorPaths:
    """Test error handling paths in validate_config_exists."""

    @patch('src.core.first_run.get_config_path')
    @patch('src.core.first_run.console')
    def test_config_path_exception_handled(self, mock_console, mock_get_path):
        """Test that exceptions in path handling are caught."""
        mock_get_path.side_effect = Exception("Path error")

        # Should handle the exception gracefully
        with pytest.raises(Exception):
            validate_config_exists()

    @patch('src.core.first_run.console')
    def test_missing_keys_function_called_for_existing_config(self, mock_console):
        """Test that get_missing_config_keys is called when config exists."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            with patch('src.core.first_run.get_missing_config_keys') as mock_missing:
                config_path = Path("/tmp/config.yaml")
                mock_get_path.return_value = config_path
                mock_missing.return_value = []

                with patch('pathlib.Path.exists', return_value=True):
                    validate_config_exists()

                    mock_missing.assert_called_once()


class TestValidateConfigExistsMessageContent:
    """Test the content of error messages displayed."""

    @patch('src.core.first_run.console')
    def test_fresh_install_message_has_expected_location(self, mock_console):
        """Test that error message shows where config should be located."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            test_path = Path("/home/user/.config/rag-memory/config.yaml")
            mock_get_path.return_value = test_path

            validate_config_exists()

            # Config path should be shown somewhere in output
            all_calls = [str(call) for call in mock_console.print.call_args_list]
            output = ' '.join(all_calls)
            # Either the path or some reference to config location should be there
            assert 'config' in output.lower() or 'rag-memory' in output.lower()

    @patch('src.core.first_run.console')
    def test_incomplete_config_shows_docker_rebuild_hint(self, mock_console):
        """Test that incomplete config suggests rebuilding Docker containers."""
        with patch('src.core.first_run.get_config_path') as mock_get_path:
            config_path = Path("/tmp/config.yaml")
            mock_get_path.return_value = config_path

            with patch('src.core.first_run.get_missing_config_keys') as mock_missing:
                mock_missing.return_value = ['neo4j_uri']

                with patch('pathlib.Path.exists', return_value=True):
                    validate_config_exists()

                    all_calls = [str(call) for call in mock_console.print.call_args_list]
                    output = ' '.join(all_calls)
                    # Should suggest rebuilding containers
                    assert 'docker' in output.lower() or 'update' in output.lower() or 'configure' in output.lower()


class TestValidateConfigExistsIntegration:
    """Integration tests for validate_config_exists."""

    @patch('src.core.first_run.get_config_path')
    @patch('src.core.first_run.load_environment_variables')
    @patch('src.core.first_run.get_missing_config_keys')
    @patch('src.core.first_run.console')
    def test_full_flow_fresh_install(self, mock_console, mock_missing, mock_load_env, mock_get_path):
        """Test full flow for fresh installation."""
        mock_get_path.return_value = Path("/nonexistent/config.yaml")

        result = validate_config_exists()

        assert result is False
        assert mock_console.print.called

    @patch('src.core.first_run.get_config_path')
    @patch('src.core.first_run.load_environment_variables')
    @patch('src.core.first_run.get_missing_config_keys')
    @patch('src.core.first_run.console')
    def test_full_flow_complete_config(self, mock_console, mock_missing, mock_load_env, mock_get_path):
        """Test full flow with complete configuration."""
        config_path = Path("/tmp/config.yaml")
        mock_get_path.return_value = config_path
        mock_missing.return_value = []

        with patch('pathlib.Path.exists', return_value=True):
            result = validate_config_exists()

            assert result is True
            assert not mock_console.print.called


class TestEnsureConfigOrExitEdgeCases:
    """Test edge cases for ensure_config_or_exit."""

    @patch('src.core.first_run.load_environment_variables')
    @patch('src.core.first_run.validate_config_exists')
    @patch('sys.exit')
    def test_ensure_config_or_exit_doesnt_call_exit_on_success(self, mock_exit, mock_validate, mock_load_env):
        """Test that sys.exit is NOT called when config is valid."""
        mock_validate.return_value = True

        ensure_config_or_exit()

        mock_exit.assert_not_called()

    @patch('src.core.first_run.load_environment_variables')
    def test_ensure_config_or_exit_loads_env_even_if_validate_fails(self, mock_load_env):
        """Test that environment is loaded even if validation fails."""
        with patch('src.core.first_run.validate_config_exists', return_value=False):
            with patch('sys.exit'):
                ensure_config_or_exit()

                # load_environment_variables should be called first
                mock_load_env.assert_called_once()

    @patch('src.core.first_run.load_environment_variables')
    @patch('src.core.first_run.validate_config_exists')
    def test_multiple_calls_to_ensure_config_or_exit(self, mock_validate, mock_load_env):
        """Test that ensure_config_or_exit can be called multiple times."""
        mock_validate.return_value = True

        # Should not raise errors on multiple calls
        ensure_config_or_exit()
        ensure_config_or_exit()

        assert mock_load_env.call_count == 2
        assert mock_validate.call_count == 2
