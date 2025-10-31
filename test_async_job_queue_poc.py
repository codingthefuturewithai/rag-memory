#!/usr/bin/env python3
"""
Proof of Concept: Async Job Queue for MCP Server
Tests if background asyncio tasks continue after client disconnect on Windows/Mac/Linux

This mimics EXACTLY how an MCP server handles requests:
1. FastAPI/uvicorn receives HTTP request
2. MCP tool returns response immediately
3. Client disconnects (connection closes)
4. Background asyncio task continues processing

Run this on Windows/Mac/Linux to verify it works reliably.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# ============================================================================
# JOB QUEUE (In-memory tracking)
# ============================================================================

_jobs: Dict[str, dict] = {}
_job_counter = 0


def create_job(operation: str, params: dict) -> str:
    """Create a new job and return job_id"""
    global _job_counter
    _job_counter += 1
    job_id = f"job_{_job_counter}"

    _jobs[job_id] = {
        "job_id": job_id,
        "operation": operation,
        "params": params,
        "status": "queued",
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None
    }

    print(f"[SERVER] Created {job_id} for {operation}")
    return job_id


def get_job_status(job_id: str) -> dict:
    """Get job status"""
    return _jobs.get(job_id, {"error": "Job not found"})


# ============================================================================
# BACKGROUND WORKER (Simulates long-running ingestion)
# ============================================================================

async def _process_job(job_id: str, sleep_seconds: int):
    """
    Background task that processes a job.

    This simulates what happens during ingest_text/ingest_url:
    - Chunking documents
    - Generating embeddings (OpenAI API calls)
    - Knowledge graph extraction

    Critical test: Does this continue running after client disconnects?
    """
    job = _jobs[job_id]

    try:
        # Mark as started
        job["status"] = "processing"
        job["started_at"] = datetime.now().isoformat()
        print(f"[WORKER] Started {job_id} (will take {sleep_seconds}s)")

        # Simulate long-running work (like graph extraction)
        # This is where the client would timeout and disconnect
        await asyncio.sleep(sleep_seconds)

        # Mark as complete
        job["status"] = "completed"
        job["completed_at"] = datetime.now().isoformat()
        job["result"] = {
            "message": f"Successfully processed after {sleep_seconds}s",
            "processed_at": datetime.now().isoformat()
        }
        print(f"[WORKER] ✅ Completed {job_id} successfully!")

    except Exception as e:
        job["status"] = "failed"
        job["completed_at"] = datetime.now().isoformat()
        job["error"] = str(e)
        print(f"[WORKER] ❌ Failed {job_id}: {e}")


# ============================================================================
# FASTAPI SERVER (Mimics MCP Server)
# ============================================================================

app = FastAPI()


@app.post("/ingest")
async def ingest_endpoint(sleep_seconds: int = 90):
    """
    Mimics MCP ingest tool behavior:
    1. Receives request
    2. Creates job
    3. Starts background task
    4. Returns immediately (client gets response)
    5. Client disconnects
    6. Background task continues (critical test!)

    Args:
        sleep_seconds: How long the background job takes (default: 90s to exceed typical 60s timeout)
    """
    # Create job
    job_id = create_job("ingest", {"sleep_seconds": sleep_seconds})

    # Start background task (non-blocking)
    # This is the CRITICAL part - does it continue after client disconnect?
    asyncio.create_task(_process_job(job_id, sleep_seconds))

    # Return immediately (client receives this in <1 second)
    print(f"[SERVER] Returning response to client for {job_id}")
    return JSONResponse({
        "job_id": job_id,
        "status": "started",
        "message": f"Job started. Will take ~{sleep_seconds} seconds.",
        "check_status_url": f"/status/{job_id}"
    })


@app.get("/status/{job_id}")
async def status_endpoint(job_id: str):
    """Check job status - mimics check_ingestion_status tool"""
    job = get_job_status(job_id)
    print(f"[SERVER] Status check for {job_id}: {job.get('status', 'not_found')}")
    return JSONResponse(job)


@app.get("/jobs")
async def list_jobs():
    """List all jobs (for debugging)"""
    return JSONResponse({
        "total_jobs": len(_jobs),
        "jobs": list(_jobs.values())
    })


# ============================================================================
# CLIENT SIMULATOR (Mimics MCP Client with 60s timeout)
# ============================================================================

async def simulate_client_with_timeout():
    """
    Simulates an MCP client (like ChatGPT) with a 60-second timeout.

    1. Submits job (takes 90s)
    2. Waits 10 seconds
    3. "Times out" and disconnects
    4. Checks status later to see if job completed
    """
    import httpx

    print("\n" + "="*80)
    print("CLIENT SIMULATION: MCP client with short timeout")
    print("="*80 + "\n")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Submit job that takes 90 seconds (will exceed client's 10s timeout)
            print("[CLIENT] Submitting ingest job (will take 90s)...")
            response = await client.post("http://localhost:8765/ingest?sleep_seconds=90")
            data = response.json()
            job_id = data["job_id"]

            print(f"[CLIENT] ✅ Got response: {data}")
            print(f"[CLIENT] Job ID: {job_id}")

            # Simulate client "waiting" then timing out
            print(f"[CLIENT] Waiting 10 seconds, then 'timing out' (closing connection)...")
            await asyncio.sleep(10)
            print(f"[CLIENT] ❌ Connection timeout! Disconnecting...")

        except Exception as e:
            print(f"[CLIENT] ❌ Error: {e}")
            job_id = "job_1"  # Assume first job

    # Client has now "disconnected"
    print(f"[CLIENT] Connection closed. But background job should still be running on server!")

    # Wait for job to complete (90s total - 10s already passed = 80s remaining)
    print(f"[CLIENT] Waiting 85 more seconds for background job to complete...")
    await asyncio.sleep(85)

    # Check if job completed despite client disconnect
    print(f"\n[CLIENT] Checking job status after 'disconnect'...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8765/status/{job_id}")
        status = response.json()

        print(f"[CLIENT] Status check result:")
        print(f"  - Status: {status.get('status')}")
        print(f"  - Started: {status.get('started_at')}")
        print(f"  - Completed: {status.get('completed_at')}")
        print(f"  - Result: {status.get('result')}")

        if status.get('status') == 'completed':
            print(f"\n✅ SUCCESS! Background job completed despite client disconnect!")
            print(f"   This proves asyncio.create_task() works reliably for job queue.")
            return True
        else:
            print(f"\n❌ FAILED! Background job did not complete.")
            print(f"   Status: {status.get('status')}")
            print(f"   This means job queue approach is NOT reliable on this platform.")
            return False


# ============================================================================
# TEST RUNNER
# ============================================================================

async def run_test():
    """Run the full test"""
    print("\n" + "="*80)
    print("ASYNC JOB QUEUE POC - Testing Background Task Reliability")
    print("="*80)
    print(f"Platform: {import_platform_info()}")
    print(f"Testing if asyncio.create_task() continues after client disconnect")
    print("="*80 + "\n")

    # Start server in background
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
    server = uvicorn.Server(config)

    # Run server and client concurrently
    async with asyncio.TaskGroup() as tg:
        # Start server
        server_task = tg.create_task(server.serve())

        # Wait for server to start
        await asyncio.sleep(2)

        # Run client test
        client_task = tg.create_task(simulate_client_with_timeout())


def import_platform_info():
    """Get platform information"""
    import platform
    import sys
    return f"{platform.system()} {platform.release()} (Python {sys.version.split()[0]})"


# ============================================================================
# SIMPLE STANDALONE TEST (Alternative - no httpx needed)
# ============================================================================

async def simple_standalone_test():
    """
    Simplified test without HTTP layer.
    Tests just the asyncio.create_task() behavior.
    """
    print("\n" + "="*80)
    print("SIMPLE STANDALONE TEST - No HTTP, just asyncio")
    print("="*80 + "\n")

    job_id = create_job("test", {"duration": 10})

    # Start background task
    print(f"[TEST] Starting background task for {job_id}...")
    asyncio.create_task(_process_job(job_id, 10))

    # Return immediately (simulates client getting response)
    print(f"[TEST] 'Returning' to client immediately...")
    await asyncio.sleep(1)

    print(f"[TEST] Client would disconnect here. Waiting 12s to see if job completes...")
    await asyncio.sleep(12)

    # Check status
    status = get_job_status(job_id)
    print(f"\n[TEST] Final status: {status['status']}")

    if status['status'] == 'completed':
        print("✅ SUCCESS! Background task completed.")
        return True
    else:
        print("❌ FAILED! Background task did not complete.")
        return False


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    print("\n" + "="*80)
    print("ASYNC JOB QUEUE POC")
    print("="*80)
    print("\nChoose test mode:")
    print("  1. Simple test (no HTTP, just asyncio) - RECOMMENDED")
    print("  2. Full test (HTTP client/server simulation)")
    print()

    choice = input("Enter choice (1 or 2, default=1): ").strip() or "1"

    if choice == "1":
        asyncio.run(simple_standalone_test())
    else:
        try:
            asyncio.run(run_test())
        except KeyboardInterrupt:
            print("\n\nTest interrupted.")
        except Exception as e:
            print(f"\n\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
