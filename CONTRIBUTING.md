# Contributing to RAG Memory

## Development Setup

```bash
# Clone repository
git clone <repo-url>
cd rag-memory

# Install dependencies
uv sync

# Start local development database
python scripts/setup.py
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_configuration.py -v

# Run with coverage
uv run pytest --cov=src
```

## Code Quality

```bash
# Format code
uv run black src tests

# Lint code
uv run ruff check src tests --fix

# Check types (if using type hints)
# (Optional: add mypy or pyright if desired)
```

## Building and Publishing to PyPI

### Prerequisites

1. PyPI account (create at https://pypi.org)
2. PyPI API token (generate at https://pypi.org/manage/account/tokens/)
3. Store token in `~/.pypirc` or use `uv` environment variable:
   ```bash
   export UV_PUBLISH_TOKEN="pypi-AgEI..."
   ```

### Publishing Steps

1. **Update version in `pyproject.toml`**
   ```toml
   [project]
   version = "0.8.0"  # Increment version number
   ```

2. **Verify all tests pass**
   ```bash
   uv run pytest
   ```

3. **Commit version bump**
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.8.0"
   ```

4. **Create git tag (optional but recommended)**
   ```bash
   git tag -a v0.8.0 -m "Release version 0.8.0"
   git push origin v0.8.0
   ```

5. **Build distribution packages**
   ```bash
   uv build
   ```
   This creates:
   - `dist/rag_memory-0.8.0.tar.gz` (source distribution)
   - `dist/rag_memory-0.8.0-py3-none-any.whl` (wheel)

6. **Publish to PyPI**
   ```bash
   # With token in environment variable
   uv publish --token "$UV_PUBLISH_TOKEN"

   # Or using ~/.pypirc configuration
   uv publish
   ```

7. **Verify publication**
   Visit https://pypi.org/project/rag-memory/ and verify the new version appears

### Troubleshooting

**"Version already exists"**: PyPI doesn't allow republishing the same version number. Increment the version and try again.

**"Unauthorized"**: Check your API token is correct and has `write` permissions.

**"Invalid distribution"**: Run `uv build` again and check for any errors in the output.

## Release Checklist

- [ ] Version bumped in `pyproject.toml`
- [ ] All tests passing (`uv run pytest`)
- [ ] Changes committed to git
- [ ] Git tag created (optional)
- [ ] `uv build` successful
- [ ] `uv publish` successful
- [ ] New version visible on PyPI
- [ ] Installation works: `uv tool install rag-memory==X.Y.Z`

## Testing a Fresh Installation

After publishing, test the installation in a clean environment:

```bash
# Create temporary directory
mkdir /tmp/rag-memory-test
cd /tmp/rag-memory-test

# Install CLI from PyPI
uv tool install rag-memory==0.8.0

# Clone repo for MCP server and setup
git clone <repo-url> rag-memory-dev
cd rag-memory-dev
python scripts/setup.py

# Test CLI tools
rag status

# MCP server is running in Docker containers
```

## Configuration System

RAG Memory uses a YAML-based configuration system stored in OS-standard locations:

- **macOS**: `~/Library/Application Support/rag-memory/config.yaml`
- **Linux**: `~/.config/rag-memory/config.yaml`
- **Windows**: `%LOCALAPPDATA%\rag-memory\config.yaml`

When running in Docker containers (MCP server), config is mounted at `/app/.config/rag-memory/config.yaml`.

For details, see the configuration loading logic in `src/core/config_loader.py`.
