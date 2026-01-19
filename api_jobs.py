#!/usr/bin/env python3
"""
Job API endpoints for Flask app.
Separated for clarity - import and register with Flask app.
"""

from flask import jsonify, request
from jobs import get_job, list_jobs


def register_job_routes(app):
    """Register job-related API routes with Flask app."""
    
    @app.route('/api/jobs/<job_id>', methods=['GET'])
    def get_job_status(job_id):
        """
        Get status and details of a specific job.
        
        Returns:
            200: Job details
            404: Job not found
        """
        job = get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Format timestamps for readability
        if job.get('created_at'):
            from datetime import datetime
            job['created_at_formatted'] = datetime.fromtimestamp(job['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        if job.get('started_at'):
            job['started_at_formatted'] = datetime.fromtimestamp(job['started_at']).strftime('%Y-%m-%d %H:%M:%S')
        if job.get('finished_at'):
            job['finished_at_formatted'] = datetime.fromtimestamp(job['finished_at']).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(job)
    
    
    @app.route('/api/jobs', methods=['GET'])
    def list_all_jobs():
        """
        List jobs with optional filters.
        
        Query params:
            status: Filter by status (queued|running|succeeded|failed)
            type: Filter by job type
            limit: Max number of jobs to return (default 50)
        
        Returns:
            200: List of jobs
        """
        status = request.args.get('status')
        job_type = request.args.get('type')
        limit = int(request.args.get('limit', 50))
        
        jobs = list_jobs(status=status, job_type=job_type, limit=limit)
        
        # Format timestamps
        from datetime import datetime
        for job in jobs:
            if job.get('created_at'):
                job['created_at_formatted'] = datetime.fromtimestamp(job['created_at']).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'jobs': jobs,
            'count': len(jobs),
            'filters': {
                'status': status,
                'type': job_type,
                'limit': limit
            }
        })
    
    
    @app.route('/api/jobs/stats', methods=['GET'])
    def get_job_stats():
        """
        Get job queue statistics.
        
        Returns:
            200: Job statistics by status
        """
        queued = list_jobs(status='queued', limit=1000)
        running = list_jobs(status='running', limit=1000)
        succeeded = list_jobs(status='succeeded', limit=100)
        failed = list_jobs(status='failed', limit=100)
        
        return jsonify({
            'queued': len(queued),
            'running': len(running),
            'succeeded': len(succeeded),
            'failed': len(failed),
            'total': len(queued) + len(running) + len(succeeded) + len(failed)
        })
