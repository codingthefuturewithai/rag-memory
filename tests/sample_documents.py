"""Sample documents for testing similarity search."""

# Test cases with expected similarity ranges
HIGH_SIMILARITY_TESTS = [
    {
        "name": "PostgreSQL Database Query",
        "document": "PostgreSQL is a powerful open-source relational database management system that supports advanced data types and performance optimization features.",
        "query": "What is PostgreSQL and what type of database is it?",
        "expected_min": 0.75,
        "expected_max": 0.95,
        "description": "Nearly identical semantic meaning - should score very high",
    },
    {
        "name": "Python Programming Language",
        "document": "Python is a high-level programming language known for its simplicity, readability, and extensive use in web development, data science, and automation.",
        "query": "Tell me about the Python programming language",
        "expected_min": 0.75,
        "expected_max": 0.95,
        "description": "Direct match on topic - should score very high",
    },
]

MEDIUM_SIMILARITY_TESTS = [
    {
        "name": "Python to Machine Learning",
        "document": "Python is a popular programming language widely used for data science, machine learning, artificial intelligence, and scientific computing.",
        "query": "What are the best tools for machine learning?",
        "expected_min": 0.50,
        "expected_max": 0.75,
        "description": "Related but not identical - mentions ML but query asks about tools",
    },
    {
        "name": "Database to Performance",
        "document": "Databases provide persistent storage for application data with features like transactions, indexing, and query optimization.",
        "query": "How can I improve application performance?",
        "expected_min": 0.45,
        "expected_max": 0.70,
        "description": "Related concepts - database performance is one aspect of app performance",
    },
]

LOW_SIMILARITY_TESTS = [
    {
        "name": "Weather to Database",
        "document": "The weather today is sunny and warm with clear blue skies and a gentle breeze.",
        "query": "How do I configure a database server?",
        "expected_min": 0.05,
        "expected_max": 0.40,
        "description": "Completely unrelated topics - should score very low",
    },
    {
        "name": "Cooking to Programming",
        "document": "To make a delicious pasta dish, boil water, add salt, cook pasta for 10 minutes, and drain.",
        "query": "How do I write a function in Python?",
        "expected_min": 0.05,
        "expected_max": 0.40,
        "description": "Completely unrelated topics - should score very low",
    },
]

# Technical documents for realistic testing
TECHNICAL_DOCUMENTS = [
    {
        "content": "Vector databases use embeddings to represent data as high-dimensional vectors, enabling semantic search through similarity calculations like cosine distance.",
        "metadata": {"category": "database", "topic": "vector-search"},
    },
    {
        "content": "HNSW (Hierarchical Navigable Small World) is a graph-based algorithm for approximate nearest neighbor search that provides excellent recall with fast query times.",
        "metadata": {"category": "algorithms", "topic": "search"},
    },
    {
        "content": "Normalizing vectors to unit length is critical for accurate cosine similarity calculations in RAG systems, preventing artificially low similarity scores.",
        "metadata": {"category": "machine-learning", "topic": "embeddings"},
    },
    {
        "content": "PostgreSQL's pgvector extension enables storing and querying vector embeddings directly in the database, supporting both exact and approximate nearest neighbor search.",
        "metadata": {"category": "database", "topic": "postgresql"},
    },
    {
        "content": "RAG (Retrieval-Augmented Generation) combines information retrieval with language models to generate responses grounded in relevant context from a knowledge base.",
        "metadata": {"category": "ai", "topic": "rag"},
    },
    {
        "content": "OpenAI's text-embedding-3-small model produces 1536-dimensional embeddings optimized for semantic similarity at a cost of $0.02 per million tokens.",
        "metadata": {"category": "ai", "topic": "embeddings"},
    },
    {
        "content": "Cosine similarity measures the angle between vectors, with scores ranging from -1 to 1, where 1 indicates identical direction and 0 indicates orthogonality.",
        "metadata": {"category": "mathematics", "topic": "similarity"},
    },
    {
        "content": "Docker Compose simplifies multi-container applications by defining services, networks, and volumes in a single YAML configuration file.",
        "metadata": {"category": "devops", "topic": "docker"},
    },
]

# Queries for testing technical documents
TECHNICAL_QUERIES = [
    {
        "query": "How does vector search work in databases?",
        "expected_top_docs": [0, 3],  # Vector databases and pgvector docs
        "min_similarity": 0.65,
    },
    {
        "query": "What is the importance of vector normalization?",
        "expected_top_docs": [2],  # Normalization doc
        "min_similarity": 0.70,
    },
    {
        "query": "Tell me about RAG systems and how they work",
        "expected_top_docs": [4],  # RAG doc
        "min_similarity": 0.75,
    },
    {
        "query": "Which embedding model should I use for cost-effective semantic search?",
        "expected_top_docs": [5],  # OpenAI embeddings doc
        "min_similarity": 0.60,
    },
]


def get_all_test_cases():
    """Get all test cases organized by expected similarity."""
    return {
        "high": HIGH_SIMILARITY_TESTS,
        "medium": MEDIUM_SIMILARITY_TESTS,
        "low": LOW_SIMILARITY_TESTS,
    }


def get_technical_test_data():
    """Get technical documents and queries for realistic testing."""
    return {
        "documents": TECHNICAL_DOCUMENTS,
        "queries": TECHNICAL_QUERIES,
    }
