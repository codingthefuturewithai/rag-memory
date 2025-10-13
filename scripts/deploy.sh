#!/bin/bash
# Fly.io Deployment Script for RAG Memory MCP Server
#
# Usage:
#   ./scripts/deploy.sh              # Deploy to Fly.io
#   ./scripts/deploy.sh logs         # View logs
#   ./scripts/deploy.sh status       # Check deployment status
#   ./scripts/deploy.sh secrets      # List secrets (no values shown)
#   ./scripts/deploy.sh restart      # Restart the app
#   ./scripts/deploy.sh shell        # SSH into running container

set -e  # Exit on error

APP_NAME="rag-memory-mcp"
FLY_BIN="${HOME}/.fly/bin/flyctl"

# Check if flyctl is installed
if [ ! -f "$FLY_BIN" ]; then
    echo "Error: flyctl not found at $FLY_BIN"
    echo "Install with: curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Get command (default to deploy)
COMMAND="${1:-deploy}"

case "$COMMAND" in
    deploy)
        echo "🚀 Deploying to Fly.io..."
        echo "App: $APP_NAME"
        echo ""
        $FLY_BIN deploy --wait-timeout 300 --app $APP_NAME
        echo ""
        echo "✅ Deployment complete!"
        echo "🔗 URL: https://$APP_NAME.fly.dev/sse"
        ;;

    logs)
        echo "📋 Viewing logs for $APP_NAME..."
        echo "Press Ctrl+C to exit"
        echo ""
        $FLY_BIN logs --app $APP_NAME
        ;;

    status)
        echo "📊 Checking status for $APP_NAME..."
        echo ""
        $FLY_BIN status --app $APP_NAME
        ;;

    secrets)
        echo "🔐 Listing secrets for $APP_NAME..."
        echo "(Values are not shown for security)"
        echo ""
        $FLY_BIN secrets list --app $APP_NAME
        ;;

    restart)
        echo "🔄 Restarting $APP_NAME..."
        $FLY_BIN apps restart $APP_NAME
        echo "✅ Restart complete!"
        ;;

    shell)
        echo "🐚 Connecting to $APP_NAME container..."
        $FLY_BIN ssh console --app $APP_NAME
        ;;

    help|--help|-h)
        echo "Fly.io Deployment Script for RAG Memory MCP Server"
        echo ""
        echo "Usage:"
        echo "  ./scripts/deploy.sh [command]"
        echo ""
        echo "Commands:"
        echo "  deploy      Deploy to Fly.io (default)"
        echo "  logs        View application logs"
        echo "  status      Check deployment status"
        echo "  secrets     List configured secrets"
        echo "  restart     Restart the application"
        echo "  shell       SSH into running container"
        echo "  help        Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./scripts/deploy.sh              # Deploy"
        echo "  ./scripts/deploy.sh logs         # View logs"
        echo "  ./scripts/deploy.sh status       # Check status"
        ;;

    *)
        echo "Error: Unknown command '$COMMAND'"
        echo "Run './scripts/deploy.sh help' for usage information"
        exit 1
        ;;
esac
