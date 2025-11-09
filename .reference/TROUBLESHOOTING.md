# Troubleshooting

Common issues and solutions for RAG Memory.

## Database Connection Issues

### PostgreSQL Connection Refused

**Error:**
```
Could not connect to database
Connection refused at localhost:54320
```

**Causes:**
- Docker container not running
- Wrong port
- Firewall blocking connection

**Solutions:**
```bash
# Check container running
docker ps | grep postgres

# If not running, start it
rag start

# Check logs
docker logs rag-memory-postgres

# Test connection directly
psql postgresql://raguser:ragpassword@localhost:54320/rag_memory

# If port conflict, check what's using 54320
lsof -i :54320
```

### Neo4j Connection Refused

**Error:**
```
Unable to connect to Neo4j at bolt://localhost:7687
```

**Causes:**
- Neo4j container not running
- Wrong credentials
- Network issue

**Solutions:**
```bash
# Check container running
docker ps | grep neo4j

# If not running, start it
rag start

# Check logs
docker logs rag-memory-neo4j

# Test connection
docker exec -it rag-memory-neo4j cypher-shell -u neo4j -p graphiti-password

# Verify environment
echo $NEO4J_PASSWORD
```

### Both Databases Required

**Error:**
```
Server startup failed: Neo4j unavailable
```

**Cause:**
RAG Memory requires both PostgreSQL and Neo4j to be running.

**Solution:**
```bash
# Check both databases
rag status

# Start both
rag start

# Verify both healthy
docker ps | grep -E "postgres|neo4j"
```

## OpenAI API Issues

### Invalid API Key

**Error:**
```
Authentication error: Invalid API key
```

**Causes:**
- API key incorrect
- API key not set
- Environment variable not loaded

**Solutions:**
```bash
# Check config file
grep api_key ~/Library/Application\ Support/rag-memory/config.yaml

# Verify environment (DO NOT run with AI assistants)
# echo $OPENAI_API_KEY

# Update key
rag config set openai.api_key "sk-new-key-here"

# Restart services
rag restart
```

### Rate Limit Exceeded

**Error:**
```
Rate limit exceeded. Please try again in X seconds
```

**Cause:**
Too many API requests in short time.

**Solution:**
```bash
# Wait and retry
# Reduce batch size for large ingestions
# Spread ingestion over time
```

## Docker Issues

### Docker Not Running

**Error:**
```
Cannot connect to Docker daemon
```

**Solution:**
```bash
# macOS: Start Docker Desktop app
# Linux: sudo systemctl start docker
# Windows: Start Docker Desktop

# Verify
docker ps
```

### Port Already in Use

**Error:**
```
Bind for 0.0.0.0:54320 failed: port is already allocated
```

**Cause:**
Another service using port 54320.

**Solutions:**
```bash
# Find what's using port
lsof -i :54320

# Option 1: Stop conflicting service
# Option 2: Change RAG Memory port in docker-compose.yml
```

### Permission Denied

**Error:**
```
Permission denied while trying to connect to Docker daemon
```

**Solution (Linux):**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in
# Or: newgrp docker
```

### Container Won't Start

**Error:**
```
Container rag-memory-postgres exits immediately
```

**Solutions:**
```bash
# Check logs
docker logs rag-memory-postgres

# Remove and recreate
docker-compose down
docker volume prune  # WARNING: Deletes data
docker-compose up -d

# Check disk space
df -h
```

## Ingestion Issues

### Document Already Exists

**Error:**
```
Document with title "guide.md" already exists in collection "tech-docs"
```

**Cause:**
Attempting to ingest duplicate document.

**Solutions:**
```bash
# Option 1: Update existing document
rag document update <id> --content "new content"

# Option 2: Use different title
rag ingest file guide.md --collection tech-docs --title "guide-v2"

# Option 3: Use recrawl mode (for URLs)
rag ingest url https://example.com --mode recrawl
```

### Chunking Errors

**Error:**
```
Failed to chunk document: content too short
```

**Cause:**
Document smaller than chunk size.

**Solution:**
```bash
# Reduce chunk size
rag ingest file small.txt \
  --collection docs \
  --chunk-size 500 \
  --chunk-overlap 100
```

### Web Crawl Timeout

**Error:**
```
Crawl timeout after 60 seconds
```

**Causes:**
- Site too large
- Network slow
- Site blocking requests

**Solutions:**
```bash
# Reduce crawl depth
rag ingest url https://example.com \
  --follow-links \
  --max-depth 1  # Instead of 2 or 3

# Crawl specific section
rag ingest url https://example.com/docs/api \
  --follow-links

# Check site structure first
rag analyze website https://example.com
```

## Search Issues

### No Results Found

**Causes:**
- Collection empty
- Threshold too high
- Query doesn't match content

**Solutions:**
```bash
# Check collection has documents
rag collection info your-collection

# Remove threshold
rag search "query" --collection your-collection

# Lower threshold
rag search "query" --collection your-collection --threshold 0.3

# Try broader query
rag search "general topic" --collection your-collection
```

### Low Similarity Scores

**Causes:**
- Content not related to query
- Query too vague
- Wrong collection

**Solutions:**
```bash
# Make query more specific
rag search "How do I configure X for Y?" --collection docs

# Check correct collection
rag collection list

# Verify content exists
rag document list --collection docs
```

### Unexpected Results

**Causes:**
- Query ambiguous
- Content similar but wrong
- Need threshold adjustment

**Solutions:**
```bash
# Rephrase query more specifically
# Use natural language questions
# Increase threshold for stricter matching

rag search "specific detailed question?" \
  --collection docs \
  --threshold 0.7
```

## MCP Server Issues

### Server Not Showing in Claude Desktop

**Causes:**
- Config file syntax error
- Wrong file path
- MCP server not installed

**Solutions:**
```bash
# Verify config file exists
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Check JSON syntax (no trailing commas, proper quotes)
# Use JSON validator: jsonlint.com

# Verify command exists
which rag-mcp-stdio

# Restart Claude Desktop completely
```

### MCP Tools Not Working

**Causes:**
- Database not connected
- Environment variables missing
- Wrong config

**Solutions:**
```bash
# Check databases running
rag status

# Verify environment in MCP config
# Check config.json has OPENAI_API_KEY and DATABASE_URL

# Test CLI works
rag collection list

# Check MCP logs
cat ~/Library/Logs/Claude/mcp*.log
```

## Collection Issues

### Cannot Delete Collection

**Error:**
```
Collection "tech-docs" has 42 documents. Type collection name to confirm
```

**Cause:**
Safety check requires confirmation.

**Solution:**
```bash
# Follow prompt and type collection name exactly
# This prevents accidental deletion
```

### Collection Not Found

**Error:**
```
Collection "tech-docs" does not exist
```

**Causes:**
- Typo in collection name
- Collection deleted
- Wrong database

**Solutions:**
```bash
# List all collections
rag collection list

# Create if needed
rag collection create tech-docs \
  --description "Technical docs" \
  --domain "Engineering" \
  --domain-scope "Public documentation"
```

## Knowledge Graph Issues

### Graph Extraction Slow

**Cause:**
Entity extraction uses LLM calls which take time (30-60 seconds per document).

**Solution:**
- This is expected behavior
- Not suitable for real-time ingestion
- Consider batch ingestion overnight

### Empty Episodes

**Observation:**
```cypher
MATCH (e:Episode) WHERE NOT (e)--(:Entity) RETURN count(e)
# Returns: 4
```

**Cause:**
Document had no extractable entities or extraction failed.

**Not an error:**
Some documents legitimately have no entities. If many documents show this, check:

```bash
# Check logs
docker logs rag-memory-mcp | grep -i graphiti

# Verify Graphiti models configured
grep graphiti ~/Library/Application\ Support/rag-memory/config.yaml
```

## Performance Issues

### Slow Search

**Causes:**
- Collection very large
- No HNSW index
- Database overloaded

**Solutions:**
```bash
# Verify index exists
psql $DATABASE_URL -c "\d document_chunks"
# Should show hnsw index

# Check database resources
docker stats rag-memory-postgres

# Reduce result count
rag search "query" --limit 5
```

### High Memory Usage

**Cause:**
Large document ingestion or many concurrent operations.

**Solutions:**
```bash
# Check container resources
docker stats

# Increase Docker memory limit (Docker Desktop settings)
# Restart Docker

# Reduce batch sizes for ingestion
```

## Debugging Commands

### Check Service Status

```bash
# Overall status
rag status

# Docker containers
docker ps -a | grep rag-memory

# Database health
psql $DATABASE_URL -c "SELECT 1"
docker exec -it rag-memory-neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD -c "RETURN 1"
```

### View Logs

```bash
# All logs
rag logs

# Specific service
rag logs --service postgres
rag logs --service neo4j
rag logs --service mcp

# Follow logs in real-time
rag logs --service mcp --follow

# Export logs for support
rag logs --export-all diagnostics.tar.gz
```

### Database Queries

**PostgreSQL:**
```bash
# Connect
psql $DATABASE_URL

# Count documents
SELECT COUNT(*) FROM source_documents;

# Count chunks
SELECT COUNT(*) FROM document_chunks;

# Check collections
SELECT name, description FROM collections;
```

**Neo4j:**
```bash
# Connect
docker exec -it rag-memory-neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD

# Count episodes
MATCH (e:Episode) RETURN count(e);

# Count entities
MATCH (n:Entity) RETURN count(n);

# Check relationships
MATCH ()-[r]-() RETURN count(r);
```

## Getting Help

If issue not resolved:

1. **Export logs:**
   ```bash
   rag logs --export-all support-request.tar.gz
   ```

2. **Gather information:**
   - RAG Memory version: `rag --version`
   - OS and version
   - Docker version: `docker --version`
   - Error message (full text)
   - Steps to reproduce

3. **Check existing issues:**
   - GitHub Issues
   - Documentation

4. **Create bug report:**
   - Include logs export
   - Provide reproduction steps
   - Describe expected vs actual behavior

## Next Steps

- **Installation** - See INSTALLATION.md for setup
- **Configuration** - See CONFIGURATION.md for settings
- **CLI Guide** - See CLI_GUIDE.md for commands
- **MCP Guide** - See MCP_GUIDE.md for agent setup
