#!/usr/bin/env python3
"""
Amazon Content Generation Workflow
Extracted workflow logic that can be run synchronously or asynchronously.
"""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Callable

# Import from parent directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_amazon_content import (
    read_products_from_csv,
    generate_content_with_claude,
    upload_to_cloudflare_r2,
    generate_flatfile,
    MAX_UPLOAD_WORKERS
)


def run_amazon_content_workflow(
    payload: dict,
    progress_callback: Optional[Callable[[str, dict], None]] = None
) -> dict:
    """
    Run the Amazon content generation workflow.
    
    This function extracts the core logic from generate_amazon_content.py
    so it can be called both synchronously and asynchronously.
    
    Args:
        payload: {
            'csv_path': str,              # Path to products CSV
            'output_path': str,           # Output flatfile path
            'exports_path': str,          # Exports directory (default: 'exports')
            'brand': str,                 # Brand name (default: 'NorthByNorthEast')
            'theme': str,                 # Theme description (optional)
            'use_cases': str,             # Use cases (optional)
            'upload_images': bool,        # Whether to upload images (default: True)
            'qa_filter': str,             # QA filter (default: 'approved')
            'm_number': str,              # Specific M number (optional)
        }
        progress_callback: Optional callback function(stage: str, data: dict)
                          Called at each workflow stage for progress tracking
    
    Returns:
        {
            'success': bool,
            'flatfile_path': str,
            'products_processed': int,
            'images_uploaded': int,
            'duration_seconds': float,
            'error': str (if failed)
        }
    """
    start_time = time.time()
    
    def report_progress(stage: str, data: dict = None):
        """Helper to report progress if callback provided."""
        if progress_callback:
            progress_callback(stage, data or {})
        logging.info(f"[WORKFLOW] {stage}: {data or {}}")
    
    try:
        # Extract parameters with defaults
        csv_path = Path(payload.get('csv_path', 'products.csv'))
        output_path = Path(payload.get('output_path', 'amazon_flatfile.xlsx'))
        exports_path = Path(payload.get('exports_path', 'exports'))
        brand = payload.get('brand', 'NorthByNorthEast')
        theme = payload.get('theme', '')
        use_cases = payload.get('use_cases', '')
        upload_images = payload.get('upload_images', True)
        qa_filter = payload.get('qa_filter', 'approved')
        m_number = payload.get('m_number')
        
        report_progress('validating_inputs', {
            'csv_path': str(csv_path),
            'output_path': str(output_path)
        })
        
        # Validate inputs
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        # Get API key from environment
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        # Read products
        report_progress('loading_products', {'csv_path': str(csv_path)})
        products = read_products_from_csv(csv_path, qa_filter=qa_filter)
        
        if not products:
            raise ValueError(f"No products found in {csv_path} with qa_filter={qa_filter}")
        
        # Filter to specific M number if requested
        if m_number:
            products = [p for p in products if p.m_number == m_number]
            if not products:
                raise ValueError(f"M number {m_number} not found in CSV")
        
        report_progress('products_loaded', {
            'count': len(products),
            'qa_filter': qa_filter
        })
        
        # Generate content for each product
        report_progress('generating_content', {'total_products': len(products)})
        contents = {}
        
        for idx, product in enumerate(products, 1):
            report_progress('generating_product_content', {
                'product': product.m_number,
                'progress': f"{idx}/{len(products)}"
            })
            
            try:
                content = generate_content_with_claude(product, api_key, brand, theme, use_cases)
                contents[product.m_number] = content
                logging.info(f"Generated content for {product.m_number}: {content.title[:80]}")
            except Exception as e:
                logging.error(f"Failed to generate content for {product.m_number}: {e}")
                raise
        
        report_progress('content_generated', {'products_with_content': len(contents)})
        
        # Upload images if requested
        images_uploaded = 0
        if upload_images:
            report_progress('preparing_image_upload', {})
            
            # Get R2 credentials
            r2_account_id = os.environ.get("R2_ACCOUNT_ID")
            r2_access_key = os.environ.get("R2_ACCESS_KEY_ID")
            r2_secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
            r2_bucket = os.environ.get("R2_BUCKET_NAME")
            r2_public_url = os.environ.get("R2_PUBLIC_URL")
            
            if not all([r2_account_id, r2_access_key, r2_secret_key, r2_bucket, r2_public_url]):
                raise ValueError("R2 environment variables not fully set")
            
            # Collect all images from all products
            all_upload_tasks = []
            for product in products:
                m_folder_name = f"{product.m_number} {product.description} {product.color_display} {product.size.title()}"
                m_folder = exports_path / m_folder_name
                
                if m_folder.exists():
                    images_dir = m_folder / "002 Images"
                    if images_dir.exists():
                        img_files = sorted(images_dir.glob("*.png"))
                        for idx, img_file in enumerate(img_files):
                            all_upload_tasks.append((product.m_number, idx, img_file))
                else:
                    logging.warning(f"M folder not found: {m_folder}")
            
            report_progress('uploading_images', {
                'total_images': len(all_upload_tasks),
                'workers': MAX_UPLOAD_WORKERS
            })
            
            # Upload all images in parallel
            upload_results = {}  # {m_number: {idx: url}}
            completed = 0
            
            def upload_task(task):
                m_number, idx, img_file = task
                url = upload_to_cloudflare_r2(
                    img_file, r2_bucket, r2_account_id,
                    r2_access_key, r2_secret_key, r2_public_url,
                    also_upload_jpeg=True
                )
                return (m_number, idx, url)
            
            with ThreadPoolExecutor(max_workers=MAX_UPLOAD_WORKERS) as executor:
                futures = {executor.submit(upload_task, task): task for task in all_upload_tasks}
                for future in as_completed(futures):
                    m_number, idx, url = future.result()
                    if m_number not in upload_results:
                        upload_results[m_number] = {}
                    upload_results[m_number][idx] = url
                    completed += 1
                    images_uploaded = completed
                    
                    if completed % 10 == 0 or completed == len(all_upload_tasks):
                        report_progress('image_upload_progress', {
                            'completed': completed,
                            'total': len(all_upload_tasks)
                        })
            
            # Assign URLs back to products in correct order
            for product in products:
                if product.m_number in upload_results:
                    results = upload_results[product.m_number]
                    product.image_urls = [results[i] for i in sorted(results.keys())]
            
            report_progress('images_uploaded', {'count': images_uploaded})
        
        # Generate flatfile
        report_progress('generating_flatfile', {'output_path': str(output_path)})
        generate_flatfile(products, contents, output_path, brand, parent_sku=None)
        
        duration = time.time() - start_time
        
        result = {
            'success': True,
            'flatfile_path': str(output_path),
            'products_processed': len(contents),
            'images_uploaded': images_uploaded,
            'duration_seconds': round(duration, 2)
        }
        
        report_progress('workflow_completed', result)
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = str(e)
        logging.error(f"Workflow failed: {error_msg}")
        
        report_progress('workflow_failed', {
            'error': error_msg,
            'duration_seconds': round(duration, 2)
        })
        
        return {
            'success': False,
            'error': error_msg,
            'duration_seconds': round(duration, 2)
        }
