# Repository Reorganization Plan

## Executive Summary

This document provides a detailed plan for reorganizing the RAG Memory repository structure to reduce root-level clutter from ~50 files to ~10 essential files, while maintaining all functionality and not breaking any dependencies.

## Current State Analysis

### Root Directory Issues
- **19 coverage files**: `.coverage.Tims-MacBook-Pro.local.*` (test artifacts)
- **5 docker-compose files**: yml, dev.yml, test.yml, template.yml, plus generated yml
- **5 environment files**: .env, .env.dev, .env.test, .env.prod, backup.env
- **2 Fly.io configs**: fly.toml, fly.test.toml
- **Multiple build/setup files**: build.sh, init.sql, alembic.ini, sitecustomize.py
- **Test file at root**: test_startup_validations.py
- **Documentation scattered**: Various .md files mixed with code

### Critical Dependencies Found

1. **Docker Compose Path References**:
   - `scripts/setup.py:L448-449`: Reads template from root, generates compose file to root
   - `scripts/setup.py:L501`: Runs `docker-compose` expecting file in root
   - `tests/conftest.py`: References test compose file location
   - All compose files mount `./init.sql` as volume

2. **Alembic Configuration**:
   - `alembic.ini:L8`: `script_location = %(here)s/alembic`
   - Uses `%(here)s` token (location of ini file) as reference point

3. **Dockerfile Build Context**:
   - Copies: `alembic/`, `alembic.ini`, `init.sql` from root context
   - Docker compose files expect Dockerfile at root

4. **Test Configuration**:
   - `tests/conftest.py:L47`: Sets config path to `repo_root / 'config'`
   - Expects `.env.test` and `.env.dev` at repo root

5. **Backup Configuration**:
   - Docker compose expects `./backups` directory relative to compose file location
   - Can be configured via environment variable

## Proposed New Structure

```
rag-memory/
├── src/                        # [NO CHANGE] Application source code
├── tests/                      # [NO CHANGE] Test suite
├── docs/                       # [EXPAND] Consolidate all documentation
│   ├── architecture/           # Technical documentation
│   ├── setup/                  # Setup guides
│   └── api/                    # API documentation
├── config/                     # [NO CHANGE] Configuration files
│   ├── config.dev.yaml
│   ├── config.test.yaml
│   ├── config.local.yaml
│   └── config.example.yaml
├── scripts/                    # [NO CHANGE] Utility scripts
│   ├── setup.py
│   ├── build.sh               # Move here if desired
│   └── ...
├── deploy/                     # [NEW] All deployment artifacts
│   ├── docker/                 # Docker-related files
│   │   ├── compose/           # All docker-compose files
│   │   │   ├── docker-compose.yml
│   │   │   ├── docker-compose.dev.yml
│   │   │   ├── docker-compose.test.yml
│   │   │   └── docker-compose.template.yml
│   │   ├── init.sql           # Database initialization
│   │   └── Dockerfile         # Container definition
│   ├── fly/                   # Fly.io deployment
│   │   ├── fly.toml
│   │   └── fly.test.toml
│   └── alembic/               # Database migrations
│       ├── alembic.ini
│       ├── env.py
│       └── versions/
├── build/                      # [NEW] Build artifacts (gitignored)
│   ├── coverage/              # Coverage reports
│   └── dist/                  # Distribution packages
├── data/                       # [NEW] Data directories (gitignored)
│   └── backups/               # Database backups
├── .github/                    # [NEW] GitHub-specific files
│   └── CONTRIBUTING.md
├── .reference/                 # [NO CHANGE] Project reference docs
├── .claude/                    # [NO CHANGE] Claude-specific config
├── pyproject.toml             # [MUST STAY] Python project definition
├── uv.lock                    # [MUST STAY] Dependency lock
├── README.md                  # [MUST STAY] Main documentation
├── LICENSE                    # [MUST STAY] Legal
├── CLAUDE.md                  # [MUST STAY] Project memory
├── .gitignore                 # [MUST STAY] Git configuration
├── .dockerignore              # [MUST STAY] Docker configuration
├── .coveragerc                # [MUST STAY] Coverage config
├── .env.example               # [MUST STAY] Environment template
└── .env                       # [MUST STAY] Local secrets (gitignored)
```

## Required Code Changes

### 1. setup.py Updates

```python
# Line 448-449 (old)
template_path = project_root / 'docker-compose.template.yml'
compose_path = project_root / 'docker-compose.yml'

# Line 448-449 (new)
template_path = project_root / 'deploy' / 'docker' / 'compose' / 'docker-compose.template.yml'
compose_path = project_root / 'deploy' / 'docker' / 'compose' / 'docker-compose.yml'

# Line 501 (old - docker-compose command)
"docker-compose",

# Line 501 (new)
"docker-compose", "-f", str(compose_path),
```

### 2. Docker Compose Files Updates

All compose files need these changes:

```yaml
# Old - Dockerfile reference
build:
  context: .
  dockerfile: Dockerfile

# New - Dockerfile reference
build:
  context: ../../..
  dockerfile: deploy/docker/Dockerfile

# Old - init.sql mount
volumes:
  - ./init.sql:/docker-entrypoint-initdb.d/init.sql

# New - init.sql mount
volumes:
  - ../init.sql:/docker-entrypoint-initdb.d/init.sql

# Old - backup directory
BACKUP_ARCHIVE_DIR: "${BACKUP_ARCHIVE_DIR:-./backups}"

# New - backup directory
BACKUP_ARCHIVE_DIR: "${BACKUP_ARCHIVE_DIR:-../../../../data/backups}"
```

### 3. Alembic Configuration

Move alembic.ini to deploy/alembic/ and update:

```ini
# Old
script_location = %(here)s/alembic

# New (no change needed - %(here)s is relative to ini file location)
script_location = %(here)s
```

### 4. Dockerfile Updates

```dockerfile
# Old - copy from root
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY init.sql /app/init.sql

# New - copy from deploy paths
COPY deploy/alembic /app/alembic
COPY deploy/alembic/alembic.ini /app/alembic.ini
COPY deploy/docker/init.sql /app/init.sql
```

### 5. Test Configuration (conftest.py)

```python
# No changes needed - already uses relative paths correctly
```

### 6. .gitignore Updates

Add:
```
# Build artifacts
/build/
/data/backups/

# Coverage files (now in build/coverage/)
.coverage.*
htmlcov/
```

### 7. Command Documentation Updates

Update `.claude/commands/getting-started.md` and any other docs:

```bash
# Old
docker-compose -f docker-compose.dev.yml up -d

# New
docker-compose -f deploy/docker/compose/docker-compose.dev.yml up -d
```

## Migration Steps

### Phase 1: Create Directory Structure
```bash
# Create new directories
mkdir -p deploy/docker/compose
mkdir -p deploy/fly
mkdir -p deploy/alembic
mkdir -p build/coverage
mkdir -p data/backups
mkdir -p .github
mkdir -p docs/architecture
mkdir -p docs/setup
mkdir -p docs/api
```

### Phase 2: Move Files (Preserving Git History)
```bash
# Move docker files
git mv docker-compose*.yml deploy/docker/compose/
git mv Dockerfile deploy/docker/
git mv init.sql deploy/docker/

# Move Fly.io files
git mv fly*.toml deploy/fly/

# Move alembic files
git mv alembic.ini deploy/alembic/
git mv alembic/* deploy/alembic/

# Move documentation
git mv CONTRIBUTING.md .github/
git mv FLYIO_SCALE_TO_ZERO_ISSUE.md docs/architecture/
git mv TEST_COVERAGE_AUDIT.md docs/architecture/

# Move test file
git mv test_startup_validations.py tests/

# Move build script (optional)
git mv build.sh scripts/
```

### Phase 3: Update Code References
1. Apply all code changes listed in "Required Code Changes" section
2. Run tests to verify nothing broke
3. Update any additional documentation

### Phase 4: Clean Up
```bash
# Remove coverage files (they'll regenerate in build/coverage/)
rm -f .coverage.*

# Remove backup.env if not needed
rm -f backup.env

# Update .gitignore
```

## Testing Plan

1. **Docker Compose Tests**:
   ```bash
   # Test each compose file works
   docker-compose -f deploy/docker/compose/docker-compose.yml up -d
   docker-compose -f deploy/docker/compose/docker-compose.dev.yml up -d
   docker-compose -f deploy/docker/compose/docker-compose.test.yml up -d
   ```

2. **Setup Script Test**:
   ```bash
   python scripts/setup.py
   ```

3. **Test Suite**:
   ```bash
   uv run pytest tests/
   ```

4. **Build Test**:
   ```bash
   scripts/build.sh
   ```

5. **Alembic Migrations**:
   ```bash
   cd deploy/alembic
   alembic upgrade head
   ```

## Benefits After Reorganization

1. **Root directory**: Reduced from ~50 files to ~10 essential files
2. **Clear separation**: Deploy/, config/, scripts/, docs/ have distinct purposes
3. **Better gitignore**: Coverage and build artifacts automatically contained
4. **Improved discoverability**: Related files grouped together
5. **Cleaner Docker context**: All Docker files in one place
6. **Organized deployments**: Fly.io separate from Docker local setup

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking setup.py | Test thoroughly, update all path references |
| Docker build context issues | Verify context paths in compose files |
| Alembic can't find migrations | Test alembic commands after move |
| CI/CD breaks | No CI/CD currently, but document changes needed |
| User confusion | Update all documentation with new paths |

## Rollback Plan

If issues arise:
1. Git history preserved with `git mv`
2. Can revert commit to restore original structure
3. All changes are in version control

## Notes

- sitecustomize.py purpose unclear - may be able to remove
- backup.env appears to be a duplicate - can likely remove
- openai_debug.log should be gitignored if not already
- coverage_analysis.md could move to docs/architecture/

---

**Status**: Ready for implementation when tests complete
**Last Updated**: 2025-10-25