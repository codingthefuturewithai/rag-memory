#!/bin/bash

# RAG Memory - Build Script for PyPI (UV-based)
#
# Usage:
#   ./build.sh              # Run tests, then build
#   ./build.sh --skip-tests # Skip tests, build only

# Parse command line arguments
SKIP_TESTS=false
for arg in "$@"; do
    case $arg in
        --skip-tests|-s)
            SKIP_TESTS=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./build.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-tests, -s    Skip running tests before build"
            echo "  --help, -h          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "🚀 Building RAG Memory for PyPI..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV not found! Please install UV first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ UV found: $(uv --version)"

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/
rm -rf dist/
rm -rf *.egg-info/

# Run tests first (unless skipped)
if [ "$SKIP_TESTS" = false ]; then
    echo "🧪 Running tests..."
    uv run pytest tests/ -v
    if [ $? -ne 0 ]; then
        echo "❌ Tests failed! Aborting build."
        exit 1
    fi
else
    echo "⏭️  Skipping tests (--skip-tests flag provided)"
fi

# Build the package using UV
echo "🔨 Building package with UV..."
uv build

# Check the build
echo "✅ Checking build..."
uv tool run twine check dist/*

echo "📋 Build complete! Files created:"
ls -lh dist/

echo ""
echo "🎉 Ready to upload to PyPI!"
echo ""

# Prompt for upload
read -p "Do you want to upload to PyPI now? (yes/no): " response
if [[ "$response" == "yes" || "$response" == "y" ]]; then
    echo "📤 Uploading to PyPI..."
    uv tool run twine upload dist/*
    if [ $? -eq 0 ]; then
        echo "✅ Successfully uploaded to PyPI!"
        
        # Get version from pyproject.toml
        VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
        
        # Offer to tag the release
        echo ""
        read -p "Do you want to tag this release as v${VERSION}? (yes/no): " tag_response
        if [[ "$tag_response" == "yes" || "$tag_response" == "y" ]]; then
            git tag "v${VERSION}"
            echo "✅ Tagged as v${VERSION}"

            # Check if we have a remote
            if git remote get-url origin &> /dev/null; then
                read -p "Do you want to push commits and tags to GitHub? (yes/no): " push_response
                if [[ "$push_response" == "yes" || "$push_response" == "y" ]]; then
                    git push origin main
                    git push origin "v${VERSION}"
                    echo "✅ Commits and tag pushed to GitHub!"
                fi
            else
                echo "⚠️  No git remote configured. Skipping push."
            fi
        fi
    else
        echo "❌ Upload failed. Check your credentials and network connection."
        exit 1
    fi
else
    echo "⏭️  Skipping upload."
    echo "To upload later, run:"
    echo "  uv tool run twine upload dist/*"
    echo ""
    echo "Or just run this script again!"
fi
