#!/usr/bin/env python3
"""
Signage Publisher Web GUI

A browser-based interface for staff to run the publishing pipeline
across Amazon, eBay, and Etsy channels.
"""

import csv
import json
import os
import subprocess
import threading
import queue
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request, Response

# Import job queue system
from jobs import enqueue_job, get_job, list_jobs, update_job_status
from api_jobs import register_job_routes

# Configuration
APP_DIR = Path(__file__).parent
os.chdir(APP_DIR)

# Load config.bat environment variables
config_path = APP_DIR / "config.bat"
if config_path.exists():
    with open(config_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("set ") and "=" in line:
                parts = line[4:].split("=", 1)
                if len(parts) == 2:
                    os.environ[parts[0]] = parts[1]

# Feature flags for async job system
ASYNC_JOBS_ENABLED = os.environ.get('ASYNC_JOBS_ENABLED', 'false').lower() == 'true'
ASYNC_JOB_TYPES = set(filter(None, os.environ.get('ASYNC_JOB_TYPES', '').split(',')))

app = Flask(__name__)

# Store for command output streaming
command_outputs = {}
command_status = {}

# Products CSV columns
PRODUCTS_COLUMNS = [
    "m_number", "description", "size", "color", "layout_mode", "icon_files",
    "text_line_1", "text_line_2", "text_line_3", "orientation", "font",
    "material", "mounting_type", "lifestyle_image", "qa_status", "qa_comment",
    "icon_scale", "text_scale", "ebay_listing_id", "ean"
]

# Display columns (subset for the table)
DISPLAY_COLUMNS = [
    "m_number", "description", "size", "color", "layout_mode", 
    "icon_files", "orientation", "lifestyle_image", "qa_status"
]

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Signage Publisher</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
            border-radius: 8px;
        }
        header h1 {
            font-size: 28px;
            margin-bottom: 5px;
        }
        header p {
            opacity: 0.9;
            font-size: 14px;
        }
        .tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 20px;
        }
        .tab {
            padding: 12px 24px;
            background: #ddd;
            border: none;
            border-radius: 8px 8px 0 0;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .tab:hover {
            background: #ccc;
        }
        .tab.active {
            background: white;
            color: #3498db;
        }
        .tab-content {
            display: none;
            background: white;
            padding: 20px;
            border-radius: 0 8px 8px 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .tab-content.active {
            display: block;
        }
        .section {
            background: #f9f9f9;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .section h3 {
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .section h3 .step {
            background: #3498db;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #3498db;
            color: white;
        }
        .btn-primary:hover {
            background: #2980b9;
        }
        .btn-success {
            background: #27ae60;
            color: white;
        }
        .btn-success:hover {
            background: #219a52;
        }
        .btn-danger {
            background: #e74c3c;
            color: white;
        }
        .btn-danger:hover {
            background: #c0392b;
        }
        .btn-secondary {
            background: #95a5a6;
            color: white;
        }
        .btn-secondary:hover {
            background: #7f8c8d;
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        select, input[type="text"] {
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            min-width: 300px;
        }
        select:focus, input[type="text"]:focus {
            outline: none;
            border-color: #3498db;
        }
        .form-row {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .checkbox-group input {
            width: 18px;
            height: 18px;
        }
        #output {
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            padding: 15px;
            border-radius: 6px;
            height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        #output .success { color: #4ec9b0; }
        #output .error { color: #f14c4c; }
        #output .info { color: #3794ff; }
        .status-bar {
            background: #2c3e50;
            color: white;
            padding: 10px 15px;
            border-radius: 6px;
            margin-top: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #27ae60;
        }
        .status-dot.running {
            background: #f39c12;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        /* Products Table */
        .toolbar {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        .toolbar .spacer {
            flex: 1;
        }
        .products-table-container {
            overflow-x: auto;
            border: 1px solid #ddd;
            border-radius: 6px;
        }
        .products-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .products-table th {
            background: #2c3e50;
            color: white;
            padding: 12px 10px;
            text-align: left;
            font-weight: 500;
            white-space: nowrap;
            position: sticky;
            top: 0;
        }
        .products-table td {
            padding: 10px;
            border-bottom: 1px solid #eee;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .products-table tr:hover {
            background: #f5f9fc;
        }
        .products-table tr.selected {
            background: #e3f2fd;
        }
        .products-table td input {
            width: 100%;
            padding: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 13px;
        }
        .products-table td input:focus {
            outline: none;
            border-color: #3498db;
        }
        .product-count {
            color: #666;
            font-size: 14px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        /* QA Review styles */
        .qa-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }
        @media (max-width: 1200px) {
            .qa-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 800px) {
            .qa-grid { grid-template-columns: 1fr; }
        }
        .qa-card {
            background: #f9f9f9;
            border: 2px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
        }
        .qa-card.pending { border-color: #f39c12; }
        .qa-card.approved { border-color: #27ae60; }
        .qa-card.rejected { border-color: #e74c3c; }
        .qa-card-header {
            padding: 10px 15px;
            background: #2c3e50;
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .qa-card-header h4 { margin: 0; font-size: 14px; }
        .qa-card-header .size { font-size: 12px; opacity: 0.8; }
        .qa-card-body { padding: 15px; }
        .qa-status-btns {
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
        }
        .qa-status-btns button {
            flex: 1;
            padding: 8px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            opacity: 0.5;
        }
        .qa-status-btns button.selected { opacity: 1; }
        .qa-status-btns .btn-pending { background: #f39c12; color: #000; }
        .qa-status-btns .btn-approved { background: #27ae60; color: white; }
        .qa-status-btns .btn-rejected { background: #e74c3c; color: white; }
        .qa-comment {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-bottom: 10px;
            font-size: 13px;
            resize: vertical;
            min-height: 50px;
        }
        .qa-filter.active { background: #3498db !important; color: white !important; }
        .qa-card.hidden { display: none; }
        /* Scale controls */
        .scale-controls {
            display: flex;
            gap: 15px;
            margin-bottom: 10px;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 4px;
        }
        .scale-group {
            flex: 1;
        }
        .scale-group label {
            display: block;
            font-size: 11px;
            color: #666;
            margin-bottom: 4px;
        }
        .scale-group input[type="range"] {
            width: 100%;
            cursor: pointer;
        }
        .scale-val {
            color: #3498db;
            font-weight: bold;
        }
        .scale-presets {
            display: flex;
            gap: 4px;
            margin-top: 4px;
        }
        .scale-presets button {
            padding: 2px 6px;
            font-size: 10px;
            border: 1px solid #ccc;
            background: white;
            border-radius: 3px;
            cursor: pointer;
        }
        .scale-presets button:hover {
            background: #e0e0e0;
        }
        /* Main product image - LARGE for QA */
        .qa-card-images {
            background: #fff;
            padding: 10px;
            text-align: center;
        }
        .main-image {
            width: 100%;
            height: 280px;
            object-fit: contain;
            border: 2px solid #ddd;
            border-radius: 6px;
            cursor: pointer;
            background: #fafafa;
            image-rendering: -webkit-optimize-contrast;
            transform: scale(1);
        }
        .main-image:hover {
            border-color: #3498db;
        }
        .thumb-row {
            display: none;
        }
        /* Image modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            cursor: pointer;
        }
        .modal.active { display: flex; }
        .modal img {
            max-width: 90%;
            max-height: 90%;
            object-fit: contain;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Signage Publisher</h1>
            <p>Workflow: products.csv → Amazon → Create XLSM flatfile → eBay/Etsy</p>
        </header>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('pipeline')">Pipeline</button>
            <button class="tab" onclick="showTab('products')">Products CSV</button>
            <button class="tab" onclick="showTab('qa')">QA Review</button>
        </div>
        
        <!-- Pipeline Tab -->
        <div id="pipeline-tab" class="tab-content active">
            <div class="section">
                <h3><span class="step">1</span> Amazon Pipeline</h3>
                <p style="margin-bottom: 15px; color: #666;">Generate M folders and product images from products.csv (content generated after QA)</p>
                <div class="form-row">
                    <button class="btn btn-primary" onclick="runAmazon()" id="amazon-btn">
                        Run Amazon Pipeline
                    </button>
                    <span style="color: #666; margin: 0 10px;">or</span>
                    <input type="text" id="single-m-number" placeholder="M1220" style="width: 80px; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                    <button class="btn btn-secondary" onclick="runSingleProduct()" id="single-btn">
                        Run Single Product
                    </button>
                </div>
            </div>
            
            <div class="section">
                <h3><span class="step">2</span> Select Flatfile for eBay/Etsy</h3>
                <div class="form-row">
                    <select id="flatfile-select">
                        <option value="">Loading flatfiles...</option>
                    </select>
                    <button class="btn btn-secondary" onclick="refreshFlatfiles()">↻ Refresh</button>
                </div>
            </div>
            
            <div class="section">
                <h3><span class="step">3</span> Publish to Channels</h3>
                <div class="form-row">
                    <button class="btn btn-success" onclick="runEbay()" id="ebay-btn">
                        Run eBay Pipeline
                    </button>
                    <div class="checkbox-group">
                        <input type="checkbox" id="ebay-promote" checked>
                        <label for="ebay-promote">Promote (5% ad rate)</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="ebay-dryrun">
                        <label for="ebay-dryrun">Dry run</label>
                    </div>
                </div>
                <div class="form-row">
                    <button class="btn btn-success" onclick="runEtsy()" id="etsy-btn">
                        Run Etsy Pipeline
                    </button>
                    <span style="color: #666; font-size: 13px;">(Generates Shop Uploader file for manual upload)</span>
                </div>
            </div>
            
            <div class="section">
                <h3>Output</h3>
                
                <!-- Progress bar for pipelines -->
                <div id="pipeline-progress-container" style="display: none; margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span id="progress-label">Processing...</span>
                        <span id="progress-percent">0%</span>
                    </div>
                    <div style="background: #ddd; border-radius: 4px; height: 20px; overflow: hidden;">
                        <div id="progress-bar" style="background: #27ae60; height: 100%; width: 0%; transition: width 0.3s;"></div>
                    </div>
                </div>
                
                <div id="output">Ready. Select a pipeline to run.</div>
                <div class="status-bar">
                    <div class="status-indicator">
                        <div class="status-dot" id="status-dot"></div>
                        <span id="status-text">Ready</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- QA Review Tab -->
        <div id="qa-tab" class="tab-content">
            <div class="section">
                <h3>QA Review</h3>
                <p style="margin-bottom: 15px; color: #666;">Review and approve generated product images before publishing</p>
                
                <div class="toolbar" style="margin-bottom: 20px;">
                    <button class="btn btn-primary" onclick="loadQAProducts()">↻ Refresh</button>
                    <button class="btn btn-success" onclick="approveAllPending()">✓ Approve All Pending</button>
                    <button class="btn btn-secondary" onclick="regeneratePending()">🔄 Regenerate Pending</button>
                    <button class="btn btn-warning" id="finalize-all-btn" onclick="showPipelineConfig()" style="background: #e67e22; color: white;">📦 Finalize All Approved & Generate Content</button>
                    <div class="spacer"></div>
                    <span id="qa-stats" style="color: #666;">Loading...</span>
                </div>
                
                <!-- Pipeline Configuration Panel -->
                <div id="pipeline-config" style="display: none; background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                    <h4 style="margin: 0 0 15px 0;">📝 Product Description for AI Content Generation</h4>
                    <p style="color: #666; margin-bottom: 10px; font-size: 13px;">Provide a clear description of the signage theme. This will be used by AI to generate Amazon listing content, search terms, and lifestyle images.</p>
                    
                    <div style="margin-bottom: 10px;">
                        <button class="btn btn-primary" onclick="autoGenerateDescription()" id="auto-generate-btn" style="padding: 8px 15px;">
                            🤖 Auto-generate with AI
                        </button>
                        <span id="auto-generate-status" style="margin-left: 10px; color: #666; font-size: 13px;"></span>
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; font-weight: bold; margin-bottom: 5px;">Signage Theme/Description:</label>
                        <textarea id="product-theme" rows="3" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;" placeholder="e.g., Keep Dogs On Lead sign for public parks and outdoor spaces. Warning sign to remind dog owners to keep their pets on a leash in designated areas."></textarea>
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; font-weight: bold; margin-bottom: 5px;">Target Use Cases (optional):</label>
                        <input type="text" id="product-use-cases" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px;" placeholder="e.g., parks, nature reserves, dog walking areas, public gardens">
                    </div>
                    
                    <div style="display: flex; gap: 10px;">
                        <button class="btn btn-success" onclick="startPipeline()" style="padding: 10px 20px;">▶ Start Pipeline</button>
                        <button class="btn btn-secondary" onclick="hidePipelineConfig()">Cancel</button>
                    </div>
                </div>
                
                <div id="pipeline-status" style="display: none; background: #f8f9fa; border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                    <h4 style="margin: 0 0 15px 0;">📦 Pipeline Progress</h4>
                    
                    <!-- Step indicators -->
                    <div style="display: flex; justify-content: space-around; margin-bottom: 20px; padding: 15px; background: white; border-radius: 8px; border: 1px solid #eee;">
                        <div style="text-align: center;">
                            <div id="step-images-tick" style="font-size: 32px; margin-bottom: 5px;">⏳</div>
                            <div style="font-weight: bold;">Images</div>
                            <div style="font-size: 11px; color: #666;">Product photos</div>
                        </div>
                        <div style="text-align: center;">
                            <div id="step-lifestyle-tick" style="font-size: 32px; margin-bottom: 5px;">⏳</div>
                            <div style="font-weight: bold;">Lifestyle</div>
                            <div style="font-size: 11px; color: #666;">Context images</div>
                        </div>
                        <div style="text-align: center;">
                            <div id="step-content-tick" style="font-size: 32px; margin-bottom: 5px;">⏳</div>
                            <div style="font-weight: bold;">Content</div>
                            <div style="font-size: 11px; color: #666;">Amazon listing</div>
                        </div>
                    </div>
                    
                    <!-- Overall progress -->
                    <div style="margin-bottom: 15px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span id="pipeline-step">Initializing...</span>
                            <span id="pipeline-percent">0%</span>
                        </div>
                        <div style="background: #ddd; border-radius: 4px; height: 20px; overflow: hidden;">
                            <div id="pipeline-bar" style="background: #27ae60; height: 100%; width: 0%; transition: width 0.3s;"></div>
                        </div>
                    </div>
                    
                    <!-- Product grid -->
                    <div id="pipeline-products" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; margin-bottom: 15px; max-height: 300px; overflow-y: auto;"></div>
                    
                    <!-- Generated flatfile -->
                    <div id="pipeline-flatfile" style="display: none; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 4px; padding: 10px; margin-bottom: 15px;">
                        <strong>📄 Generated Flatfile:</strong> <span id="flatfile-name"></span>
                    </div>
                    
                    <!-- CLI log (collapsed by default) -->
                    <details style="margin-top: 10px;">
                        <summary style="cursor: pointer; color: #666; font-size: 12px;">Show Technical Log</summary>
                        <div id="pipeline-log" style="font-family: monospace; font-size: 11px; max-height: 150px; overflow-y: auto; background: #1e1e1e; color: #0f0; padding: 10px; border-radius: 4px; margin-top: 10px;"></div>
                    </details>
                </div>
                
                <div class="qa-filters" style="margin-bottom: 15px;">
                    <button class="btn btn-secondary qa-filter active" data-filter="all" onclick="filterQA('all')">All</button>
                    <button class="btn btn-secondary qa-filter" data-filter="pending" onclick="filterQA('pending')">Pending</button>
                    <button class="btn btn-secondary qa-filter" data-filter="approved" onclick="filterQA('approved')">Approved</button>
                    <button class="btn btn-secondary qa-filter" data-filter="rejected" onclick="filterQA('rejected')">Rejected</button>
                </div>
                
                <div id="qa-grid" class="qa-grid">
                    <div class="loading">Loading products...</div>
                </div>
            </div>
        </div>
        
        <!-- Products Tab -->
        <div id="products-tab" class="tab-content">
            <div class="toolbar">
                <button class="btn btn-secondary" onclick="loadProducts()">↻ Reload</button>
                <button class="btn btn-primary" onclick="saveProducts()">💾 Save</button>
                <button class="btn btn-success" onclick="addProduct()">+ Add Row</button>
                <button class="btn btn-danger" onclick="deleteSelected()">🗑 Delete Selected</button>
                <div class="spacer"></div>
                <span class="product-count" id="product-count">0 products</span>
            </div>
            <div class="products-table-container" style="max-height: 500px; overflow-y: auto;">
                <table class="products-table" id="products-table">
                    <thead>
                        <tr id="table-header"></tr>
                    </thead>
                    <tbody id="table-body">
                        <tr><td colspan="9" class="loading">Loading products...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <!-- Image Modal -->
    <div class="modal" id="image-modal" onclick="closeModal()">
        <img id="modal-image" src="" alt="Full size">
    </div>
    
    <script>
        const DISPLAY_COLUMNS = {{ display_columns | tojson }};
        let products = [];
        let qaProducts = [];
        let selectedRows = new Set();
        let isRunning = false;
        let currentQAFilter = 'all';
        
        // Tab switching
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelector(`#${tabName}-tab`).classList.add('active');
            event.target.classList.add('active');
            
            if (tabName === 'products') {
                loadProducts();
            }
            if (tabName === 'qa') {
                loadQAProducts();
            }
        }
        
        // Image modal
        function showModal(src) {
            document.getElementById('modal-image').src = src;
            document.getElementById('image-modal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('image-modal').classList.remove('active');
        }
        
        // Flatfiles
        async function refreshFlatfiles() {
            const select = document.getElementById('flatfile-select');
            select.innerHTML = '<option value="">Loading...</option>';
            
            const response = await fetch('/api/flatfiles');
            const data = await response.json();
            
            select.innerHTML = data.flatfiles.map(f => 
                `<option value="${f}">${f}</option>`
            ).join('');
            
            if (data.flatfiles.length === 0) {
                select.innerHTML = '<option value="">No flatfiles found</option>';
            }
        }
        
        // Pipeline execution
        function setRunning(running) {
            isRunning = running;
            const dot = document.getElementById('status-dot');
            const btns = ['amazon-btn', 'ebay-btn', 'etsy-btn'];
            
            if (running) {
                dot.classList.add('running');
                btns.forEach(id => document.getElementById(id).disabled = true);
            } else {
                dot.classList.remove('running');
                btns.forEach(id => document.getElementById(id).disabled = false);
            }
        }
        
        function setStatus(text) {
            document.getElementById('status-text').textContent = text;
        }
        
        function appendOutput(text, className = '') {
            const output = document.getElementById('output');
            if (className) {
                output.innerHTML += `<span class="${className}">${escapeHtml(text)}</span>\\n`;
            } else {
                output.innerHTML += escapeHtml(text) + '\\n';
            }
            output.scrollTop = output.scrollHeight;
        }
        
        function clearOutput() {
            document.getElementById('output').innerHTML = '';
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function showProgress(label, percent) {
            const container = document.getElementById('pipeline-progress-container');
            const bar = document.getElementById('progress-bar');
            const labelEl = document.getElementById('progress-label');
            const percentEl = document.getElementById('progress-percent');
            
            container.style.display = 'block';
            bar.style.width = percent + '%';
            labelEl.textContent = label;
            percentEl.textContent = Math.round(percent) + '%';
        }
        
        function hideProgress() {
            document.getElementById('pipeline-progress-container').style.display = 'none';
        }
        
        function parseProgress(line) {
            // Parse progress patterns from output
            // Pattern: "Upload progress: 10/50 images"
            let match = line.match(/progress[:\s]+(\d+)\/(\d+)/i);
            if (match) {
                const current = parseInt(match[1]);
                const total = parseInt(match[2]);
                return { label: 'Uploading images...', percent: (current / total) * 100 };
            }
            // Pattern: "Processing M1150..."
            match = line.match(/Processing (M\d+)/i);
            if (match) {
                return { label: `Processing ${match[1]}...`, percent: null };
            }
            // Pattern: "Generating content for M1150"
            match = line.match(/Generating content for (M\d+)/i);
            if (match) {
                return { label: `Generating content for ${match[1]}...`, percent: null };
            }
            return null;
        }
        
        async function runPipeline(endpoint, name) {
            if (isRunning) return;
            
            clearOutput();
            setRunning(true);
            setStatus(`Running: ${name}...`);
            showProgress('Starting...', 0);
            appendOutput(`=== ${name} ===\\n`, 'info');
            
            let progressPercent = 0;
            
            try {
                const response = await fetch(endpoint, { method: 'POST' });
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const text = decoder.decode(value);
                    const lines = text.split('\\n');
                    lines.forEach(line => {
                        if (line.trim()) {
                            // Parse progress
                            const progress = parseProgress(line);
                            if (progress) {
                                if (progress.percent !== null) {
                                    progressPercent = progress.percent;
                                }
                                showProgress(progress.label, progressPercent);
                            }
                            
                            if (line.includes('ERROR') || line.includes('FAILED')) {
                                appendOutput(line, 'error');
                            } else if (line.includes('SUCCESS') || line.includes('COMPLETE')) {
                                appendOutput(line, 'success');
                            } else {
                                appendOutput(line);
                            }
                        }
                    });
                }
                
                showProgress('Complete!', 100);
                appendOutput(`\\n=== ${name} Complete ===`, 'success');
                setStatus(`Completed: ${name}`);
                
                // Hide progress bar after 2 seconds
                setTimeout(hideProgress, 2000);
            } catch (error) {
                appendOutput(`Error: ${error.message}`, 'error');
                setStatus(`Error: ${name}`);
                hideProgress();
            }
            
            setRunning(false);
        }
        
        function runAmazon() {
            runPipeline('/api/run/amazon', 'Amazon Pipeline');
        }
        
        function runEbay() {
            const flatfile = document.getElementById('flatfile-select').value;
            if (!flatfile) {
                alert('Please select a flatfile first!');
                return;
            }
            
            const promote = document.getElementById('ebay-promote').checked;
            const dryrun = document.getElementById('ebay-dryrun').checked;
            
            let url = `/api/run/ebay?flatfile=${encodeURIComponent(flatfile)}`;
            if (dryrun) url += '&dryrun=1';
            else if (promote) url += '&promote=1';
            
            runPipeline(url, `eBay Pipeline (${flatfile})`);
        }
        
        function runEtsy() {
            const flatfile = document.getElementById('flatfile-select').value;
            if (!flatfile) {
                alert('Please select a flatfile first!');
                return;
            }
            
            runPipeline(`/api/run/etsy?flatfile=${encodeURIComponent(flatfile)}`, 
                        `Etsy Pipeline (${flatfile})`);
        }
        
        function runSingleProduct() {
            const mNumber = document.getElementById('single-m-number').value.trim().toUpperCase();
            if (!mNumber) {
                alert('Please enter an M number (e.g., M1220)');
                return;
            }
            if (!mNumber.match(/^M\\d+$/)) {
                alert('Invalid M number format. Use format like M1220');
                return;
            }
            
            runPipeline(`/api/run/single-product?m_number=${mNumber}`, 
                        `Single Product Pipeline (${mNumber})`);
        }
        
        // Products CSV
        async function loadProducts() {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '<tr><td colspan="9" class="loading">Loading...</td></tr>';
            
            const response = await fetch('/api/products');
            const data = await response.json();
            products = data.products;
            
            renderProducts();
        }
        
        function renderProducts() {
            // Header
            const header = document.getElementById('table-header');
            header.innerHTML = '<th><input type="checkbox" onchange="toggleSelectAll(this)"></th>' +
                DISPLAY_COLUMNS.map(col => `<th>${col}</th>`).join('');
            
            // Body
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = products.map((product, idx) => `
                <tr data-idx="${idx}" class="${selectedRows.has(idx) ? 'selected' : ''}" onclick="toggleSelect(${idx}, event)">
                    <td><input type="checkbox" ${selectedRows.has(idx) ? 'checked' : ''} onclick="event.stopPropagation(); toggleSelect(${idx})"></td>
                    ${DISPLAY_COLUMNS.map(col => `
                        <td ondblclick="editCell(this, ${idx}, '${col}')" title="${escapeHtml(product[col] || '')}">${escapeHtml(product[col] || '')}</td>
                    `).join('')}
                </tr>
            `).join('');
            
            document.getElementById('product-count').textContent = `${products.length} products`;
        }
        
        function toggleSelect(idx, event) {
            if (event && event.target.tagName === 'INPUT') return;
            
            if (selectedRows.has(idx)) {
                selectedRows.delete(idx);
            } else {
                selectedRows.add(idx);
            }
            renderProducts();
        }
        
        function toggleSelectAll(checkbox) {
            if (checkbox.checked) {
                products.forEach((_, idx) => selectedRows.add(idx));
            } else {
                selectedRows.clear();
            }
            renderProducts();
        }
        
        function editCell(td, idx, col) {
            const currentValue = products[idx][col] || '';
            const input = document.createElement('input');
            input.type = 'text';
            input.value = currentValue;
            td.innerHTML = '';
            td.appendChild(input);
            input.focus();
            input.select();
            
            function save() {
                products[idx][col] = input.value;
                td.textContent = input.value;
                td.title = input.value;
            }
            
            input.onblur = save;
            input.onkeydown = (e) => {
                if (e.key === 'Enter') { save(); input.blur(); }
                if (e.key === 'Escape') { td.textContent = currentValue; td.title = currentValue; }
            };
        }
        
        async function saveProducts() {
            const response = await fetch('/api/products', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ products })
            });
            
            const data = await response.json();
            if (data.success) {
                alert(`Saved ${products.length} products to products.csv`);
            } else {
                alert(`Error: ${data.error}`);
            }
        }
        
        function addProduct() {
            // Find max M number
            let maxM = 1000;
            products.forEach(p => {
                const m = p.m_number || '';
                if (m.startsWith('M') && !isNaN(parseInt(m.slice(1)))) {
                    maxM = Math.max(maxM, parseInt(m.slice(1)));
                }
            });
            
            const newProduct = {
                m_number: `M${maxM + 1}`,
                description: '',
                size: 'saville',
                color: 'silver',
                layout_mode: 'A',
                icon_files: '',
                orientation: 'landscape',
                lifestyle_image: '',
                qa_status: 'pending'
            };
            
            products.push(newProduct);
            renderProducts();
        }
        
        function deleteSelected() {
            if (selectedRows.size === 0) {
                alert('Please select rows to delete');
                return;
            }
            
            if (!confirm(`Delete ${selectedRows.size} selected row(s)?`)) return;
            
            products = products.filter((_, idx) => !selectedRows.has(idx));
            selectedRows.clear();
            renderProducts();
        }
        
        // QA Review functions
        async function loadQAProducts() {
            const grid = document.getElementById('qa-grid');
            grid.innerHTML = '<div class="loading">Loading products...</div>';
            
            const response = await fetch('/api/qa/products');
            const data = await response.json();
            qaProducts = data.products;
            
            renderQAProducts();
            updateQAStats();
        }
        
        function renderQAProducts() {
            const grid = document.getElementById('qa-grid');
            const t = Date.now();
            
            grid.innerHTML = qaProducts.map((p, idx) => {
                const status = p.qa_status || 'pending';
                const hidden = currentQAFilter !== 'all' && status !== currentQAFilter ? 'hidden' : '';
                
                return `
                <div class="qa-card ${status} ${hidden}" data-idx="${idx}" data-status="${status}">
                    <div class="qa-card-header">
                        <h4>${p.m_number} - ${(p.description || '').substring(0, 40)}...</h4>
                        <span class="size">${p.size} / ${p.color}</span>
                    </div>
                    <div class="qa-card-images">
                        <img class="main-image" id="main-${p.m_number}" src="/api/image/${p.m_number}/001?t=${t}" onclick="showModal(this.src)" onerror="this.src='/api/preview/${p.m_number}?icon_scale=${p.icon_scale || 1.0}&text_scale=${p.text_scale || 1.0}'" alt="Main Product Image">
                        <div class="thumb-row">
                            <img src="/api/image/${p.m_number}/001?t=${t}" onclick="showModal(this.src)" onerror="this.style.display='none'" title="Main">
                            <img src="/api/image/${p.m_number}/002?t=${t}" onclick="showModal(this.src)" onerror="this.style.display='none'" title="Dimensions">
                            <img src="/api/image/${p.m_number}/003?t=${t}" onclick="showModal(this.src)" onerror="this.style.display='none'" title="Peel">
                            <img src="/api/image/${p.m_number}/004?t=${t}" onclick="showModal(this.src)" onerror="this.style.display='none'" title="Rear">
                            <img src="/api/image/${p.m_number}/005?t=${t}" onclick="showModal(this.src)" onerror="this.style.display='none'" title="Lifestyle">
                        </div>
                    </div>
                    <div class="qa-card-body">
                        <div class="qa-status-btns">
                            <button class="btn-pending ${status === 'pending' ? 'selected' : ''}" onclick="setQAStatus(${idx}, 'pending')">Pending</button>
                            <button class="btn-approved ${status === 'approved' ? 'selected' : ''}" onclick="setQAStatus(${idx}, 'approved')">Approved</button>
                            <button class="btn-rejected ${status === 'rejected' ? 'selected' : ''}" onclick="setQAStatus(${idx}, 'rejected')">Rejected</button>
                        </div>
                        <div class="scale-controls">
                            <div class="scale-group">
                                <label>Icon Scale: <span class="scale-val">${p.icon_scale || '1.0'}x</span></label>
                                <input type="range" min="0.5" max="2.0" step="0.05" value="${p.icon_scale || '1.0'}" 
                                       oninput="setQAScale(${idx}, 'icon_scale', this.value); this.previousElementSibling.querySelector('.scale-val').textContent = this.value + 'x'; updateLivePreview(${idx})">
                                <div class="scale-presets">
                                    <button onclick="setQAScalePreset(${idx}, 'icon_scale', 0.8, this)">0.8</button>
                                    <button onclick="setQAScalePreset(${idx}, 'icon_scale', 1.0, this)">1.0</button>
                                    <button onclick="setQAScalePreset(${idx}, 'icon_scale', 1.25, this)">1.25</button>
                                    <button onclick="setQAScalePreset(${idx}, 'icon_scale', 1.5, this)">1.5</button>
                                </div>
                            </div>
                            <div class="scale-group">
                                <label>Text Scale: <span class="scale-val">${p.text_scale || '1.0'}x</span></label>
                                <input type="range" min="0.5" max="2.0" step="0.05" value="${p.text_scale || '1.0'}"
                                       oninput="setQAScale(${idx}, 'text_scale', this.value); this.previousElementSibling.querySelector('.scale-val').textContent = this.value + 'x'; updateLivePreview(${idx})">
                                <div class="scale-presets">
                                    <button onclick="setQAScalePreset(${idx}, 'text_scale', 0.8, this)">0.8</button>
                                    <button onclick="setQAScalePreset(${idx}, 'text_scale', 1.0, this)">1.0</button>
                                    <button onclick="setQAScalePreset(${idx}, 'text_scale', 1.25, this)">1.25</button>
                                    <button onclick="setQAScalePreset(${idx}, 'text_scale', 1.5, this)">1.5</button>
                                </div>
                            </div>
                        </div>
                        <textarea class="qa-comment" placeholder="QA comments..." onchange="setQAComment(${idx}, this.value)">${p.qa_comment || ''}</textarea>
                        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                            <button class="btn btn-primary" style="flex: 1;" onclick="saveQAProduct(${idx})">Save</button>
                            <button class="btn btn-secondary" style="flex: 1;" onclick="regenerateSingle(${idx})">🔄 Regen</button>
                            <button class="btn btn-secondary" style="flex: 1;" onclick="generateLifestyle(${idx})">🖼️ Lifestyle</button>
                            ${status === 'approved' ? `<button class="btn btn-success finalize-btn" style="flex-basis: 100%; margin-top: 8px;" onclick="finalizeApproved(${idx})">📦 Finalize (generate all images)</button>` : ''}
                        </div>
                    </div>
                </div>
                `;
            }).join('');
        }
        
        function updateQAStats() {
            const pending = qaProducts.filter(p => !p.qa_status || p.qa_status === 'pending').length;
            const approved = qaProducts.filter(p => p.qa_status === 'approved').length;
            const rejected = qaProducts.filter(p => p.qa_status === 'rejected').length;
            
            document.getElementById('qa-stats').innerHTML = 
                `Total: <strong>${qaProducts.length}</strong> | ` +
                `<span style="color: #f39c12;">Pending: <strong>${pending}</strong></span> | ` +
                `<span style="color: #27ae60;">Approved: <strong>${approved}</strong></span> | ` +
                `<span style="color: #e74c3c;">Rejected: <strong>${rejected}</strong></span>`;
        }
        
        function filterQA(filter) {
            currentQAFilter = filter;
            document.querySelectorAll('.qa-filter').forEach(b => b.classList.remove('active'));
            document.querySelector(`.qa-filter[data-filter="${filter}"]`).classList.add('active');
            
            document.querySelectorAll('.qa-card').forEach(card => {
                const status = card.dataset.status;
                if (filter === 'all' || status === filter) {
                    card.classList.remove('hidden');
                } else {
                    card.classList.add('hidden');
                }
            });
        }
        
        function setQAStatus(idx, status) {
            qaProducts[idx].qa_status = status;
            const card = document.querySelector(`.qa-card[data-idx="${idx}"]`);
            card.className = `qa-card ${status}`;
            card.dataset.status = status;
            
            card.querySelectorAll('.qa-status-btns button').forEach(btn => btn.classList.remove('selected'));
            card.querySelector(`.btn-${status}`).classList.add('selected');
            
            // Apply filter
            if (currentQAFilter !== 'all' && status !== currentQAFilter) {
                card.classList.add('hidden');
            }
            
            updateQAStats();
        }
        
        function setQAComment(idx, comment) {
            qaProducts[idx].qa_comment = comment;
        }
        
        function setQAScale(idx, field, value) {
            qaProducts[idx][field] = value;
        }
        
        function setQAScalePreset(idx, field, value, btn) {
            qaProducts[idx][field] = value.toString();
            const card = btn.closest('.qa-card');
            const group = btn.closest('.scale-group');
            group.querySelector('input[type="range"]').value = value;
            group.querySelector('.scale-val').textContent = value + 'x';
            updateLivePreview(idx);
        }
        
        function updateLivePreview(idx) {
            const p = qaProducts[idx];
            const mainImg = document.getElementById(`main-${p.m_number}`);
            if (mainImg) {
                const iconScale = p.icon_scale || '1.0';
                const textScale = p.text_scale || '1.0';
                mainImg.src = `/api/preview/${p.m_number}?icon_scale=${iconScale}&text_scale=${textScale}&t=${Date.now()}`;
            }
        }
        
        async function saveQAProduct(idx) {
            const product = qaProducts[idx];
            const card = document.querySelector(`.qa-card[data-idx="${idx}"]`);
            const saveBtn = card.querySelector('.btn-primary');
            const originalText = saveBtn.textContent;
            
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
            
            const response = await fetch('/api/qa/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    m_number: product.m_number,
                    qa_status: product.qa_status || 'pending',
                    qa_comment: product.qa_comment || '',
                    icon_scale: product.icon_scale || '1.0',
                    text_scale: product.text_scale || '1.0'
                })
            });
            
            const data = await response.json();
            saveBtn.disabled = false;
            
            if (data.success) {
                // Show tick indicator instead of popup
                saveBtn.textContent = '✓ Saved';
                saveBtn.style.background = '#27ae60';
                setTimeout(() => {
                    saveBtn.textContent = originalText;
                    saveBtn.style.background = '';
                }, 1500);
            } else {
                saveBtn.textContent = '✗ Error';
                saveBtn.style.background = '#e74c3c';
                setTimeout(() => {
                    saveBtn.textContent = originalText;
                    saveBtn.style.background = '';
                }, 2000);
            }
        }
        
        async function approveAllPending() {
            if (!confirm('Approve all pending products?')) return;
            
            const pending = qaProducts.filter(p => !p.qa_status || p.qa_status === 'pending');
            const btn = document.querySelector('button[onclick="approveAllPending()"]');
            const originalText = btn ? btn.textContent : '';
            if (btn) {
                btn.disabled = true;
                btn.textContent = `Approving ${pending.length}...`;
            }
            
            for (const p of pending) {
                p.qa_status = 'approved';
                await fetch('/api/qa/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        m_number: p.m_number,
                        qa_status: 'approved',
                        qa_comment: p.qa_comment || ''
                    })
                });
            }
            
            renderQAProducts();
            updateQAStats();
            
            if (btn) {
                btn.textContent = `✓ Approved ${pending.length}`;
                btn.style.background = '#27ae60';
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.style.background = '';
                    btn.disabled = false;
                }, 2000);
            }
        }
        
        async function regeneratePending() {
            if (!confirm('Regenerate all pending products? This will re-run image generation.')) return;
            
            // Switch to pipeline tab and run regeneration
            document.querySelectorAll('.tab')[0].click();
            runPipeline('/api/run/regenerate-pending', 'Regenerate Pending Products');
        }
        
        async function regenerateSingle(idx) {
            const product = qaProducts[idx];
            
            // Save first to ensure scale values are persisted
            await fetch('/api/qa/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    m_number: product.m_number,
                    qa_status: product.qa_status || 'pending',
                    qa_comment: product.qa_comment || '',
                    icon_scale: product.icon_scale || '1.0',
                    text_scale: product.text_scale || '1.0'
                })
            });
            
            // Run single product regeneration
            const card = document.querySelector(`.qa-card[data-idx="${idx}"]`);
            const regenBtn = card.querySelector('button:last-child'); // Regen button is last
            regenBtn.disabled = true;
            regenBtn.textContent = '⏳ Regenerating...';
            
            try {
                const response = await fetch(`/api/run/regenerate-single?m_number=${product.m_number}`, { method: 'POST' });
                const text = await response.text();
                console.log('Regen output:', text);
                
                // Force refresh main image - remove and re-add to bypass cache
                const t = Date.now();
                const mainImg = document.getElementById(`main-${product.m_number}`);
                if (mainImg) {
                    const parent = mainImg.parentNode;
                    const newImg = document.createElement('img');
                    newImg.className = 'main-image';
                    newImg.id = `main-${product.m_number}`;
                    newImg.src = `/api/image/${product.m_number}/001?_=${t}`;
                    newImg.onclick = () => showModal(newImg.src);
                    parent.replaceChild(newImg, mainImg);
                }
                
                regenBtn.textContent = '✓ Done';
                setTimeout(() => { regenBtn.textContent = '🔄 Regen'; regenBtn.disabled = false; }, 2000);
            } catch (e) {
                console.error('Regen error:', e);
                regenBtn.textContent = '❌ Error';
                setTimeout(() => { regenBtn.textContent = '🔄 Regen'; regenBtn.disabled = false; }, 2000);
            }
        }
        
        async function generateLifestyle(idx) {
            const product = qaProducts[idx];
            const card = document.querySelector(`.qa-card[data-idx="${idx}"]`);
            const btns = card.querySelectorAll('.btn-secondary');
            const lifestyleBtn = btns[1]; // Second secondary button is Lifestyle
            
            lifestyleBtn.disabled = true;
            lifestyleBtn.textContent = '⏳ Generating...';
            
            try {
                const response = await fetch(`/api/run/lifestyle-single?m_number=${product.m_number}`, { method: 'POST' });
                const text = await response.text();
                console.log('Lifestyle output:', text);
                
                // Refresh thumbnail row to show new lifestyle image
                const t = Date.now();
                const thumbRow = card.querySelector('.thumb-row');
                if (thumbRow) {
                    const lifestyleImg = thumbRow.querySelector('img:last-child');
                    if (lifestyleImg) {
                        lifestyleImg.src = `/api/image/${product.m_number}/005?t=${t}`;
                    }
                }
                
                lifestyleBtn.textContent = '✓ Done';
                setTimeout(() => { lifestyleBtn.textContent = '🖼️ Lifestyle'; lifestyleBtn.disabled = false; }, 2000);
            } catch (e) {
                console.error('Lifestyle error:', e);
                lifestyleBtn.textContent = '❌ Error';
                setTimeout(() => { lifestyleBtn.textContent = '🖼️ Lifestyle'; lifestyleBtn.disabled = false; }, 2000);
            }
        }
        
        async function finalizeApproved(idx) {
            const product = qaProducts[idx];
            
            // Generate all images (not just main) for approved product
            const card = document.querySelector(`.qa-card[data-idx="${idx}"]`);
            const btn = card.querySelector('.finalize-btn');
            if (btn) {
                btn.disabled = true;
                btn.textContent = '⏳ Generating all images...';
            }
            
            try {
                const response = await fetch(`/api/run/finalize?m_number=${product.m_number}`, { method: 'POST' });
                const text = await response.text();
                console.log('Finalize output:', text);
                
                if (btn) {
                    btn.textContent = '✓ Complete';
                    btn.disabled = true;
                }
                alert(`${product.m_number}: All images and master design file generated!`);
            } catch (e) {
                console.error('Finalize error:', e);
                if (btn) {
                    btn.textContent = '❌ Error';
                    setTimeout(() => { btn.textContent = '📦 Finalize'; btn.disabled = false; }, 2000);
                }
            }
        }
        
        function showPipelineConfig() {
            const approved = qaProducts.filter(p => p.qa_status === 'approved');
            if (approved.length === 0) {
                alert('No approved products to finalize.');
                return;
            }
            document.getElementById('pipeline-config').style.display = 'block';
            document.getElementById('product-theme').focus();
        }
        
        function hidePipelineConfig() {
            document.getElementById('pipeline-config').style.display = 'none';
        }
        
        async function autoGenerateDescription() {
            const btn = document.getElementById('auto-generate-btn');
            const status = document.getElementById('auto-generate-status');
            
            // Get first approved product's M number for image analysis
            const approved = qaProducts.filter(p => p.qa_status === 'approved');
            if (approved.length === 0) {
                status.textContent = '❌ No approved products to analyze';
                status.style.color = '#e74c3c';
                return;
            }
            
            const mNumber = approved[0].m_number;
            btn.disabled = true;
            btn.textContent = '⏳ Analyzing...';
            status.textContent = 'Sending image to AI...';
            status.style.color = '#666';
            
            try {
                const response = await fetch(`/api/ai/describe-product?m_number=${mNumber}`, { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('product-theme').value = data.description;
                    document.getElementById('product-use-cases').value = data.use_cases;
                    status.textContent = '✓ Generated successfully';
                    status.style.color = '#27ae60';
                } else {
                    status.textContent = '❌ ' + (data.error || 'Failed to generate');
                    status.style.color = '#e74c3c';
                }
            } catch (e) {
                console.error('Auto-generate error:', e);
                status.textContent = '❌ Error: ' + e.message;
                status.style.color = '#e74c3c';
            }
            
            btn.disabled = false;
            btn.textContent = '🤖 Auto-generate with AI';
        }
        
        async function startPipeline() {
            const theme = document.getElementById('product-theme').value.trim();
            const useCases = document.getElementById('product-use-cases').value.trim();
            
            if (!theme) {
                alert('Please enter a signage theme/description for AI content generation.');
                document.getElementById('product-theme').focus();
                return;
            }
            
            hidePipelineConfig();
            await finalizeAllApproved(theme, useCases);
        }
        
        async function finalizeAllApproved(theme = '', useCases = '') {
            const approved = qaProducts.filter(p => p.qa_status === 'approved');
            if (approved.length === 0) {
                alert('No approved products to finalize.');
                return;
            }
            
            const btn = document.getElementById('finalize-all-btn');
            const statusDiv = document.getElementById('pipeline-status');
            const logDiv = document.getElementById('pipeline-log');
            const productsDiv = document.getElementById('pipeline-products');
            const stepSpan = document.getElementById('pipeline-step');
            const percentSpan = document.getElementById('pipeline-percent');
            const progressBar = document.getElementById('pipeline-bar');
            const flatfileDiv = document.getElementById('pipeline-flatfile');
            const flatfileName = document.getElementById('flatfile-name');
            
            btn.disabled = true;
            btn.textContent = '⏳ Running Pipeline...';
            statusDiv.style.display = 'block';
            logDiv.innerHTML = '';
            flatfileDiv.style.display = 'none';
            
            // Reset step indicators
            document.getElementById('step-images-tick').textContent = '⏳';
            document.getElementById('step-lifestyle-tick').textContent = '⏳';
            document.getElementById('step-content-tick').textContent = '⏳';
            
            // Build product grid
            productsDiv.innerHTML = approved.map(p => `
                <div class="pipeline-product" id="pp-${p.m_number}" style="background: white; border: 1px solid #ddd; border-radius: 6px; padding: 10px;">
                    <div style="font-weight: bold; margin-bottom: 8px;">${p.m_number}</div>
                    <div style="font-size: 11px; color: #666; margin-bottom: 8px;">${(p.description || '').substring(0, 25)}...</div>
                    <div style="display: flex; gap: 5px; flex-wrap: wrap;">
                        <span class="status-badge" id="img-${p.m_number}" style="padding: 2px 6px; border-radius: 3px; font-size: 10px; background: #eee;">📷 Images</span>
                        ${p.lifestyle_image === 'yes' ? `<span class="status-badge" id="life-${p.m_number}" style="padding: 2px 6px; border-radius: 3px; font-size: 10px; background: #eee;">🏠 Lifestyle</span>` : ''}
                        <span class="status-badge" id="content-${p.m_number}" style="padding: 2px 6px; border-radius: 3px; font-size: 10px; background: #eee;">📝 Content</span>
                    </div>
                </div>
            `).join('');
            
            function log(msg) {
                logDiv.innerHTML += msg + '\\n';
                logDiv.scrollTop = logDiv.scrollHeight;
            }
            
            function setProgress(step, percent) {
                stepSpan.textContent = step;
                percentSpan.textContent = percent + '%';
                progressBar.style.width = percent + '%';
            }
            
            function markDone(id, success = true) {
                const el = document.getElementById(id);
                if (el) {
                    el.style.background = success ? '#d4edda' : '#f8d7da';
                    el.style.color = success ? '#155724' : '#721c24';
                }
            }
            
            try {
                // Step 1: Generate all images for approved products
                setProgress('Step 1/3: Generating product images...', 10);
                log('📦 Step 1/3: Generating all images for approved products...');
                const imgResponse = await fetch('/api/run/finalize-approved', { method: 'POST' });
                const imgReader = imgResponse.body.getReader();
                const decoder = new TextDecoder();
                while (true) {
                    const { done, value } = await imgReader.read();
                    if (done) break;
                    const text = decoder.decode(value);
                    log(text);
                    // Check for completed products
                    const match = text.match(/Processing (M\\d+)/);
                    if (match) markDone('img-' + match[1]);
                }
                approved.forEach(p => markDone('img-' + p.m_number));
                document.getElementById('step-images-tick').textContent = '✅';
                setProgress('Step 1/3: Images complete', 33);
                log('✓ Images complete');
                
                // Step 2: Generate lifestyle images
                setProgress('Step 2/3: Generating lifestyle images...', 40);
                log('\\n🖼️ Step 2/3: Generating lifestyle images...');
                const lifeResponse = await fetch('/api/run/lifestyle?theme=' + encodeURIComponent(theme), { method: 'POST' });
                const lifeReader = lifeResponse.body.getReader();
                while (true) {
                    const { done, value } = await lifeReader.read();
                    if (done) break;
                    const text = decoder.decode(value);
                    log(text);
                    const match = text.match(/Processing (M\\d+)/);
                    if (match) markDone('life-' + match[1]);
                }
                approved.filter(p => p.lifestyle_image === 'yes').forEach(p => markDone('life-' + p.m_number));
                document.getElementById('step-lifestyle-tick').textContent = '✅';
                setProgress('Step 2/3: Lifestyle images complete', 66);
                log('✓ Lifestyle images complete');
                
                // Step 3: Generate Amazon content and flatfile
                setProgress('Step 3/3: Generating Amazon content...', 70);
                log('\\n📄 Step 3/3: Generating Amazon content & flatfile...');
                const contentParams = new URLSearchParams({ theme: theme, use_cases: useCases });
                const contentResponse = await fetch('/api/run/content?' + contentParams.toString(), { method: 'POST' });
                const contentReader = contentResponse.body.getReader();
                while (true) {
                    const { done, value } = await contentReader.read();
                    if (done) break;
                    const text = decoder.decode(value);
                    log(text);
                    const match = text.match(/Generating content for (M\\d+)/);
                    if (match) markDone('content-' + match[1]);
                    // Check for flatfile name
                    const flatMatch = text.match(/Saved flatfile to (.+\\.xlsx)/);
                    if (flatMatch) {
                        flatfileName.textContent = flatMatch[1];
                        flatfileDiv.style.display = 'block';
                    }
                }
                approved.forEach(p => markDone('content-' + p.m_number));
                document.getElementById('step-content-tick').textContent = '✅';
                setProgress('Pipeline Complete!', 100);
                log('✓ Content generation complete');
                
                log('\\n=== PIPELINE COMPLETE ===');
                btn.textContent = '✓ Pipeline Complete';
                
                // Fetch final status to get flatfile name
                const statusResp = await fetch('/api/pipeline/status');
                const status = await statusResp.json();
                if (status.flatfile) {
                    flatfileName.textContent = status.flatfile;
                    flatfileDiv.style.display = 'block';
                }
                
            } catch (e) {
                console.error('Pipeline error:', e);
                log('\\n❌ ERROR: ' + e.message);
                btn.textContent = '❌ Pipeline Error';
                setProgress('Error occurred', 0);
                progressBar.style.background = '#e74c3c';
            }
            
            setTimeout(() => { 
                btn.textContent = '📦 Finalize All Approved & Generate Content'; 
                btn.disabled = false; 
            }, 5000);
        }
        
        // Initialize
        refreshFlatfiles();
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, display_columns=DISPLAY_COLUMNS)


@app.route('/api/flatfiles')
def get_flatfiles():
    flatfiles_dir = APP_DIR / "003 FLATFILES"
    if flatfiles_dir.exists():
        files = [
            f.name for f in sorted(flatfiles_dir.glob("*.xlsm"))
            if not f.name.startswith("~$") and "_jpeg" not in f.name
        ]
        return jsonify({"flatfiles": files})
    return jsonify({"flatfiles": []})


@app.route('/api/products')
def get_products():
    csv_path = APP_DIR / "products.csv"
    products = []
    
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append(dict(row))
    
    return jsonify({"products": products})


@app.route('/api/products', methods=['POST'])
def save_products():
    try:
        data = request.json
        products = data.get('products', [])
        
        csv_path = APP_DIR / "products.csv"
        
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=PRODUCTS_COLUMNS)
            writer.writeheader()
            for product in products:
                # Ensure all columns exist
                row = {col: product.get(col, "") for col in PRODUCTS_COLUMNS}
                writer.writerow(row)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def stream_command(cmd):
    """Execute a command and stream its output."""
    # Environment variables are already loaded at app startup (lines 22-31)
    # Just copy them to the subprocess
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    
    # Add -u flag for unbuffered Python output if this is a Python command
    if 'python.exe' in cmd.lower():
        # Insert -u flag after python.exe
        cmd = cmd.replace('python.exe"', 'python.exe" -u')
    
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(APP_DIR),
        env=env,
    )
    
    for line in process.stdout:
        yield line
    
    process.wait()
    if process.returncode == 0:
        yield "\n=== SUCCESS ===\n"
    else:
        yield f"\n=== FAILED (exit code {process.returncode}) ===\n"


@app.route('/api/run/amazon', methods=['POST'])
def run_amazon():
    """Generate M folders and product images only (no content/lifestyle - that's done after QA)."""
    cmd = "python generate_images_v2.py --csv products.csv"
    return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/run/ebay', methods=['POST'])
def run_ebay():
    flatfile = request.args.get('flatfile', '')
    promote = request.args.get('promote', '0') == '1'
    dryrun = request.args.get('dryrun', '0') == '1'
    
    if not flatfile:
        return Response("Error: No flatfile specified\n", mimetype='text/plain')
    
    flatfile_path = f"003 FLATFILES\\{flatfile}"
    cmd = f'python generate_ebay_from_flatfile.py "{flatfile_path}"'
    
    if dryrun:
        cmd += " --dry-run"
    elif promote:
        cmd += " --promote --ad-rate 5.0"
    
    return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/run/etsy', methods=['POST'])
def run_etsy():
    flatfile = request.args.get('flatfile', '')
    
    if not flatfile:
        return Response("Error: No flatfile specified\n", mimetype='text/plain')
    
    flatfile_path = f"003 FLATFILES\\{flatfile}"
    product_name = flatfile.split()[0]
    output_path = f"003 FLATFILES\\{product_name}_shop_uploader.xlsx"
    
    cmd = f'python generate_etsy_shop_uploader.py --input "{flatfile_path}" --output "{output_path}"'
    
    return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/run/regenerate-pending', methods=['POST'])
def run_regenerate_pending():
    cmd = 'python generate_images_v2.py --csv products.csv --qa-filter pending'
    return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/run/single-product', methods=['POST'])
def run_single_product():
    """Run full Amazon pipeline for a single M number."""
    m_number = request.args.get('m_number', '')
    
    if not m_number:
        return Response("Error: No M number specified\n", mimetype='text/plain')
    
    cmd = (
        f'python generate_images_v2.py --csv products.csv --m-number {m_number} && '
        f'python generate_lifestyle_images.py --csv products.csv --m-number {m_number} && '
        f'python generate_amazon_content.py --csv products.csv --m-number {m_number} --upload-images --qa-filter all && '
        f'python copy_exports_to_shared.py --exports exports --m-numbers {m_number}'
    )
    return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/qa/products')
def get_qa_products():
    """Get products for QA review."""
    csv_path = APP_DIR / "products.csv"
    products = []
    
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append(dict(row))
    
    return jsonify({"products": products})


@app.route('/api/qa/save', methods=['POST'])
def save_qa_product():
    """Save QA status for a single product."""
    try:
        data = request.json
        m_number = data.get('m_number')
        qa_status = data.get('qa_status', 'pending')
        qa_comment = data.get('qa_comment', '')
        icon_scale = str(data.get('icon_scale', '1.0'))
        text_scale = str(data.get('text_scale', '1.0'))
        
        print(f"Saving {m_number}: icon_scale={icon_scale}, text_scale={text_scale}")
        
        csv_path = APP_DIR / "products.csv"
        
        # Read all products
        products = []
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get('m_number') == m_number:
                    row['qa_status'] = qa_status
                    row['qa_comment'] = qa_comment
                    row['icon_scale'] = icon_scale
                    row['text_scale'] = text_scale
                    print(f"Updated row: {row}")
                products.append(row)
        
        # Write back
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(products)
        
        return jsonify({"success": True, "icon_scale": icon_scale, "text_scale": text_scale})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/image/<m_number>/<image_num>')
def get_image(m_number, image_num):
    """Serve product images from exports folder."""
    from flask import send_file
    
    # Find the product folder
    exports_dir = APP_DIR / "exports"
    
    # Look for folder starting with m_number
    for folder in exports_dir.iterdir():
        if folder.is_dir() and folder.name.startswith(m_number):
            images_dir = folder / "002 Images"
            if images_dir.exists():
                # Try exact format: M1150 - 001.png
                img_path = images_dir / f"{m_number} - {image_num}.png"
                if img_path.exists():
                    return send_file(img_path, mimetype='image/png')
                
                # Find image matching the number pattern
                for img in sorted(images_dir.glob("*.png")):
                    # Match patterns like "M1150 - 001.png" or "001.png"
                    if f"- {image_num}" in img.name or img.name == f"{image_num}.png":
                        return send_file(img, mimetype='image/png')
    
    # Return placeholder SVG if not found
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="350" viewBox="0 0 400 350">
        <rect width="400" height="350" fill="#f0f0f0"/>
        <text x="200" y="170" text-anchor="middle" font-size="16" fill="#999">Image not found</text>
        <text x="200" y="195" text-anchor="middle" font-size="12" fill="#ccc">{m_number} - {image_num}</text>
    </svg>'''
    return Response(svg, mimetype='image/svg+xml')


@app.route('/api/run/regenerate-single', methods=['POST'])
def run_regenerate_single():
    """Regenerate images for a single product - much faster than full regeneration."""
    m_number = request.args.get('m_number', '')
    
    if not m_number:
        return Response("Error: No m_number specified\n", mimetype='text/plain')
    
    # Create a temporary CSV with just this product
    csv_path = APP_DIR / "products.csv"
    retry_path = APP_DIR / "products_single.csv"
    
    # Read the product
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = [row for row in reader if row.get('m_number') == m_number]
    
    if not rows:
        return Response(f"Error: Product {m_number} not found\n", mimetype='text/plain')
    
    # Write single product CSV
    with open(retry_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    # Run image generation for just this product - main image only for speed
    cmd = f'python generate_images_v2.py --csv products_single.csv --main-only'
    
    return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/run/finalize', methods=['POST'])
def run_finalize():
    """Generate ALL images (001-004) and master design file for an approved product."""
    m_number = request.args.get('m_number', '')
    
    if not m_number:
        return Response("Error: No m_number specified\n", mimetype='text/plain')
    
    # Create a temporary CSV with just this product
    csv_path = APP_DIR / "products.csv"
    retry_path = APP_DIR / "products_single.csv"
    
    # Read the product
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = [row for row in reader if row.get('m_number') == m_number]
    
    if not rows:
        return Response(f"Error: Product {m_number} not found\n", mimetype='text/plain')
    
    # Write single product CSV
    with open(retry_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    # Run FULL image generation (all images + master design file)
    cmd = f'python generate_images_v2.py --csv products_single.csv'
    
    return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/run/finalize-approved', methods=['POST'])
def run_finalize_approved():
    """Generate ALL images for all approved products."""
    csv_path = APP_DIR / "products.csv"
    approved_path = APP_DIR / "products_approved.csv"
    
    # Read all approved products
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = [row for row in reader if row.get('qa_status') == 'approved']
    
    if not rows:
        return Response("No approved products found\n", mimetype='text/plain')
    
    # Write approved products CSV
    with open(approved_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    # Run FULL image generation for all approved products
    cmd = f'python generate_images_v2.py --csv products_approved.csv'
    
    return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/run/lifestyle', methods=['POST'])
def run_lifestyle():
    """Generate lifestyle images for approved products."""
    theme = request.args.get('theme', '')
    # Pass theme as sign-text override for better context
    # Always use --force to regenerate with new theme
    cmd = f'python generate_lifestyle_images.py --csv products_approved.csv --force'
    if theme:
        cmd += f' --sign-text "{theme}"'
    return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/run/lifestyle-single', methods=['POST'])
def run_lifestyle_single():
    """Generate lifestyle image for a single product."""
    m_number = request.args.get('m_number', '')
    if not m_number:
        return Response("Error: No M number specified\n", mimetype='text/plain')
    
    cmd = f'python generate_lifestyle_images.py --csv products.csv --m-number {m_number} --force --skip-qa-check'
    return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/ai/describe-product', methods=['POST'])
def ai_describe_product():
    """Use Claude Vision to analyze product image and generate description."""
    import base64
    import anthropic
    
    m_number = request.args.get('m_number', '')
    if not m_number:
        return jsonify({"success": False, "error": "No M number specified"})
    
    # Find the product image
    exports_dir = APP_DIR / "exports"
    image_path = None
    
    # Search for M folder
    for folder in exports_dir.iterdir():
        if folder.is_dir() and folder.name.startswith(m_number + " "):
            images_dir = folder / "002 Images"
            if images_dir.exists():
                # Get first image (001.png)
                for img in sorted(images_dir.glob("*.png")):
                    image_path = img
                    break
            break
    
    if not image_path or not image_path.exists():
        return jsonify({"success": False, "error": f"No image found for {m_number}"})
    
    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"success": False, "error": "ANTHROPIC_API_KEY not set"})
    
    try:
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")
        
        # Call Claude Vision
        client = anthropic.Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": """Analyze this signage product image and provide:

1. DESCRIPTION: A clear 1-2 sentence description of what this sign is for and its purpose. Focus on the message/warning it conveys.

2. USE_CASES: A comma-separated list of 4-6 specific locations or settings where this sign would be used.

Respond in this exact format:
DESCRIPTION: [your description]
USE_CASES: [comma-separated list]"""
                        }
                    ],
                }
            ],
        )
        
        # Parse response
        response_text = message.content[0].text
        description = ""
        use_cases = ""
        
        for line in response_text.split("\n"):
            if line.startswith("DESCRIPTION:"):
                description = line.replace("DESCRIPTION:", "").strip()
            elif line.startswith("USE_CASES:"):
                use_cases = line.replace("USE_CASES:", "").strip()
        
        return jsonify({
            "success": True,
            "description": description,
            "use_cases": use_cases
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/run/content', methods=['POST'])
def run_content():
    """Generate Amazon content and flatfile with timestamped name."""
    from datetime import datetime
    theme = request.args.get('theme', '')
    use_cases = request.args.get('use_cases', '')
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    flatfile_name = f"amazon_flatfile_{timestamp}.xlsx"
    
    # Check if async mode is enabled for this job type
    if ASYNC_JOBS_ENABLED and 'generate_amazon_content' in ASYNC_JOB_TYPES:
        # Async mode: enqueue job and return immediately
        payload = {
            'csv_path': 'products_approved.csv',
            'output_path': flatfile_name,
            'exports_path': 'exports',
            'brand': 'NorthByNorthEast',
            'theme': theme,
            'use_cases': use_cases,
            'upload_images': True,
            'qa_filter': 'all'
        }
        
        job_id = enqueue_job('generate_amazon_content', payload)
        
        return jsonify({
            'mode': 'async',
            'jobId': job_id,
            'statusUrl': f'/api/jobs/{job_id}',
            'message': 'Job queued successfully. Check status at the provided URL.'
        }), 202
    else:
        # Synchronous mode (existing behavior - unchanged)
        # Write theme/use_cases to temp files to avoid shell escaping issues
        theme_file = APP_DIR / "temp_theme.txt"
        use_cases_file = APP_DIR / "temp_use_cases.txt"
        
        with open(theme_file, "w", encoding="utf-8") as f:
            f.write(theme)
        with open(use_cases_file, "w", encoding="utf-8") as f:
            f.write(use_cases)
        
        cmd = f'"C:\\Users\\Admin\\AppData\\Local\\Python\\bin\\python.exe" generate_amazon_content.py --csv products_approved.csv --output {flatfile_name} --upload-images --theme-file temp_theme.txt --use-cases-file temp_use_cases.txt'
        return Response(stream_command(cmd), mimetype='text/plain')


@app.route('/api/pipeline/status', methods=['GET'])
def get_pipeline_status():
    """Get current pipeline status for progress display."""
    csv_path = APP_DIR / "products_approved.csv"
    
    products = []
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                m_number = row.get('m_number', '')
                lifestyle = row.get('lifestyle_image', '').lower() == 'yes'
                
                # Check what's been generated
                exports_dir = APP_DIR / "exports"
                images_done = False
                lifestyle_done = False
                
                for folder in exports_dir.iterdir():
                    if folder.is_dir() and folder.name.startswith(m_number):
                        images_dir = folder / "002 Images"
                        if images_dir.exists():
                            pngs = list(images_dir.glob("*.png"))
                            images_done = len(pngs) >= 4  # 001-004
                            lifestyle_done = any("005" in p.name or "lifestyle" in p.name.lower() for p in pngs)
                        break
                
                products.append({
                    "m_number": m_number,
                    "description": row.get('description', '')[:30],
                    "needs_lifestyle": lifestyle,
                    "images_done": images_done,
                    "lifestyle_done": lifestyle_done,
                    "content_done": False  # Updated after content generation
                })
    
    # Find latest flatfile by modification time (not alphabetically)
    flatfiles = list(APP_DIR.glob("amazon_flatfile_*.xlsx"))
    if flatfiles:
        latest_flatfile = max(flatfiles, key=lambda f: f.stat().st_mtime).name
    else:
        latest_flatfile = None
    
    return jsonify({
        "products": products,
        "flatfile": latest_flatfile
    })


# Layout bounds from CSV for live preview
LAYOUT_BOUNDS = {}

def load_layout_bounds():
    """Load layout bounds from CSV for live SVG preview."""
    global LAYOUT_BOUNDS
    csv_path = APP_DIR / "assets" / "layout_modes.csv"
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row.get("size", ""), row.get("orientation", "landscape"), 
                       row.get("layout_mode", ""), row.get("element", ""))
                LAYOUT_BOUNDS[key] = {
                    "x": float(row.get("x", 0)),
                    "y": float(row.get("y", 0)),
                    "width": float(row.get("width", 0)),
                    "height": float(row.get("height", 0)),
                }

load_layout_bounds()


@app.route('/api/preview/<m_number>')
def get_preview(m_number):
    """Generate a live SVG preview for a product - instant, no Inkscape needed."""
    try:
        # Get scale overrides from query params
        icon_scale = float(request.args.get('icon_scale', '1.0'))
        text_scale = float(request.args.get('text_scale', '1.0'))
        
        # Find product in CSV
        csv_path = APP_DIR / "products.csv"
        product = None
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('m_number') == m_number:
                    product = row
                    break
        
        if not product:
            # Return a placeholder SVG
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 150" width="400" height="300">
                <rect width="200" height="150" fill="#f0f0f0"/>
                <text x="100" y="75" text-anchor="middle" font-size="14" fill="#999">Product {m_number} not found</text>
            </svg>'''
            return Response(svg, mimetype='image/svg+xml')
        
        size = product.get('size', 'saville')
        orientation = product.get('orientation', 'landscape')
        layout_mode = product.get('layout_mode', 'A')
        icon_files = [f.strip() for f in (product.get('icon_files') or '').split(',') if f.strip()]
        text_lines = [
            product.get('text_line_1', ''),
            product.get('text_line_2', ''),
            product.get('text_line_3', ''),
        ]
        text_lines = [t for t in text_lines if t]
        
        # Size dimensions (canvas size in mm)
        sizes = {
            "saville": (153.4, 133.4),
            "dick": (170, 130),
            "barzan": (230, 175),
            "dracula": (140, 140),
            "baby_jesus": (330, 230),
        }
        width, height = sizes.get(size, (153.4, 133.4))
        
        # Get layout bounds
        icon_bounds = LAYOUT_BOUNDS.get((size, orientation, layout_mode, "icon"), {})
        text1_bounds = LAYOUT_BOUNDS.get((size, orientation, layout_mode, "text_1"), {})
        text2_bounds = LAYOUT_BOUNDS.get((size, orientation, layout_mode, "text_2"), {})
        
        # Scale SVG to fit nicely - make it 400px wide
        svg_width = 400
        svg_height = int(svg_width * height / width)
        
        # Build SVG
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{svg_width}" height="{svg_height}">
            <defs>
                <linearGradient id="signBg" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:#f8f8f8"/>
                    <stop offset="100%" style="stop-color:#e8e8e8"/>
                </linearGradient>
            </defs>
            <rect width="{width}" height="{height}" fill="#d0d0d0" rx="8"/>
            <rect x="20" y="15" width="{width-40}" height="{height-30}" fill="url(#signBg)" stroke="#bbb" stroke-width="1" rx="4"/>
        '''
        
        # Icon placeholder with scale
        if icon_bounds:
            orig_w = icon_bounds.get('width', 60)
            orig_h = icon_bounds.get('height', 60)
            iw = orig_w * icon_scale
            ih = orig_h * icon_scale
            # Center the scaled icon
            ix = icon_bounds.get('x', 50) + (orig_w - iw) / 2
            iy = icon_bounds.get('y', 50) + (orig_h - ih) / 2
            
            # Draw icon area with nice styling
            svg += f'''
                <rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" fill="#3498db" opacity="0.25" stroke="#3498db" stroke-width="2" rx="4"/>
                <text x="{ix + iw/2}" y="{iy + ih/2 - 5}" text-anchor="middle" dominant-baseline="middle" font-size="{max(8, min(14, iw/6))}" font-weight="bold" fill="#2980b9">ICON</text>
                <text x="{ix + iw/2}" y="{iy + ih/2 + 10}" text-anchor="middle" dominant-baseline="middle" font-size="{max(6, min(10, iw/8))}" fill="#3498db">{icon_scale}x</text>
            '''
        
        # Text lines with scale
        scaled_font = 10 * text_scale
        
        if text1_bounds:
            tx = text1_bounds.get('x', 30)
            ty = text1_bounds.get('y', 100)
            tw = text1_bounds.get('width', 90)
            th = text1_bounds.get('height', 20) * text_scale
            # Adjust y to center scaled text box
            ty_adj = ty + (text1_bounds.get('height', 20) - th) / 2
            
            text_content = text_lines[0] if text_lines else "TEXT LINE 1"
            svg += f'''
                <rect x="{tx}" y="{ty_adj}" width="{tw}" height="{th}" fill="#27ae60" opacity="0.2" stroke="#27ae60" stroke-width="1" rx="2"/>
                <text x="{tx + tw/2}" y="{ty_adj + th/2}" text-anchor="middle" dominant-baseline="middle" font-size="{scaled_font}" font-weight="bold" fill="#1e8449">{text_content[:25]}</text>
            '''
        
        if text2_bounds:
            tx = text2_bounds.get('x', 30)
            ty = text2_bounds.get('y', 120)
            tw = text2_bounds.get('width', 90)
            th = text2_bounds.get('height', 20) * text_scale
            ty_adj = ty + (text2_bounds.get('height', 20) - th) / 2
            
            text_content = text_lines[1] if len(text_lines) > 1 else "TEXT LINE 2"
            svg += f'''
                <rect x="{tx}" y="{ty_adj}" width="{tw}" height="{th}" fill="#27ae60" opacity="0.2" stroke="#27ae60" stroke-width="1" rx="2"/>
                <text x="{tx + tw/2}" y="{ty_adj + th/2}" text-anchor="middle" dominant-baseline="middle" font-size="{scaled_font}" font-weight="bold" fill="#1e8449">{text_content[:25]}</text>
            '''
        
        # Info bar at top
        svg += f'''
            <rect x="0" y="0" width="{width}" height="18" fill="#2c3e50" opacity="0.9"/>
            <text x="10" y="13" font-size="10" fill="white" font-weight="bold">{m_number} | {size} | Layout {layout_mode}</text>
            <text x="{width - 10}" y="13" font-size="9" fill="#3498db" text-anchor="end">Icon: {icon_scale}x | Text: {text_scale}x</text>
        '''
        
        svg += '</svg>'
        
        return Response(svg, mimetype='image/svg+xml')
    except Exception as e:
        # Return error SVG
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 150" width="400" height="300">
            <rect width="200" height="150" fill="#fee"/>
            <text x="100" y="70" text-anchor="middle" font-size="12" fill="#c00">Error: {str(e)[:30]}</text>
        </svg>'''
        return Response(svg, mimetype='image/svg+xml')


if __name__ == '__main__':
    import webbrowser
    
    # Register job API routes
    register_job_routes(app)
    
    # Use PORT environment variable for Render deployment, default to 5000 for local
    port = int(os.environ.get('PORT', 5000))
    # Use 0.0.0.0 for Render, 127.0.0.1 for local
    host = '0.0.0.0' if os.environ.get('RENDER') else '127.0.0.1'
    url = f"http://localhost:{port}"
    
    # Open browser after a short delay (only for local development)
    if not os.environ.get('RENDER'):
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    
    print(f"Starting Signage Publisher Web GUI at {url}")
    app.run(host=host, port=port, debug=False, threaded=True)
