#!/usr/bin/env bash
#
# Check Alembic migration versions across Docker and Supabase
#
# This script helps ensure both databases are at the same schema version.
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Supabase project configuration (update these values)
SUPABASE_PROJECT_REF="yjokksbyqpzjoumjdyuu"
SUPABASE_REGION="us-east-1"

echo -e "${BLUE}🔍 Checking Alembic Migration Versions...${NC}\n"

# Step 1: Check Docker version
echo -e "${BLUE}📦 Docker (Local):${NC}"
if ! docker-compose ps | grep -q "rag-memory"; then
    echo -e "${RED}❌ Docker container not running${NC}\n"
    DOCKER_VERSION="N/A"
else
    DOCKER_DB_URL="postgresql://raguser:ragpassword@localhost:54320/rag_memory"
    DOCKER_VERSION=$(DATABASE_URL="$DOCKER_DB_URL" uv run alembic current 2>/dev/null | grep -v "INFO" | head -1 || echo "Not initialized")

    if [ "$DOCKER_VERSION" == "Not initialized" ]; then
        echo -e "${YELLOW}⚠️  No migrations applied${NC}"
    else
        echo -e "${GREEN}✅ $DOCKER_VERSION${NC}"
    fi
fi
echo

# Step 2: Get Supabase password
echo -e "${YELLOW}Enter your Supabase database password (or press Enter to skip):${NC}"
read -s SUPABASE_PASSWORD
echo

if [ -z "$SUPABASE_PASSWORD" ]; then
    echo -e "${YELLOW}⏭️  Skipping Supabase check${NC}\n"
    SUPABASE_VERSION="Skipped"
else
    # Construct Supabase connection string (DIRECT connection)
    SUPABASE_DB_URL="postgresql://postgres.$SUPABASE_PROJECT_REF:$SUPABASE_PASSWORD@db.$SUPABASE_PROJECT_REF.supabase.co:5432/postgres"

    echo -e "${BLUE}☁️  Supabase (Remote):${NC}"
    SUPABASE_VERSION=$(DATABASE_URL="$SUPABASE_DB_URL" uv run alembic current 2>/dev/null | grep -v "INFO" | head -1 || echo "Not initialized")

    if [ "$SUPABASE_VERSION" == "Not initialized" ]; then
        echo -e "${YELLOW}⚠️  No migrations applied${NC}"
    else
        echo -e "${GREEN}✅ $SUPABASE_VERSION${NC}"
    fi
    echo
fi

# Step 3: Compare versions
echo -e "${BLUE}📊 Comparison:${NC}"

if [ "$DOCKER_VERSION" == "N/A" ] && [ "$SUPABASE_VERSION" == "Skipped" ]; then
    echo -e "${YELLOW}⚠️  Unable to compare (Docker not running, Supabase skipped)${NC}"
elif [ "$DOCKER_VERSION" == "$SUPABASE_VERSION" ]; then
    echo -e "${GREEN}✅ Both databases are at the same version!${NC}"
    echo -e "   Version: $DOCKER_VERSION"
elif [ "$SUPABASE_VERSION" == "Skipped" ]; then
    echo -e "${BLUE}ℹ️  Docker: $DOCKER_VERSION${NC}"
    echo -e "${YELLOW}   Supabase: Not checked${NC}"
else
    echo -e "${RED}❌ VERSION MISMATCH!${NC}"
    echo -e "   Docker:   $DOCKER_VERSION"
    echo -e "   Supabase: $SUPABASE_VERSION"
    echo
    echo -e "${YELLOW}⚠️  Databases are out of sync!${NC}"
    echo -e "${BLUE}💡 To fix:${NC}"
    echo -e "   1. Check which version is behind"
    echo -e "   2. Run: ${GREEN}uv run alembic upgrade head${NC} on the database that's behind"
    echo -e "   3. Verify again with this script"
fi
echo

# Step 4: Show migration history
echo -e "${BLUE}📜 Available Migrations:${NC}"
uv run alembic history --verbose 2>/dev/null | grep -E "^[a-f0-9]+ " || echo "Unable to fetch migration history"
