#!/bin/bash

# RAG Memory - Environment Setup Script
# Usage: source scripts/set-env.sh [dev|test|prod] or source scripts/set-env.sh reset

set_environment() {
    local env_name="$1"
    local env_file=".env.${env_name}"

    # Check if file exists
    if [ ! -f "$env_file" ]; then
        echo "❌ Error: $env_file not found"
        return 1
    fi

    # Source the file and export variables
    set -a
    source "$env_file"
    set +a

    # Extract critical variables for verification
    local db_url="$DATABASE_URL"
    local api_key="${OPENAI_API_KEY:0:20}..."
    local neo4j_uri="$NEO4J_URI"
    local env_display="${ENV_NAME:-$env_name}"

    # Verify key variables are set
    if [ -z "$DATABASE_URL" ] || [ -z "$OPENAI_API_KEY" ]; then
        echo "❌ Error: Critical variables not set after loading $env_file"
        unset DATABASE_URL OPENAI_API_KEY NEO4J_URI NEO4J_USER NEO4J_PASSWORD
        return 1
    fi

    echo "✅ Environment loaded: $env_display"
    echo "   DATABASE_URL: $db_url"
    echo "   OPENAI_API_KEY: $api_key"
    [ -n "$neo4j_uri" ] && echo "   NEO4J_URI: $neo4j_uri"

    return 0
}

reset_environment() {
    unset DATABASE_URL OPENAI_API_KEY NEO4J_URI NEO4J_USER NEO4J_PASSWORD
    unset DEV_POSTGRES_PORT DEV_NEO4J_HTTP_PORT DEV_NEO4J_BOLT_PORT
    unset POSTGRES_HOST POSTGRES_PORT POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB
    unset ENV_NAME ENVIRONMENT
    echo "✅ Environment variables cleared"
    return 0
}

# Main logic
case "$1" in
    dev|test|prod)
        set_environment "$1"
        ;;
    reset)
        reset_environment
        ;;
    "")
        echo "Usage: source scripts/set-env.sh [dev|test|prod|reset]"
        echo ""
        echo "Examples:"
        echo "  source scripts/set-env.sh dev     # Load development environment"
        echo "  source scripts/set-env.sh test    # Load test environment"
        echo "  source scripts/set-env.sh prod    # Load production environment"
        echo "  source scripts/set-env.sh reset   # Clear all RAG environment variables"
        return 1
        ;;
    *)
        echo "❌ Error: Unknown environment '$1'"
        echo "Valid options: dev, test, prod, reset"
        return 1
        ;;
esac
