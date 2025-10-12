# Environment Variable Loading in RAG Memory

This document explains how RAG Memory looks for and loads environment variables (DATABASE_URL and OPENAI_API_KEY) for both CLI and MCP server usage.

## Overview

RAG Memory uses a **three-tier priority system** for loading environment variables. The implementation is in `src/core/config_loader.py` and uses a clear, predictable order to ensure you always know where your configuration is coming from.

## Loading Priority Order (Highest to Lowest)

### 1. Environment Variables (Highest Priority)

Variables you set manually in your shell session take the highest priority.

**Examples:**
```bash
# Linux/macOS
export DATABASE_URL="postgresql://raguser:ragpass@localhost:54320/rag_poc"
export OPENAI_API_KEY="sk-..."

# Windows PowerShell
$env:DATABASE_URL="postgresql://raguser:ragpass@localhost:54320/rag_poc"
$env:OPENAI_API_KEY="sk-..."
```

- These are **already in the environment** before the tool runs
- Take precedence over everything else
- Useful for temporary overrides or CI/CD environments

### 2. Project-Specific `.env` File

A `.env` file in your current working directory for project-specific configuration.

**Location:** `./.env` (current working directory only)

**Important behaviors:**
- **No parent directory search** - must be exactly where you run the command
- Loaded using `python-dotenv` with `override=False`
- Won't override existing environment variables (respects priority #1)
- **Only used for development** - end users should NOT need this

**Example `.env` file:**
```bash
DATABASE_URL=postgresql://raguser:ragpass@localhost:54320/rag_poc
OPENAI_API_KEY=sk-proj-...
```

**This is for developers only** - users installing from PyPI will NOT have this file.

### 3. User-Specific Global Config File

A global configuration file in your home directory that persists across all projects.

**Location:** `~/.rag-memory-env`

**Behaviors:**
- Loaded using custom `load_env_file()` function
- Only sets variables that aren't already in the environment
- This is where the **first-run setup** saves your configuration
- Can be edited manually or managed by the CLI
- Works across all platforms (Windows, macOS, Linux)

**File format:**
```bash
# RAG Memory - Configuration File
# This file is automatically managed by rag-memory
# You can edit or delete this file anytime

# PostgreSQL connection for RAG Memory (default Docker setup)
DATABASE_URL=postgresql://raguser:ragpass@localhost:54320/rag_poc

# OpenAI API key for embeddings
OPENAI_API_KEY=sk-...
```

## First-Run Setup (Interactive)

When you run any CLI command for the first time, RAG Memory will:

1. **Check for configuration** - Look for `~/.rag-memory-env`
2. **Prompt for setup** if not found:
   - Ask for DATABASE_URL (provides default for Docker setup)
   - Ask for OPENAI_API_KEY (password-masked input)
3. **Save configuration** to `~/.rag-memory-env`
4. **Set file permissions** to `0o600` (user-only read/write on Unix systems)
5. **Proceed with command** once config is ready

**Example interactive prompt:**
```
🔧 First-Time Setup Required

RAG Memory needs to create a configuration file: ~/.rag-memory-env

This will store your database connection and API key settings.
The file will be created with user-only permissions (chmod 0o600).

Would you like to set this up now? [Y/n]: y

1. Database Configuration
If you're using the default Docker setup, press Enter to accept the default.
Database URL [postgresql://raguser:ragpass@localhost:54320/rag_poc]:

2. OpenAI API Key
Your API key will be stored securely with user-only file permissions.
Get your key from: https://platform.openai.com/api-keys
OpenAI API Key: ****

Saving configuration...
✓ Configuration saved to ~/.rag-memory-env

You can edit this file anytime to update your settings.
```

## MCP Server Configuration

For MCP server usage (Claude Desktop, Claude Code, Cursor), environment variables are passed via the MCP client configuration:

**Example (Claude Desktop config):**
```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "rag-mcp-stdio",
      "args": [],
      "env": {
        "OPENAI_API_KEY": "sk-your-api-key-here",
        "DATABASE_URL": "postgresql://raguser:ragpass@localhost:54320/rag_poc"
      }
    }
  }
}
```

**Important:**
- MCP server does NOT use `~/.rag-memory-env` file
- All config comes from the MCP client's `env` section
- Both DATABASE_URL and OPENAI_API_KEY are required

## Implementation Details

### Key Code (from `src/core/config_loader.py`)

```python
def load_environment_variables():
    """
    Load environment variables using three-tier priority system.

    Priority order (highest to lowest):
    1. Environment variables (already set in shell)
    2. Project .env file (current directory only)
    3. Global ~/.rag-memory-env file (user-specific)
    """
    # 1. Environment variables - highest priority, already in os.environ

    # 2. Project .env file - current directory only (for development)
    current_dir_env = Path.cwd() / '.env'
    if current_dir_env.exists():
        # override=False means env vars take precedence
        load_dotenv(dotenv_path=current_dir_env, override=False)

    # 3. Global user config file - lowest priority
    global_config = get_global_config_path()
    if global_config.exists():
        env_vars = load_env_file(global_config)
        for key, value in env_vars.items():
            # Only set if not already in environment
            if key not in os.environ:
                os.environ[key] = value
```

### Cross-Platform Support

The system works on all platforms:

- **File path:** `Path.home() / ".rag-memory-env"` works on Windows, macOS, Linux
- **Permissions:** `chmod 0o600` on Unix-like systems, Windows file permissions handled by OS
- **Environment variables:** Standard Python `os.environ` works everywhere

## Important Behaviors

1. **No recursive search**: The `.env` file is only loaded from the current working directory, not parent directories
2. **No override**: Later sources never override earlier ones - priority is strictly maintained
3. **Case sensitive**: Environment variable names are case-sensitive
4. **First-run wizard**: Runs automatically on first CLI command (skipped if config exists)

## Security Features

- The `~/.rag-memory-env` file is set to user-only permissions (`chmod 0o600`) on Unix-like systems (macOS, Linux, WSL)
- API keys are masked during interactive input
- The tool checks for permissions before attempting to save keys
- On Windows, file permissions are handled by the OS differently but the file is still protected

## Use Cases

### Use Case 1: End User (PyPI Installation)

1. Install: `uv tool install rag-memory`
2. Run any command: `rag status`
3. First-run wizard creates `~/.rag-memory-env`
4. All future commands use that config

**No need for:**
- Cloning the repo
- Creating `.env` files
- Setting system environment variables (unless you want to override)

### Use Case 2: Developer (Cloned Repo)

1. Clone repo: `git clone https://github.com/YOUR-USERNAME/rag-memory.git`
2. Install deps: `cd rag-memory && uv sync`
3. Create `.env`: `cp .env.example .env`
4. Edit `.env` with your settings
5. Run CLI: `uv run rag status`

**Project `.env` takes precedence** over `~/.rag-memory-env` for dev work.

### Use Case 3: MCP Server (AI Agent)

1. Install: `uv tool install rag-memory`
2. Configure MCP client with both DATABASE_URL and OPENAI_API_KEY in `env` section
3. Restart AI agent
4. MCP server uses config from MCP client, NOT from files

### Use Case 4: Temporary Override

```bash
# Override database for one command
export DATABASE_URL="postgresql://otheruser:otherpass@localhost:5432/other_db"
rag status  # Uses the override

# In a new terminal, back to global config
rag status  # Uses ~/.rag-memory-env
```

### Use Case 5: CI/CD Usage

```bash
# In your CI/CD pipeline, set environment variables
export DATABASE_URL="${SECRET_DB_URL}"
export OPENAI_API_KEY="${SECRET_API_KEY}"
rag ingest file documentation.md --collection docs
```

## Design Philosophy

This design makes configuration **simple and predictable**:

1. ✅ **Explicit environment variables win** - highest priority for overrides
2. ✅ **Project configs next** - per-project settings for developers
3. ✅ **Global user config last** - convenient default for end users
4. ✅ **No magic** - clear, documented priority order
5. ✅ **No surprises** - earlier sources always win, never overridden
6. ✅ **First-run wizard** - no manual file creation required
7. ✅ **Cross-platform** - works on Windows, macOS, Linux

## Troubleshooting

### "DATABASE_URL not found" error

**Check in order:**
1. Is the environment variable set? `echo $DATABASE_URL` (Unix) or `echo %DATABASE_URL%` (Windows)
2. Is there a `.env` file in current directory? `cat .env` (only for dev)
3. Is there a global config? `cat ~/.rag-memory-env`
4. Did first-run setup complete? Run any command to restart wizard

### "OPENAI_API_KEY not found" error

**Check:**
- Global config exists: `cat ~/.rag-memory-env | grep OPENAI_API_KEY`
- Key is valid (starts with `sk-`)
- No extra spaces or quotes in the config file

### Can't save configuration during first-run

**Check:**
- Home directory is writable: `touch ~/.rag-memory-env`
- File permissions (Unix): `ls -la ~/.rag-memory-env`
- Manually create if needed: `nano ~/.rag-memory-env` (edit and save)

### Wrong config being used

**Remember priority order:**
- Environment variables override everything
- Check what's set: `env | grep -E '(DATABASE_URL|OPENAI_API_KEY)'`
- Unset if needed: `unset DATABASE_URL` (Unix) or `Remove-Item Env:DATABASE_URL` (PowerShell)

### MCP server can't connect

**Check MCP client config:**
- Both DATABASE_URL and OPENAI_API_KEY in `env` section
- No trailing commas in JSON
- Database is running: `docker-compose ps`

## Related Files

- `src/core/config_loader.py` - Configuration loading logic
- `src/core/first_run.py` - First-run setup wizard
- `src/core/database.py` - Uses config_loader
- `src/core/embeddings.py` - Uses config_loader
- `src/cli.py` - CLI entry point with first-run check
- `~/.rag-memory-env` - Your global config file (created automatically)
