# RAG Memory Configuration System

## Overview

The configuration system automatically detects missing environment variables on every startup and prompts users to provide them. This enables seamless upgrades and fresh installations without requiring manual file editing.

## How It Works

### Configuration Hierarchy

When RAG Memory starts, it checks for required variables in this order:

```
1. Shell environment variables (highest priority)
2. ~/.rag-memory-env (global user config file)
```

### Required Variables

The following variables are required to run RAG Memory:

```python
REQUIRED_VARIABLES = [
    'DATABASE_URL',           # PostgreSQL/Supabase connection
    'OPENAI_API_KEY',         # OpenAI API key for embeddings
    'NEO4J_URI',              # Neo4j Aura connection URI
    'NEO4J_USER',             # Neo4j username (default: neo4j)
    'NEO4J_PASSWORD',         # Neo4j password
]
```

### Configuration File

The configuration file is stored at:
- **Linux/Mac:** `~/.rag-memory-env`
- **Windows:** `%USERPROFILE%\.rag-memory-env`

**Format:** Simple KEY=VALUE pairs
```
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-...
NEO4J_URI=neo4j+s://...
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
```

**Security:** File permissions are set to `0o600` (read/write for user only) on Unix-like systems.

## Scenarios

### Scenario 1: Fresh Installation

**User action:** Install RAG Memory and run it for the first time

**What happens:**
1. System detects no config file exists
2. Prompts: "⚠️  Missing Configuration"
3. Shows list of missing variables
4. Asks: "Would you like to configure these now?"
5. Prompts user for each variable (in order):
   - PostgreSQL/Supabase Database URL
   - OpenAI API Key (password input, hidden)
   - Neo4j Aura Connection URI
   - Neo4j Username
   - Neo4j Password (password input, hidden)
6. Saves to `~/.rag-memory-env`
7. Configuration complete, app starts

**Result:** One-time setup, no manual file editing

### Scenario 2: Upgrade (Old Version to New)

**User action:** Has old RAG Memory (from before Neo4j support) → runs `uv pip install --upgrade rag-memory` → runs app

**Old config file (~/.rag-memory-env):**
```
DATABASE_URL=postgresql://...
OPENAI_API_KEY=sk-...
```

**What happens:**
1. System loads existing config (DATABASE_URL and OPENAI_API_KEY exist)
2. Detects 3 missing variables (the new Neo4j ones)
3. Prompts: "⚠️  Missing Configuration"
4. Shows: "Your configuration file is missing 3 required variables."
5. Explains: "This typically happens when RAG Memory is upgraded with new features."
6. Lists missing: "NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD"
7. Asks: "Would you like to configure these now?"
8. Prompts only for the missing variables (Neo4j credentials)
9. Adds them to existing config file
10. Configuration complete

**Result:** Seamless upgrade - only new variables are prompted for

### Scenario 3: Shell Environment Variables

**User action:** Sets env vars in shell, then runs RAG Memory

**Shell setup:**
```bash
export DATABASE_URL="postgresql://..."
export OPENAI_API_KEY="sk-..."
export NEO4J_URI="neo4j+s://..."
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="..."

# Run app
rag-memory search "query"
```

**What happens:**
1. System checks shell environment variables first
2. Finds all 5 variables already set
3. No prompts needed
4. App starts immediately

**Result:** No config file needed if all vars are in environment

### Scenario 4: Partial Configuration

**User action:** User accidentally deletes NEO4J_PASSWORD from config file

**Config file missing:**
```
NEO4J_PASSWORD=...  # DELETED
```

**What happens:**
1. System detects NEO4J_PASSWORD missing from both config and environment
2. Prompts: "⚠️  Missing Configuration"
3. Lists missing: "NEO4J_PASSWORD"
4. Prompts only for that one variable
5. Adds it back to config file

**Result:** Self-healing - system detects any missing variable

## Adding New Features

If you add a new feature requiring environment variables:

1. Add to `REQUIRED_VARIABLES` in `src/core/config_loader.py`:
   ```python
   REQUIRED_VARIABLES = [
       'DATABASE_URL',
       'OPENAI_API_KEY',
       'NEO4J_URI',
       'NEO4J_USER',
       'NEO4J_PASSWORD',
       'NEW_FEATURE_VAR',  # Add here
   ]
   ```

2. Add prompt text in `src/core/first_run.py`:
   ```python
   prompts = {
       ...
       'NEW_FEATURE_VAR': 'Description for user',
   }
   ```

3. Optionally add default value:
   ```python
   defaults = {
       ...
       'NEW_FEATURE_VAR': 'default-value',
   }
   ```

4. Done! On next startup:
   - Users with old configs will be prompted for the new variable
   - New installations will be prompted for all variables including the new one
   - No manual config file editing needed

## User-Friendly Prompts

The system provides user-friendly prompts for each variable:

| Variable | Prompt | Input Type | Default |
|----------|--------|-----------|---------|
| `DATABASE_URL` | PostgreSQL/Supabase Database URL | Text | Local Docker URL |
| `OPENAI_API_KEY` | OpenAI API Key | Password (hidden) | None |
| `NEO4J_URI` | Neo4j Aura Connection URI | Text | None |
| `NEO4J_USER` | Neo4j Username | Text | neo4j |
| `NEO4J_PASSWORD` | Neo4j Password | Password (hidden) | None |

## Implementation Details

### Core Functions

**`ensure_config_or_exit()` (src/core/first_run.py)**
- Called on every MCP server startup
- Loads environment variables
- Calls `prompt_for_missing_variables()`
- Exits if configuration incomplete

**`prompt_for_missing_variables()` (src/core/first_run.py)**
- Detects missing variables
- Shows user-friendly prompt
- Prompts for each missing variable
- Saves to config file
- Handles fresh installs, upgrades, and partial configs

**`get_missing_variables()` (src/core/config_loader.py)**
- Returns list of variables missing from both config file and environment
- Enables the self-healing configuration system

**`REQUIRED_VARIABLES` (src/core/config_loader.py)**
- Central list of all required variables
- Single source of truth for configuration requirements
- Easy to extend for new features

### Security Features

1. **File Permissions:** Config file created with `0o600` (user read/write only)
2. **Password Masking:** Password fields use `Prompt.ask(..., password=True)` to hide input
3. **No Default Passwords:** Actual values are never hardcoded or shown in prompts
4. **Environment Variable Priority:** Shell env vars override config file (can pass via MCP client JSON config)

## Troubleshooting

### "Configuration is required to use RAG Memory"

This appears when the wizard exits. Either:
1. User declined to configure (answer "yes" to configure)
2. User provided empty value for required variable
3. File permissions issue

Run the app again to restart the configuration wizard.

### Config file won't save

**Possible causes:**
1. `~/.rag-memory-env` directory doesn't exist (mkdirs parent)
2. Permission issues (check `~/.` directory permissions)
3. Disk full

**Solution:** System fails silently but prompts again on next startup.

### Variable not being recognized

1. Check if set in shell: `echo $VARIABLE_NAME`
2. Check if in config file: `cat ~/.rag-memory-env`
3. Verify no typos in variable name (case-sensitive)
4. For shell vars: must be `export VARIABLE_NAME=value`

## Future Extensions

The system is designed to be extensible:

- Add new required variables to `REQUIRED_VARIABLES`
- Add prompts to `_get_prompt_text()`
- Add defaults to `_get_default_value()`
- On next upgrade, users are automatically prompted for new variables
- No breaking changes or manual migration needed

## Testing

To test the configuration system:

```bash
# Test fresh install
rm ~/.rag-memory-env
uv run rag <any-command>  # Should prompt for all variables

# Test upgrade
# Edit ~/.rag-memory-env to remove NEO4J_PASSWORD
uv run rag <any-command>  # Should prompt only for NEO4J_PASSWORD

# Test shell env vars
export DATABASE_URL="postgresql://..."
export OPENAI_API_KEY="sk-..."
export NEO4J_URI="neo4j+s://..."
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="..."
uv run rag <any-command>  # Should start without prompting
```

