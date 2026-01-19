# Async Job Queue System - Implementation Guide

## Overview

This document describes the async job queue system added to the Amazon Publisher web application. The system allows long-running workflows (like Amazon content generation) to run asynchronously in a background worker process, preventing timeouts and improving user experience.

## Architecture

### Components

1. **Job Queue (`jobs.py`)**: SQLite-based job queue with atomic job claiming
2. **Workflow Module (`workflows/amazon_content.py`)**: Extracted workflow logic that can run sync or async
3. **Job API (`api_jobs.py`)**: REST API endpoints for job management
4. **Worker Process (`worker.py`)**: Background process that executes queued jobs
5. **Modified Web App (`publisher_web.py`)**: Updated to support async mode via feature flags

### Design Principles

- **Non-breaking**: Existing synchronous behavior remains default
- **Feature-flagged**: Async mode enabled via environment variables
- **Idempotent**: Jobs can be safely retried
- **Observable**: Progress tracking and status endpoints
- **Resource-safe**: Concurrency limits prevent OOM

## Quick Start

### 1. Enable Async Mode

Add to your environment (or `config.bat`):

```batch
set ASYNC_JOBS_ENABLED=true
set ASYNC_JOB_TYPES=generate_amazon_content
```

### 2. Start the Web App

```batch
PUBLISHER_WEB.bat
```

The web app will run as normal, but now supports async job enqueueing.

### 3. Start the Worker

In a **separate terminal/command prompt**:

```batch
run_worker.bat
```

The worker will continuously poll for jobs and process them.

### 4. Test the System

```batch
python test_async_jobs.py
```

Or manually via the web interface:
1. Go to QA Review tab
2. Mark products as approved
3. Click "Finalize All Approved & Generate Content"
4. If async mode is enabled, you'll get a job ID instead of streaming output

## API Endpoints

### Enqueue Job (Modified Endpoint)

**POST** `/api/run/content?theme=...&use_cases=...`

**Behavior:**
- If `ASYNC_JOBS_ENABLED=false`: Runs synchronously (existing behavior)
- If `ASYNC_JOBS_ENABLED=true`: Enqueues job and returns immediately

**Response (Async Mode):**
```json
{
  "mode": "async",
  "jobId": "550e8400-e29b-41d4-a716-446655440000",
  "statusUrl": "/api/jobs/550e8400-e29b-41d4-a716-446655440000",
  "message": "Job queued successfully. Check status at the provided URL."
}
```
Status: `202 Accepted`

### Get Job Status

**GET** `/api/jobs/{job_id}`

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "generate_amazon_content",
  "status": "running",
  "created_at": 1737302400.0,
  "started_at": 1737302405.0,
  "progress": {
    "stage": "uploading_images",
    "data": {
      "completed": 30,
      "total": 60
    }
  },
  "payload": {...},
  "attempts": 1,
  "max_attempts": 3
}
```

**Status Values:**
- `queued`: Waiting for worker
- `running`: Currently being processed
- `succeeded`: Completed successfully
- `failed`: Failed after max retries

### List Jobs

**GET** `/api/jobs?status=queued&type=generate_amazon_content&limit=50`

**Query Parameters:**
- `status`: Filter by status (optional)
- `type`: Filter by job type (optional)
- `limit`: Max results (default: 50)

**Response:**
```json
{
  "jobs": [...],
  "count": 10,
  "filters": {
    "status": "queued",
    "type": "generate_amazon_content",
    "limit": 50
  }
}
```

### Job Statistics

**GET** `/api/jobs/stats`

**Response:**
```json
{
  "queued": 5,
  "running": 2,
  "succeeded": 150,
  "failed": 3,
  "total": 160
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ASYNC_JOBS_ENABLED` | `false` | Enable async job mode |
| `ASYNC_JOB_TYPES` | `""` | Comma-separated list of job types to run async |
| `WORKER_CONCURRENCY` | `1` | Max concurrent jobs per worker (currently only 1 supported) |
| `WORKER_POLL_INTERVAL` | `2` | Seconds between queue polls |
| `WORKER_STALE_JOB_TIMEOUT` | `600` | Seconds before requeuing stale jobs (10 min) |

### Example Configuration

```batch
REM Enable async mode for Amazon content generation only
set ASYNC_JOBS_ENABLED=true
set ASYNC_JOB_TYPES=generate_amazon_content

REM Worker settings
set WORKER_CONCURRENCY=1
set WORKER_POLL_INTERVAL=2
set WORKER_STALE_JOB_TIMEOUT=600
```

## Workflow Details

### Amazon Content Generation Workflow

**Job Type:** `generate_amazon_content`

**Payload:**
```json
{
  "csv_path": "products_approved.csv",
  "output_path": "amazon_flatfile_20260119_1430.xlsx",
  "exports_path": "exports",
  "brand": "NorthByNorthEast",
  "theme": "Delivery boundary signs",
  "use_cases": "Gated communities, private driveways",
  "upload_images": true,
  "qa_filter": "all",
  "m_number": null
}
```

**Progress Stages:**
1. `validating_inputs`
2. `loading_products`
3. `products_loaded`
4. `generating_content`
5. `generating_product_content` (per product)
6. `content_generated`
7. `preparing_image_upload`
8. `uploading_images`
9. `image_upload_progress` (periodic)
10. `images_uploaded`
11. `generating_flatfile`
12. `workflow_completed`

**Result (Success):**
```json
{
  "success": true,
  "flatfile_path": "amazon_flatfile_20260119_1430.xlsx",
  "products_processed": 15,
  "images_uploaded": 60,
  "duration_seconds": 180.5
}
```

**Result (Failure):**
```json
{
  "success": false,
  "error": "ANTHROPIC_API_KEY environment variable not set",
  "duration_seconds": 0.5
}
```

## Job Lifecycle

```
[Enqueued] → [Claimed by Worker] → [Running] → [Succeeded/Failed]
                                        ↓
                                   [Requeued if retries remain]
```

### Retry Logic

- Jobs automatically retry on failure
- Default: 3 attempts maximum
- Exponential backoff not implemented (immediate retry)
- After max attempts, job marked as `failed`

### Stale Job Recovery

- Worker periodically checks for stale jobs (running > 10 minutes)
- Stale jobs are requeued automatically
- Prevents jobs from being stuck if worker crashes

## Database Schema

**File:** `jobs.db` (SQLite)

**Table:** `jobs`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PRIMARY KEY | UUID |
| `type` | TEXT | Job type identifier |
| `status` | TEXT | queued\|running\|succeeded\|failed |
| `created_at` | REAL | Unix timestamp |
| `updated_at` | REAL | Unix timestamp |
| `started_at` | REAL | Unix timestamp (nullable) |
| `finished_at` | REAL | Unix timestamp (nullable) |
| `requested_by` | TEXT | User identifier (nullable) |
| `payload` | TEXT | JSON payload |
| `result` | TEXT | JSON result (nullable) |
| `error` | TEXT | Error message (nullable) |
| `attempts` | INTEGER | Current attempt count |
| `max_attempts` | INTEGER | Maximum retries |
| `progress` | TEXT | JSON progress data (nullable) |
| `worker_id` | TEXT | Worker that claimed job (nullable) |

**Indexes:**
- `idx_jobs_status` on `(status, created_at)`
- `idx_jobs_type` on `(type)`

## Troubleshooting

### Jobs Stay in "Queued" Status

**Cause:** Worker not running or crashed

**Solution:**
1. Check if worker is running: `tasklist | findstr python`
2. Start worker: `run_worker.bat`
3. Check worker logs for errors

### Jobs Fail Immediately

**Cause:** Missing environment variables or configuration

**Solution:**
1. Check worker logs for error messages
2. Verify `config.bat` has all required variables:
   - `ANTHROPIC_API_KEY`
   - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
   - `R2_BUCKET_NAME`, `R2_PUBLIC_URL`
3. Restart worker after fixing config

### "Unknown job type" Error

**Cause:** Job type not implemented in worker

**Solution:**
- Currently only `generate_amazon_content` is supported
- Check job type spelling in `ASYNC_JOB_TYPES`

### Worker Uses Too Much Memory

**Cause:** Image processing or concurrent jobs

**Solution:**
1. Ensure `WORKER_CONCURRENCY=1`
2. Monitor with Task Manager
3. Restart worker periodically if needed

### Database Locked Errors

**Cause:** Multiple workers or high contention

**Solution:**
- Run only one worker instance
- SQLite WAL mode is enabled for better concurrency
- Check for zombie processes: `tasklist | findstr python`

## Testing

### Manual Testing

1. **Enable async mode** (see Quick Start)
2. **Start web app and worker**
3. **Trigger job via UI:**
   - Go to QA Review
   - Approve products
   - Click "Finalize All Approved & Generate Content"
4. **Monitor job:**
   - Note the job ID from response
   - Visit `/api/jobs/{job_id}` in browser
   - Refresh to see progress updates

### Automated Testing

```batch
REM Test complete async flow
python test_async_jobs.py

REM Test API endpoints only
python test_async_jobs.py api
```

### Verify Synchronous Mode Still Works

1. **Disable async mode:**
   ```batch
   set ASYNC_JOBS_ENABLED=false
   ```
2. **Restart web app**
3. **Run pipeline** - should stream output as before

## Deployment Considerations

### Running on Render

If deploying to Render, add a worker service:

```yaml
services:
  - type: web
    name: amazon-publisher-web
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python publisher_web.py
    envVars:
      - key: ASYNC_JOBS_ENABLED
        value: true
      - key: ASYNC_JOB_TYPES
        value: generate_amazon_content
  
  - type: worker
    name: amazon-publisher-worker
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python worker.py
    envVars:
      - key: WORKER_CONCURRENCY
        value: 1
```

### Shared Database

- Both web and worker must access same `jobs.db`
- On Render, use persistent disk or external database
- For local dev, file-based SQLite works fine

### Monitoring

- Check worker logs regularly
- Monitor job queue depth (`/api/jobs/stats`)
- Set up alerts for failed jobs
- Track average job duration

## Future Enhancements

### Potential Improvements

1. **More Workflows:** Add async support for:
   - Lifestyle image generation
   - Full pipeline execution
   - eBay/Etsy publishing

2. **Better Progress Tracking:**
   - Real-time progress bar in UI
   - WebSocket updates instead of polling

3. **Job Prioritization:**
   - Priority queue for urgent jobs
   - User-specific queues

4. **Concurrency:**
   - Support `WORKER_CONCURRENCY > 1`
   - Resource-based scheduling

5. **Persistence:**
   - Job result file storage
   - Job history cleanup/archiving

6. **Monitoring:**
   - Prometheus metrics
   - Grafana dashboards
   - Email notifications on failure

## Files Created/Modified

### New Files

- `jobs.py` - Job queue management
- `api_jobs.py` - Job API endpoints
- `workflows/__init__.py` - Workflow module
- `workflows/amazon_content.py` - Extracted Amazon workflow
- `worker.py` - Background worker process
- `run_worker.bat` - Worker startup script
- `test_async_jobs.py` - Test script
- `ASYNC_JOBS_GUIDE.md` - This documentation

### Modified Files

- `publisher_web.py` - Added feature flags, job imports, async mode support

### Database

- `jobs.db` - Created automatically on first run

## Support

For issues or questions:
1. Check this guide
2. Review worker logs
3. Test with `test_async_jobs.py`
4. Check job status via API endpoints

---

**Version:** 1.0  
**Date:** January 19, 2026  
**Status:** Test Implementation - Production Ready After Validation
