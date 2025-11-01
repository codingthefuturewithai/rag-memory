"""
Test ingest_url with follow_links=True via MCP client against Docker container.
This tests the full end-to-end flow: analyze_website -> ingest_url.
"""
import asyncio
import json
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Test ingest_url with follow_links against containerized MCP server."""

    # Connect to MCP server running in Docker on port 8001
    server_params = StdioServerParameters(
        command="curl",
        args=[
            "-N",  # No buffering
            "-H", "Accept: text/event-stream",
            "http://localhost:8001/sse"
        ],
    )

    logger.info("="*80)
    logger.info("Testing MCP ingest_url with follow_links=True (Docker container)")
    logger.info("="*80)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Step 1: List collections to find test collection
            logger.info("\nStep 1: Listing collections...")
            result = await session.call_tool("list_collections", {})
            collections_text = result.content[0].text if result.content else "{}"
            collections_data = json.loads(collections_text)
            logger.info(f"Found {len(collections_data)} collections")

            # Use existing test collection or create new one
            collection_name = "test_crawl_docker"
            collection_exists = any(c['name'] == collection_name for c in collections_data)

            if not collection_exists:
                logger.info(f"\nCreating collection: {collection_name}")
                create_result = await session.call_tool("create_collection", {
                    "name": collection_name,
                    "description": "Test collection for Docker crawler testing",
                    "domain": "Testing",
                    "domain_scope": "Docker integration testing"
                })
                logger.info("Collection created")

            # Step 2: Analyze website
            logger.info("\nStep 2: Analyzing website...")
            analyze_result = await session.call_tool("analyze_website", {
                "base_url": "https://docs.python.org"
            })

            analyze_text = analyze_result.content[0].text if analyze_result.content else "{}"
            analyze_data = json.loads(analyze_text)
            analysis_token = analyze_data.get("analysis_token")

            logger.info(f"Analysis complete: {analyze_data.get('total_urls', 0)} URLs found")
            logger.info(f"Analysis token: {analysis_token[:20]}...")

            # Step 3: Ingest with follow_links=True
            logger.info("\nStep 3: Ingesting URL with follow_links=True, max_pages=5...")
            logger.info("This will take several minutes - crawler is running in Docker...")

            ingest_result = await session.call_tool("ingest_url", {
                "url": "https://docs.python.org/3/tutorial/",
                "collection_name": collection_name,
                "follow_links": True,
                "max_pages": 5,
                "analysis_token": analysis_token,
                "mode": "crawl",
                "include_document_ids": True
            })

            ingest_text = ingest_result.content[0].text if ingest_result.content else "{}"
            ingest_data = json.loads(ingest_text)

            logger.info("="*80)
            logger.info("✅ INGEST COMPLETED")
            logger.info("="*80)
            logger.info(f"Pages crawled: {ingest_data.get('pages_crawled', 0)}")
            logger.info(f"Pages ingested: {ingest_data.get('pages_ingested', 0)}")
            logger.info(f"Total chunks: {ingest_data.get('total_chunks', 0)}")
            logger.info(f"Document IDs: {len(ingest_data.get('document_ids', []))}")

            if ingest_data.get('pages_crawled', 0) >= 2:
                logger.info("\n✅ SUCCESS: Multi-page crawl with follow_links=True works in Docker!")
            else:
                logger.error("\n❌ FAILURE: Expected at least 2 pages crawled")

            return ingest_data


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\n\nFINAL RESULT:")
    print(json.dumps(result, indent=2))
