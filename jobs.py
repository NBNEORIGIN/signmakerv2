#!/usr/bin/env python3
"""
Job Queue Management System
Provides SQLite-backed job queue for async workflow execution.
"""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

# Database path
DB_PATH = Path(__file__).parent / "jobs.db"


@contextmanager
def get_db():
    """Get database connection with WAL mode for concurrent access."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize job database schema."""
    with get_db() as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL,
                requested_by TEXT,
                payload TEXT NOT NULL,
                result TEXT,
                error TEXT,
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                progress TEXT,
                worker_id TEXT
            )
        ''')
        db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type)')
        db.commit()


def enqueue_job(job_type: str, payload: dict, requested_by: Optional[str] = None, max_attempts: int = 3) -> str:
    """
    Enqueue a new job.
    
    Args:
        job_type: Type of job (e.g., 'generate_amazon_content')
        payload: Job parameters as dict
        requested_by: User identifier (optional)
        max_attempts: Maximum retry attempts
        
    Returns:
        Job ID (UUID)
    """
    job_id = str(uuid.uuid4())
    now = time.time()
    
    with get_db() as db:
        db.execute('''
            INSERT INTO jobs (id, type, status, created_at, updated_at, payload, requested_by, max_attempts)
            VALUES (?, ?, 'queued', ?, ?, ?, ?, ?)
        ''', (job_id, job_type, now, now, json.dumps(payload), requested_by, max_attempts))
        db.commit()
    
    return job_id


def get_job(job_id: str) -> Optional[Dict]:
    """Get job by ID."""
    with get_db() as db:
        row = db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
        if not row:
            return None
        
        job = dict(row)
        # Parse JSON fields
        if job['payload']:
            job['payload'] = json.loads(job['payload'])
        if job['result']:
            job['result'] = json.loads(job['result'])
        if job['progress']:
            job['progress'] = json.loads(job['progress'])
        
        return job


def claim_next_job(worker_id: str) -> Optional[Dict]:
    """
    Atomically claim the next queued job.
    
    Args:
        worker_id: Identifier for the worker claiming the job
        
    Returns:
        Job dict or None if no jobs available
    """
    now = time.time()
    
    with get_db() as db:
        # Find next queued job
        row = db.execute('''
            SELECT id FROM jobs 
            WHERE status = 'queued' 
            ORDER BY created_at 
            LIMIT 1
        ''').fetchone()
        
        if not row:
            return None
        
        job_id = row['id']
        
        # Atomically claim it
        db.execute('''
            UPDATE jobs 
            SET status = 'running', 
                started_at = ?, 
                worker_id = ?, 
                updated_at = ?
            WHERE id = ? AND status = 'queued'
        ''', (now, worker_id, now, job_id))
        db.commit()
        
        # Return the claimed job
        return get_job(job_id)


def update_job_status(
    job_id: str,
    status: str,
    result: Optional[dict] = None,
    error: Optional[str] = None,
    progress: Optional[dict] = None,
    attempts: Optional[int] = None
):
    """
    Update job status and metadata.
    
    Args:
        job_id: Job ID
        status: New status (queued|running|succeeded|failed)
        result: Result data (for succeeded jobs)
        error: Error message (for failed jobs)
        progress: Progress information
        attempts: Updated attempt count
    """
    now = time.time()
    
    updates = ['updated_at = ?']
    params = [now]
    
    updates.append('status = ?')
    params.append(status)
    
    if status == 'succeeded':
        updates.append('finished_at = ?')
        params.append(now)
    elif status == 'failed':
        updates.append('finished_at = ?')
        params.append(now)
    
    if result is not None:
        updates.append('result = ?')
        params.append(json.dumps(result))
    
    if error is not None:
        updates.append('error = ?')
        params.append(error)
    
    if progress is not None:
        updates.append('progress = ?')
        params.append(json.dumps(progress))
    
    if attempts is not None:
        updates.append('attempts = ?')
        params.append(attempts)
    
    params.append(job_id)
    
    with get_db() as db:
        db.execute(f'''
            UPDATE jobs 
            SET {', '.join(updates)}
            WHERE id = ?
        ''', params)
        db.commit()


def list_jobs(status: Optional[str] = None, job_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """
    List jobs with optional filters.
    
    Args:
        status: Filter by status
        job_type: Filter by type
        limit: Maximum number of jobs to return
        
    Returns:
        List of job dicts
    """
    query = 'SELECT * FROM jobs WHERE 1=1'
    params = []
    
    if status:
        query += ' AND status = ?'
        params.append(status)
    
    if job_type:
        query += ' AND type = ?'
        params.append(job_type)
    
    query += ' ORDER BY created_at DESC LIMIT ?'
    params.append(limit)
    
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
        jobs = []
        for row in rows:
            job = dict(row)
            # Parse JSON fields
            if job['payload']:
                job['payload'] = json.loads(job['payload'])
            if job['result']:
                job['result'] = json.loads(job['result'])
            if job['progress']:
                job['progress'] = json.loads(job['progress'])
            jobs.append(job)
        
        return jobs


def requeue_stale_jobs(timeout_seconds: int = 600):
    """
    Requeue jobs that have been running too long (likely worker crashed).
    
    Args:
        timeout_seconds: Jobs running longer than this are considered stale
    """
    cutoff = time.time() - timeout_seconds
    
    with get_db() as db:
        db.execute('''
            UPDATE jobs 
            SET status = 'queued', 
                worker_id = NULL,
                updated_at = ?
            WHERE status = 'running' 
            AND started_at < ?
        ''', (time.time(), cutoff))
        db.commit()


# Initialize database on module import
init_db()
