#!/bin/bash
# Deploy RAG Memory to Fly.io test environment (rag-memory-test)
# Completely isolated from existing rag-memory-mcp production app
#
# Usage: ./scripts/deploy-fly-test.sh [command]
#   ./scripts/deploy-fly-test.sh launch    - Create new test app
#   ./scripts/deploy-fly-test.sh volumes   - Create required volumes
#   ./scripts/deploy-fly-test.sh secrets    - Set OPENAI_API_KEY
#   ./scripts/deploy-fly-test.sh deploy    - Deploy to Fly.io
#   ./scripts/deploy-fly-test.sh status    - Check app status
#   ./scripts/deploy-fly-test.sh logs      - View recent logs
#   ./scripts/deploy-fly-test.sh shell     - SSH into container
#   ./scripts/deploy-fly-test.sh destroy   - Delete test app (careful!)
#
# Run without arguments for full setup from scratch

set -e

APP_NAME="rag-memory-test"
CONFIG_FILE="fly.test.toml"
REGION="iad"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}▶ $1${NC}"
}

log_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

log_error() {
    echo -e "${RED}✗ $1${NC}"
}

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

cmd_launch() {
    log_info "Creating new Fly.io app: $APP_NAME"

    # Create app using docker-compose.prod.yml
    flyctl launch \
        --copy-config \
        --name "$APP_NAME" \
        --region "$REGION" \
        --org personal \
        --no-deploy

    log_info "App created. Next: run './scripts/deploy-fly-test.sh volumes'"
}

cmd_volumes() {
    log_info "Creating persistent volumes for $APP_NAME..."

    log_info "  Creating postgres_data (10 GB)..."
    flyctl volumes create postgres_data \
        --size 10 \
        --region "$REGION" \
        --app "$APP_NAME" 2>/dev/null || log_warn "postgres_data may already exist"

    log_info "  Creating neo4j_data (10 GB)..."
    flyctl volumes create neo4j_data \
        --size 10 \
        --region "$REGION" \
        --app "$APP_NAME" 2>/dev/null || log_warn "neo4j_data may already exist"

    log_info "  Creating neo4j_logs (5 GB)..."
    flyctl volumes create neo4j_logs \
        --size 5 \
        --region "$REGION" \
        --app "$APP_NAME" 2>/dev/null || log_warn "neo4j_logs may already exist"

    log_info "Verifying volumes..."
    flyctl volumes list --app "$APP_NAME"

    log_info "Next: run './scripts/deploy-fly-test.sh secrets'"
}

cmd_secrets() {
    log_warn "IMPORTANT: You need an OpenAI API key to proceed."
    echo "Your OPENAI_API_KEY will be stored securely in Fly.io secrets."
    echo ""

    read -p "Enter your OPENAI_API_KEY: " -r OPENAI_API_KEY

    if [ -z "$OPENAI_API_KEY" ]; then
        log_error "API key cannot be empty"
        exit 1
    fi

    log_info "Setting OPENAI_API_KEY secret..."
    flyctl secrets set OPENAI_API_KEY="$OPENAI_API_KEY" --app "$APP_NAME"

    log_info "Verifying secret is set (value hidden for security)..."
    flyctl secrets list --app "$APP_NAME"

    log_info "Next: run './scripts/deploy-fly-test.sh deploy'"
}

cmd_deploy() {
    log_info "Deploying $APP_NAME to Fly.io..."
    log_warn "This will take 5-10 minutes. Grab coffee!"

    flyctl deploy \
        --config "$CONFIG_FILE" \
        --app "$APP_NAME" \
        --wait-timeout 300

    log_info "Deployment complete! Next: run './scripts/deploy-fly-test.sh status'"
}

cmd_status() {
    log_info "Status of $APP_NAME:"
    flyctl status --app "$APP_NAME"
}

cmd_logs() {
    log_info "Recent logs for $APP_NAME (last 50 lines):"
    flyctl logs --app "$APP_NAME" --lines 50
}

cmd_shell() {
    log_info "Opening SSH console for $APP_NAME..."
    log_warn "Type 'exit' to disconnect"
    flyctl ssh console --app "$APP_NAME"
}

cmd_destroy() {
    log_warn "DANGER: About to delete app and ALL associated data!"
    read -p "Type '$APP_NAME' to confirm deletion: " -r confirm

    if [ "$confirm" != "$APP_NAME" ]; then
        log_info "Deletion cancelled"
        exit 0
    fi

    log_info "Deleting app $APP_NAME..."
    flyctl apps destroy "$APP_NAME"

    log_warn "App deleted. Volumes still exist for recovery if needed."
    log_warn "To delete volumes too: flyctl volumes destroy [volume-id]"
}

# Main
check_flyctl
check_authenticated

case "${1:-full}" in
    launch)
        cmd_launch
        ;;
    volumes)
        cmd_volumes
        ;;
    secrets)
        cmd_secrets
        ;;
    deploy)
        cmd_deploy
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    shell)
        cmd_shell
        ;;
    destroy)
        cmd_destroy
        ;;
    full)
        log_info "Starting full setup for rag-memory-test deployment..."
        cmd_launch
        echo ""
        log_warn "Before proceeding, go to Fly.io dashboard and verify app was created."
        read -p "Press Enter when ready to create volumes..."
        cmd_volumes
        echo ""
        cmd_secrets
        echo ""
        cmd_deploy
        echo ""
        log_info "Deployment complete! Run: ./scripts/deploy-fly-test.sh status"
        ;;
    *)
        log_error "Unknown command: $1"
        echo ""
        echo "Usage: $0 [command]"
        echo "Commands:"
        echo "  launch    - Create new test app"
        echo "  volumes   - Create required volumes"
        echo "  secrets   - Set OPENAI_API_KEY"
        echo "  deploy    - Deploy to Fly.io"
        echo "  status    - Check app status"
        echo "  logs      - View recent logs"
        echo "  shell     - SSH into container"
        echo "  destroy   - Delete test app (careful!)"
        echo ""
        echo "Or run without arguments for full interactive setup"
        exit 1
        ;;
esac
