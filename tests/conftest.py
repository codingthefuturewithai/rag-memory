"""Pytest configuration and fixtures.

This file is automatically loaded by pytest before running tests.
It ensures environment variables are loaded from ~/.rag-memory-env
before any test code runs.
"""

from src.core.config_loader import load_environment_variables


# Load environment variables from ~/.rag-memory-env before tests run
# This ensures DATABASE_URL and OPENAI_API_KEY are available to all tests
load_environment_variables()
