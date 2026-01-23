#!/usr/bin/env python3
"""
Async Job Worker Process

Continuously polls the job queue and executes jobs asynchronously.
Can be run as a separate process/service from the web app.
"""

import logging
import os
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from jobs import claim_next_job, update_job_status, requeue_stale_jobs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WORKER] %(levelname)s %(message)s",
)

# Worker configuration
WORKER_ID = f"worker-{os.getpid()}"
WORKER_CONCURRENCY = int(os.environ.get('WORKER_CONCURRENCY', '1'))
POLL_INTERVAL_SECONDS = int(os.environ.get('WORKER_POLL_INTERVAL', '2'))
STALE_JOB_TIMEOUT = int(os.environ.get('WORKER_STALE_JOB_TIMEOUT', '600'))  # 10 minutes

# Load config.bat environment variables (same as web app)
config_path = Path(__file__).parent / "config.bat"
if config_path.exists():
    with open(config_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("set ") and "=" in line:
                parts = line[4:].split("=", 1)
                if len(parts) == 2:
                    os.environ[parts[0]] = parts[1]


def progress_callback(stage: str, data: dict):
    """
    Callback for workflow progress updates.
    Updates job progress in database.
    """
    # This will be called by the workflow to report progress
    # We can update the job's progress field in real-time
    pass


def process_job(job):
    """
    Process a single job.
    
    Args:
        job: Job dict from database
    """
    job_id = job['id']
    job_type = job['type']
    
    logging.info(f"Processing job {job_id} (type: {job_type})")
    
    try:
        # Route to appropriate job handler
        if job_type == 'generate_amazon_content':
            # Update status to running
            update_job_status(job_id, 'running', progress={'stage': 'starting'})
            
            # Execute Amazon content generation via subprocess
            import subprocess
            payload = job['payload']
            m_number = payload.get('m_number', '')
            
            logging.info(f"Generating Amazon content for M{m_number}")
            
            # Run the generate_amazon_content.py script
            result = subprocess.run(
                ['python', 'generate_amazon_content.py', '--csv', 'products.csv', '--m-number', m_number, '--upload-images'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Job succeeded
                update_job_status(job_id, 'succeeded', result={'output': result.stdout})
                logging.info(f"Job {job_id} succeeded")
            else:
                # Job failed
                error = result.stderr or 'Script failed'
                update_job_status(job_id, 'failed', error=error)
                logging.error(f"Job {job_id} failed: {error}")
        
        else:
            # Unknown job type - log and mark as failed
            error = f"Unknown job type: {job_type}"
            update_job_status(job_id, 'failed', error=error)
            logging.error(f"Job {job_id} failed: {error}")
    
    except Exception as e:
        # Unexpected error during job processing
        error = f"Worker exception: {str(e)}"
        attempts = job['attempts'] + 1
        
        logging.exception(f"Job {job_id} raised exception")
        
        if attempts >= job['max_attempts']:
            update_job_status(job_id, 'failed', error=error, attempts=attempts)
            logging.error(f"Job {job_id} failed permanently after {attempts} attempts")
        else:
            update_job_status(job_id, 'queued', error=error, attempts=attempts)
            logging.warning(f"Job {job_id} exception (attempt {attempts}/{job['max_attempts']}), requeuing")


def worker_loop():
    """
    Main worker loop.
    Continuously polls for jobs and processes them.
    """
    logging.info(f"Worker {WORKER_ID} starting")
    logging.info(f"Configuration: concurrency={WORKER_CONCURRENCY}, poll_interval={POLL_INTERVAL_SECONDS}s")
    
    # For now, we only support concurrency=1 to avoid OOM issues
    if WORKER_CONCURRENCY != 1:
        logging.warning(f"WORKER_CONCURRENCY={WORKER_CONCURRENCY} not yet supported, using 1")
    
    consecutive_empty_polls = 0
    
    while True:
        try:
            # Requeue any stale jobs (workers that crashed)
            if consecutive_empty_polls % 30 == 0:  # Every ~60 seconds when idle
                requeue_stale_jobs(STALE_JOB_TIMEOUT)
            
            # Try to claim next job
            job = claim_next_job(WORKER_ID)
            
            if job:
                consecutive_empty_polls = 0
                process_job(job)
            else:
                # No jobs available
                consecutive_empty_polls += 1
                if consecutive_empty_polls == 1:
                    logging.info("No jobs in queue, waiting...")
                time.sleep(POLL_INTERVAL_SECONDS)
        
        except KeyboardInterrupt:
            logging.info("Worker shutting down (KeyboardInterrupt)")
            break
        
        except Exception as e:
            logging.exception("Worker loop error")
            time.sleep(POLL_INTERVAL_SECONDS)


def main():
    """Entry point for worker process."""
    logging.info("=" * 60)
    logging.info("Amazon Publisher - Async Job Worker")
    logging.info("=" * 60)
    
    # Verify environment is configured
    required_vars = ['ANTHROPIC_API_KEY', 'R2_ACCOUNT_ID', 'R2_BUCKET_NAME']
    missing = [var for var in required_vars if not os.environ.get(var)]
    
    if missing:
        logging.error(f"Missing required environment variables: {', '.join(missing)}")
        logging.error("Make sure config.bat is properly configured")
        return 1
    
    logging.info("Environment variables loaded successfully")
    
    # Start worker loop
    try:
        worker_loop()
    except Exception as e:
        logging.exception("Worker crashed")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
