#!/usr/bin/env bash
#
# Sync database from Supabase to local Docker
#
# Usage: ./sync-from-supabase.sh <project-id> [region]
#
# Arguments:
#   project-id  - Your Supabase project ID (e.g., yjokksbyqpzjoumjdyuu)
#   region      - Your Supabase region (default: us-east-1)
#
# This script exports your Supabase database and imports it to local Docker.
# WARNING: This DESTROYS all local Docker data!
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Validate arguments
if [ $# -lt 1 ]; then
    echo -e "${RED}❌ Error: Supabase project ID is required${NC}"
    echo "Usage: $0 <project-id> [region]"
    echo "Example: $0 yjokksbyqpzjoumjdyuu us-east-1"
    exit 1
fi

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUPS_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUPS_DIR/supabase_sync_$TIMESTAMP.sql"

# Supabase project configuration from command-line arguments
SUPABASE_PROJECT_REF="$1"
SUPABASE_REGION="${2:-us-east-1}"

echo -e "${BLUE}🔄 Syncing Supabase → Docker...${NC}"
echo -e "   Project ID: ${YELLOW}$SUPABASE_PROJECT_REF${NC}"
echo -e "   Region: ${YELLOW}$SUPABASE_REGION${NC}\n"

# Step 1: Get Supabase password
echo -e "${YELLOW}Enter your Supabase database password:${NC}"
read -s SUPABASE_PASSWORD
echo

# Construct Supabase connection string (DIRECT connection for pg_dump)
SUPABASE_DB_URL="postgresql://postgres.$SUPABASE_PROJECT_REF:$SUPABASE_PASSWORD@db.$SUPABASE_PROJECT_REF.supabase.co:5432/postgres"

# Step 2: Create backups directory
mkdir -p "$BACKUPS_DIR"

# Step 3: Export from Supabase
echo -e "${BLUE}📤 Exporting from Supabase...${NC}"
if pg_dump "$SUPABASE_DB_URL" > "$BACKUP_FILE" 2>/dev/null; then
    echo -e "${GREEN}✅ Export complete: $BACKUP_FILE${NC}"
    BACKUP_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo -e "   Size: $BACKUP_SIZE\n"
else
    echo -e "${RED}❌ Export failed. Check your password and connection.${NC}"
    exit 1
fi

# Step 4: Check if Docker is running
echo -e "${BLUE}🐳 Checking Docker...${NC}"
if ! docker-compose ps | grep -q "rag-memory"; then
    echo -e "${RED}❌ Docker container 'rag-memory' is not running.${NC}"
    echo -e "   Run: docker-compose up -d"
    exit 1
fi
echo -e "${GREEN}✅ Docker is running${NC}\n"

# Step 5: Warn about data loss
echo -e "${RED}⚠️  WARNING: This will DESTROY all local Docker data!${NC}"
echo -e "${YELLOW}Do you want to continue? (yes/no)${NC}"
read -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}❌ Sync cancelled.${NC}"
    exit 0
fi

# Step 6: Drop and recreate local database
echo -e "\n${BLUE}🗑️  Dropping local database...${NC}"
docker exec rag-memory psql -U raguser -d postgres -c "DROP DATABASE IF EXISTS rag_memory;" 2>/dev/null
docker exec rag-memory psql -U raguser -d postgres -c "CREATE DATABASE rag_memory;" 2>/dev/null
echo -e "${GREEN}✅ Local database reset${NC}\n"

# Step 7: Import to Docker
echo -e "${BLUE}📥 Importing to Docker...${NC}"
if docker exec -i rag-memory psql -U raguser rag_memory < "$BACKUP_FILE" 2>&1 | grep -v "ERROR.*role.*already exists" | grep -v "ERROR.*extension.*already exists" > /dev/null; then
    echo -e "${GREEN}✅ Import complete!${NC}\n"
else
    # Check for actual errors (not just the expected ones)
    ERRORS=$(docker exec -i rag-memory psql -U raguser rag_memory < "$BACKUP_FILE" 2>&1 | grep "ERROR" | grep -v "role.*already exists" | grep -v "extension.*already exists" || true)
    if [ -n "$ERRORS" ]; then
        echo -e "${RED}❌ Import had errors:${NC}"
        echo "$ERRORS"
        exit 1
    fi
fi

# Step 8: Verify import
echo -e "${BLUE}📊 Verification:${NC}"
COLLECTIONS=$(docker exec rag-memory psql -U raguser -d rag_memory -tAc "SELECT COUNT(*) FROM collections;" 2>/dev/null)
DOCUMENTS=$(docker exec rag-memory psql -U raguser -d rag_memory -tAc "SELECT COUNT(*) FROM source_documents;" 2>/dev/null)
CHUNKS=$(docker exec rag-memory psql -U raguser -d rag_memory -tAc "SELECT COUNT(*) FROM document_chunks;" 2>/dev/null)

echo -e "   Collections: ${GREEN}$COLLECTIONS${NC}"
echo -e "   Documents: ${GREEN}$DOCUMENTS${NC}"
echo -e "   Chunks: ${GREEN}$CHUNKS${NC}\n"

echo -e "${GREEN}✅ Sync complete!${NC}"
echo -e "${BLUE}💡 Tip: Update your DATABASE_URL to use Docker:${NC}"
echo -e "   DATABASE_URL=postgresql://raguser:ragpassword@localhost:54320/rag_memory"
