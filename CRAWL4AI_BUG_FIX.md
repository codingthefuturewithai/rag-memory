# Crawl4AI Bug Fix - BFS Strategy Break Statement

## Bug Description

**Issue:** When using `max_pages` limit in BFS deep crawl strategy with streaming mode, the final page is not yielded before the generator exits.

**Root Cause:** The `break` statement executes BEFORE the `yield result` statement, causing the async generator to exit without yielding the final page.

**Impact:** When crawling with `max_pages=3`, only 2 pages are ingested. The 3rd page is crawled successfully but never yielded to the caller.

---

## File to Modify

**File:** `crawl4ai/deep_crawling/bfs_strategy.py`

**Method:** `_arun_stream()` (async generator for streaming mode)

---

## Exact Code Changes

### Location in File

Lines **232-250** in the async for loop within `_arun_stream()` method.

### BEFORE (Buggy Code)

```python
# Count only successful crawls
if result.success:
    self._pages_crawled += 1

results_count += 1

# Check if we've reached the limit during batch processing
if result.success:
    if self._pages_crawled >= self.max_pages:
        self.logger.info(f"Max pages limit ({self.max_pages}) reached during batch, stopping crawl")
        break  # Exit the generator

yield result
```

### AFTER (Fixed Code)

```python
# Count only successful crawls
if result.success:
    self._pages_crawled += 1

results_count += 1
yield result  # ← MOVED BEFORE BREAK

# Check if we've reached the limit during batch processing
if result.success:
    if self._pages_crawled >= self.max_pages:
        self.logger.info(f"Max pages limit ({self.max_pages}) reached during batch, stopping crawl")
        break  # Exit the generator
```

---

## Full Context (Lines 224-250)

For complete context, here's the full section with the fix applied:

```python
async for result in stream_gen:
    url = result.url
    depth = depths.get(url, 0)
    result.metadata = result.metadata or {}
    result.metadata["depth"] = depth
    parent_url = next((parent for (u, parent) in current_level if u == url), None)
    result.metadata["parent_url"] = parent_url

    # Count only successful crawls
    if result.success:
        self._pages_crawled += 1

    results_count += 1
    yield result  # ← CRITICAL: Must yield BEFORE break

    # Check if we've reached the limit during batch processing
    if result.success:
        if self._pages_crawled >= self.max_pages:
            self.logger.info(f"Max pages limit ({self.max_pages}) reached during batch, stopping crawl")
            break  # Exit the generator

    # Only discover links from successful crawls
    if result.success:
        # Link discovery will handle the max pages limit internally
        await self.link_discovery(result, url, depth, visited, next_level, depths)
```

---

## Verification

After applying the fix, a `max_pages=3` crawl should:

1. Crawl all 3 pages successfully
2. Yield all 3 results to the caller
3. Ingest all 3 pages into the database
4. Log message: "Max pages limit (3) reached during batch, stopping crawl" AFTER yielding page 3

Before the fix, only 2 pages were yielded (page 3 was crawled but not returned).

---

## How to Apply to Crawl4AI Fork

1. Fork the Crawl4AI repository
2. Navigate to: `crawl4ai/deep_crawling/bfs_strategy.py`
3. Find the `_arun_stream()` method
4. Locate lines 232-250 (the async for loop processing stream results)
5. Move the `yield result` line to BEFORE the break statement check
6. Ensure the final code matches the "AFTER" section above
7. Test with a 3-page crawl to verify all 3 pages are yielded

---

## Additional Notes

- This bug ONLY affects streaming mode (`_arun_stream`)
- Batch mode (`_arun_batch`) does not have this issue
- The fix is a simple one-line move - no logic changes needed
- The break statement correctly exits the generator, but must happen AFTER yielding the final result
