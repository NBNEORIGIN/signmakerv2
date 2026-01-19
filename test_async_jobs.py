#!/usr/bin/env python3
"""
Test script for async job system.
Tests the complete flow: enqueue -> worker processes -> check status.
"""

import json
import time
import requests
from pathlib import Path

BASE_URL = "http://localhost:5000"

def test_async_job_flow():
    """Test the complete async job flow."""
    print("=" * 60)
    print("Testing Async Job System")
    print("=" * 60)
    print()
    
    # Step 1: Enqueue a job
    print("Step 1: Enqueueing job via API...")
    payload = {
        'theme': 'Test theme for async job',
        'use_cases': 'Testing, Development'
    }
    
    response = requests.post(f"{BASE_URL}/api/run/content", params=payload)
    
    if response.status_code == 202:
        # Async mode
        data = response.json()
        print(f"✓ Job enqueued successfully (async mode)")
        print(f"  Job ID: {data['jobId']}")
        print(f"  Status URL: {data['statusUrl']}")
        job_id = data['jobId']
    elif response.status_code == 200:
        # Sync mode
        print("⚠ Running in synchronous mode (ASYNC_JOBS_ENABLED=false)")
        print("  To test async mode, set environment variables:")
        print("    ASYNC_JOBS_ENABLED=true")
        print("    ASYNC_JOB_TYPES=generate_amazon_content")
        return
    else:
        print(f"✗ Failed to enqueue job: {response.status_code}")
        print(f"  Response: {response.text}")
        return
    
    print()
    
    # Step 2: Check job status
    print("Step 2: Checking job status...")
    max_wait = 300  # 5 minutes
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        response = requests.get(f"{BASE_URL}/api/jobs/{job_id}")
        
        if response.status_code != 200:
            print(f"✗ Failed to get job status: {response.status_code}")
            break
        
        job = response.json()
        status = job['status']
        
        print(f"  Status: {status}", end="")
        
        if job.get('progress'):
            progress = job['progress']
            if isinstance(progress, dict):
                stage = progress.get('stage', '')
                print(f" - {stage}", end="")
        
        print()
        
        if status == 'succeeded':
            print()
            print("✓ Job completed successfully!")
            print(f"  Duration: {job.get('result', {}).get('duration_seconds', 'N/A')}s")
            print(f"  Products processed: {job.get('result', {}).get('products_processed', 'N/A')}")
            print(f"  Images uploaded: {job.get('result', {}).get('images_uploaded', 'N/A')}")
            print(f"  Flatfile: {job.get('result', {}).get('flatfile_path', 'N/A')}")
            break
        
        elif status == 'failed':
            print()
            print("✗ Job failed!")
            print(f"  Error: {job.get('error', 'Unknown error')}")
            print(f"  Attempts: {job.get('attempts', 0)}/{job.get('max_attempts', 3)}")
            break
        
        elif status in ['queued', 'running']:
            time.sleep(5)  # Poll every 5 seconds
        
        else:
            print(f"  Unknown status: {status}")
            break
    
    else:
        print()
        print(f"⚠ Job did not complete within {max_wait}s")
    
    print()
    
    # Step 3: Get job statistics
    print("Step 3: Getting job queue statistics...")
    response = requests.get(f"{BASE_URL}/api/jobs/stats")
    
    if response.status_code == 200:
        stats = response.json()
        print(f"  Queued: {stats['queued']}")
        print(f"  Running: {stats['running']}")
        print(f"  Succeeded: {stats['succeeded']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Total: {stats['total']}")
    else:
        print(f"✗ Failed to get stats: {response.status_code}")
    
    print()
    print("=" * 60)
    print("Test complete")
    print("=" * 60)


def test_job_api_endpoints():
    """Test job API endpoints directly."""
    print("=" * 60)
    print("Testing Job API Endpoints")
    print("=" * 60)
    print()
    
    # Test listing jobs
    print("1. List all jobs...")
    response = requests.get(f"{BASE_URL}/api/jobs")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Found {data['count']} jobs")
    else:
        print(f"   ✗ Failed: {response.status_code}")
    
    print()
    
    # Test filtering by status
    print("2. List queued jobs...")
    response = requests.get(f"{BASE_URL}/api/jobs?status=queued")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Found {data['count']} queued jobs")
    else:
        print(f"   ✗ Failed: {response.status_code}")
    
    print()
    
    # Test stats endpoint
    print("3. Get job statistics...")
    response = requests.get(f"{BASE_URL}/api/jobs/stats")
    if response.status_code == 200:
        stats = response.json()
        print(f"   ✓ Stats retrieved: {stats}")
    else:
        print(f"   ✗ Failed: {response.status_code}")
    
    print()
    print("=" * 60)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'api':
        test_job_api_endpoints()
    else:
        test_async_job_flow()
