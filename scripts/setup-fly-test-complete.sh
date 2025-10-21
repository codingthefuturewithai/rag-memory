#!/bin/bash
# Complete Fly.io test deployment setup in ONE command
# Handles: app creation, volumes, secrets, and deployment
# Usage: ./scripts/setup-fly-test-complete.sh MY_APP_NAME
# Example: ./scripts/setup-fly-test-complete.sh my-rag-app

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 APP_NAME"
    echo "Example: $0 my-rag-app"
    echo ""
    echo "This will create a Fly.io app with your chosen name and deploy RAG Memory to it."
    exit 1
fi

APP_NAME="$1"
CONFIG_FILE="fly.test.toml"
REGION="iad"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}▶ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
log_error() { echo -e "${RED}✗ $1${NC}"; }
log_step() { echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; echo -e "${BLUE}$1${NC}"; echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

check_flyctl() {
    if ! command -v flyctl &> /dev/null; then
        log_error "flyctl not found. Install from https://fly.io/docs/hands-on/install-flyctl/"
        exit 1
    fi
}

check_authenticated() {
    if ! flyctl auth whoami &> /dev/null; then
        log_error "Not authenticated with Fly.io. Run: flyctl auth login"
        exit 1
    fi
}

get_api_key() {
    log_warn "IMPORTANT: You need your OpenAI API key to proceed."
    echo ""
    read -p "Enter your OPENAI_API_KEY (will be stored securely in Fly.io): " -r OPENAI_API_KEY

    if [ -z "$OPENAI_API_KEY" ]; then
        log_error "API key cannot be empty"
        exit 1
    fi
}

main() {
    log_step "FLY.IO TEST DEPLOYMENT - COMPLETE SETUP"

    check_flyctl
    check_authenticated

    get_api_key

    log_step "STEP 1: Creating Fly.io app (rag-memory-test)"
    log_info "This app is completely separate from your production rag-memory-mcp app"

    flyctl launch \
        --copy-config \
        --name "$APP_NAME" \
        --region "$REGION" \
        --org personal \
        --no-deploy \
        2>&1 | grep -v "^$"

    log_step "STEP 2: Creating persistent volumes"
    log_info "Creating 3 volumes with automatic daily snapshots..."

    log_info "  Creating postgres_data (10 GB)..."
    flyctl volumes create postgres_data \
        --size 10 \
        --region "$REGION" \
        --app "$APP_NAME" \
        --yes \
        2>&1 | grep -E "ID:|Name:|Size GB:|Snapshot" || true

    log_info "  Creating neo4j_data (10 GB)..."
    flyctl volumes create neo4j_data \
        --size 10 \
        --region "$REGION" \
        --app "$APP_NAME" \
        --yes \
        2>&1 | grep -E "ID:|Name:|Size GB:|Snapshot" || true

    log_info "  Creating neo4j_logs (5 GB)..."
    flyctl volumes create neo4j_logs \
        --size 5 \
        --region "$REGION" \
        --app "$APP_NAME" \
        --yes \
        2>&1 | grep -E "ID:|Name:|Size GB:|Snapshot" || true

    log_step "STEP 3: Setting OPENAI_API_KEY secret"
    log_info "Storing API key securely in Fly.io..."

    flyctl secrets set OPENAI_API_KEY="$OPENAI_API_KEY" --app "$APP_NAME" \
        2>&1 | grep -v "^$"

    log_info "Secret stored (value hidden for security)"

    log_step "STEP 4: Deploying to Fly.io"
    log_warn "This will take 5-10 minutes. Building Docker image and starting services..."

    flyctl deploy \
        --config "$CONFIG_FILE" \
        --app "$APP_NAME" \
        --wait-timeout 300 \
        2>&1

    log_step "DEPLOYMENT COMPLETE ✅"
    log_info "App deployed: $APP_NAME"
    log_info "App URL: https://$APP_NAME.fly.dev"
    echo ""
    log_info "Next steps:"
    echo "  1. Check status: flyctl status --app $APP_NAME"
    echo "  2. View logs: flyctl logs --app $APP_NAME"
    echo "  3. Run verification: See docs/FLYIO_TEST_VERIFICATION.md"
    echo ""
    log_info "To delete this test app later: flyctl apps destroy $APP_NAME"
}

main
