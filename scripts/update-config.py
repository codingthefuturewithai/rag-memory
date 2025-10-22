#!/usr/bin/env python3
"""
Update RAG Memory Configuration

Allows users to modify existing configuration without re-running full setup.
After updating, user must restart Docker containers for changes to take effect.
"""

import sys
from pathlib import Path

import platformdirs
import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm

console = Console()


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
    console.print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    console.print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
    console.print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message"""
    console.print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message"""
    console.print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message"""
    console.print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    console.print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def get_config_path() -> Path:
    """Get path to configuration file"""
    config_dir = Path(platformdirs.user_config_dir('rag-memory', appauthor=False))
    return config_dir / 'config.yaml'


def load_config() -> dict:
    """Load existing configuration"""
    config_path = get_config_path()

    if not config_path.exists():
        print_error(f"Configuration not found: {config_path}")
        print_info("Run 'python scripts/setup.py' to create initial configuration")
        sys.exit(1)

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        return config
    except Exception as e:
        print_error(f"Failed to load configuration: {e}")
        sys.exit(1)


def save_config(config: dict) -> bool:
    """Save updated configuration"""
    config_path = get_config_path()

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print_success(f"Configuration saved: {config_path}")
        return True
    except Exception as e:
        print_error(f"Failed to save configuration: {e}")
        return False


def update_api_key(config: dict) -> bool:
    """Prompt user to update OpenAI API key"""
    print_header("Update OpenAI API Key")

    current_key = config.get('server', {}).get('openai_api_key', '')
    if current_key:
        print_info(f"Current key: {current_key[:20]}...{current_key[-4:]}")
    else:
        print_warning("No API key configured")

    update = Confirm.ask("Update OpenAI API key?", default=False)
    if not update:
        return False

    while True:
        api_key = Prompt.ask(
            "Enter new OpenAI API key",
            password=True,
        )

        if not api_key or api_key.strip() == "":
            print_error("API key cannot be empty")
            continue

        if not api_key.startswith("sk-") or len(api_key) < 20:
            print_error("Invalid API key format. Must start with 'sk-' and be at least 20 characters")
            continue

        config['server']['openai_api_key'] = api_key.strip()
        print_success("API key updated")
        return True

    return False


def update_database_url(config: dict) -> bool:
    """Prompt user to update database URL"""
    print_header("Update Database URL")

    current_url = config.get('server', {}).get('database_url', '')
    print_info(f"Current URL: {current_url}")

    update = Confirm.ask("Update database URL?", default=False)
    if not update:
        return False

    new_url = Prompt.ask("Enter new database URL")

    if not new_url or new_url.strip() == "":
        print_error("Database URL cannot be empty")
        return False

    config['server']['database_url'] = new_url.strip()
    print_success("Database URL updated")
    return True


def update_neo4j_connection(config: dict) -> bool:
    """Prompt user to update Neo4j connection details"""
    print_header("Update Neo4j Connection")

    current_uri = config.get('server', {}).get('neo4j_uri', '')
    current_user = config.get('server', {}).get('neo4j_user', '')
    current_pass = config.get('server', {}).get('neo4j_password', '')

    print_info(f"Current URI: {current_uri}")
    print_info(f"Current user: {current_user}")

    update = Confirm.ask("Update Neo4j connection details?", default=False)
    if not update:
        return False

    # Update URI
    new_uri = Prompt.ask("Neo4j URI", default=current_uri)
    if new_uri and new_uri.strip():
        config['server']['neo4j_uri'] = new_uri.strip()
        print_success("Neo4j URI updated")

    # Update user
    new_user = Prompt.ask("Neo4j username", default=current_user)
    if new_user and new_user.strip():
        config['server']['neo4j_user'] = new_user.strip()
        print_success("Neo4j username updated")

    # Update password
    new_pass = Prompt.ask(
        "Neo4j password",
        password=True,
        default=current_pass,
    )
    if new_pass and new_pass.strip():
        config['server']['neo4j_password'] = new_pass.strip()
        print_success("Neo4j password updated")

    return True


def update_mounts(config: dict) -> bool:
    """Prompt user to update directory mounts"""
    print_header("Update Directory Mounts")

    current_mounts = config.get('mounts', [])
    if current_mounts:
        print_info("Current mounts:")
        for i, mount in enumerate(current_mounts, 1):
            path = mount.get('path', '')
            print(f"  {i}. {path}")
    else:
        print_warning("No directories currently mounted")

    update = Confirm.ask("Update directory mounts?", default=False)
    if not update:
        return False

    new_mounts = []

    # Detect home directory
    home_dir = str(Path.home())
    print_info(f"\nDetected home directory: {home_dir}")

    use_home = Confirm.ask("Mount home directory as read-only?", default=True)
    if use_home:
        new_mounts.append({
            "path": home_dir,
            "read_only": True
        })
        print_success(f"Added mount: {home_dir}")

    # Option to add custom directories
    while True:
        add_more = Confirm.ask("\nAdd additional directories?", default=False)
        if not add_more:
            break

        custom_path = Prompt.ask("Enter directory path")

        # Validate directory
        try:
            path_obj = Path(custom_path).expanduser().resolve()
            if not path_obj.exists():
                print_error(f"Directory does not exist: {path_obj}")
                continue

            if not path_obj.is_dir():
                print_error(f"Not a directory: {path_obj}")
                continue

            # Try to list directory
            try:
                list(path_obj.iterdir())
            except PermissionError:
                print_error(f"Directory is not readable: {path_obj}")
                continue

            new_mounts.append({
                "path": str(path_obj),
                "read_only": True
            })
            print_success(f"Added mount: {path_obj}")
        except Exception as e:
            print_error(f"Invalid path: {e}")

    if not new_mounts:
        print_warning("No directories configured - file ingestion will not work")
        confirm_empty = Confirm.ask("Continue without any mounts?", default=False)
        if not confirm_empty:
            return False

    config['mounts'] = new_mounts
    print_success(f"Updated {len(new_mounts)} mount(s)")
    return True


def main():
    """Main update configuration flow"""
    console.print(f"\n{Colors.BOLD}{Colors.CYAN}RAG Memory - Update Configuration{Colors.RESET}\n")

    # Load existing config
    config = load_config()
    print_success("Configuration loaded")

    # Present options
    changes_made = False

    print_header("Update Options")
    print_info("Choose which settings to update:\n")

    if update_api_key(config):
        changes_made = True

    if update_database_url(config):
        changes_made = True

    if update_neo4j_connection(config):
        changes_made = True

    if update_mounts(config):
        changes_made = True

    # Save if changes were made
    if changes_made:
        if save_config(config):
            print_header("Next Steps")
            print_info("Your configuration has been updated.")
            print_info("To apply these changes, rebuild and restart Docker containers:\n")
            console.print(f"{Colors.BOLD}docker-compose -f docker-compose.local.yml up -d --build{Colors.RESET}\n")
            print_warning("Note: This will restart your services (databases may be unavailable briefly)")
        else:
            sys.exit(1)
    else:
        print_info("No changes made to configuration")

    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\nUpdate cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
