"""
QA Review Server v2 - Enhanced with Continue Pipeline and Real-time Scale Preview.

Features:
- Interactive web interface for reviewing and approving product images
- Real-time icon_scale and text_scale adjustment with live preview
- Continue Pipeline button to regenerate pending products and proceed
- Automatic CSV updates for qa_status, qa_comment, icon_scale, text_scale
"""

import csv
import logging
import subprocess
import sys
import threading
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

# Configuration
CSV_PATH = Path("products.csv")
EXPORTS_DIR = Path("exports")
PIPELINE_RUNNING = False
PIPELINE_LOG = []

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>QA Review - Amazon Publisher</title>
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px; background: #1a1a2e; color: #eee;
        }
        h1 { text-align: center; color: #fff; margin-bottom: 10px; }
        .stats { text-align: center; margin-bottom: 20px; color: #888; }
        .stats span { margin: 0 15px; }
        .stats .pending { color: #f39c12; }
        .stats .approved { color: #27ae60; }
        .stats .rejected { color: #e74c3c; }
        .filters { text-align: center; margin-bottom: 20px; }
        .filters button { 
            padding: 8px 16px; margin: 0 5px; border: none; border-radius: 4px;
            cursor: pointer; font-size: 14px;
        }
        .filters button.active { background: #3498db; color: white; }
        .filters button:not(.active) { background: #333; color: #aaa; }
        .grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); 
            gap: 20px; 
        }
        .card { 
            background: #16213e; border-radius: 8px; overflow: hidden;
            border: 2px solid transparent; transition: border-color 0.2s;
        }
        .card.pending { border-color: #f39c12; }
        .card.approved { border-color: #27ae60; }
        .card.rejected { border-color: #e74c3c; }
        .card-header { 
            padding: 10px 15px; background: #0f3460; 
            display: flex; justify-content: space-between; align-items: center;
        }
        .card-header h3 { margin: 0; font-size: 16px; }
        .card-header .size { color: #888; font-size: 12px; }
        .card-images {
            display: flex; flex-wrap: wrap; gap: 5px; padding: 10px;
            background: #ffffff; justify-content: center;
        }
        .card-images img {
            width: 80px; height: 80px; object-fit: contain;
            cursor: pointer; border: 1px solid #ddd; border-radius: 4px;
        }
        .card-images img.main-image {
            width: 100%; height: 200px; margin-bottom: 5px;
        }
        .card-body { padding: 15px; }
        .status-buttons { display: flex; gap: 8px; margin-bottom: 12px; }
        .status-buttons button {
            flex: 1; padding: 8px; border: none; border-radius: 4px;
            cursor: pointer; font-weight: bold; transition: all 0.2s;
        }
        .btn-pending { background: #f39c12; color: #000; }
        .btn-approved { background: #27ae60; color: #fff; }
        .btn-rejected { background: #e74c3c; color: #fff; }
        .status-buttons button:not(.selected) { opacity: 0.4; }
        .status-buttons button.selected { opacity: 1; transform: scale(1.05); }
        .comment-box { width: 100%; margin-bottom: 10px; }
        .comment-box textarea {
            width: 100%; padding: 10px; border: 1px solid #333; border-radius: 4px;
            background: #0a0a1a; color: #eee; font-size: 13px; resize: vertical;
            min-height: 60px;
        }
        .comment-box textarea:focus { outline: none; border-color: #3498db; }
        .save-btn {
            width: 100%; padding: 10px; background: #3498db; color: white;
            border: none; border-radius: 4px; cursor: pointer; font-weight: bold;
        }
        .save-btn:hover { background: #2980b9; }
        .save-btn:disabled { background: #555; cursor: not-allowed; }
        .save-btn.saved { background: #27ae60; }
        .product-info { font-size: 12px; color: #888; margin-bottom: 10px; }
        .toast {
            position: fixed; bottom: 20px; right: 20px; padding: 15px 25px;
            background: #27ae60; color: white; border-radius: 4px;
            display: none; z-index: 1000;
        }
        .toast.error { background: #e74c3c; }
        .modal {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.9); z-index: 1000; cursor: pointer;
            justify-content: center; align-items: center;
        }
        .modal img { max-width: 90%; max-height: 90%; object-fit: contain; }
        .bulk-actions {
            text-align: center; margin-bottom: 20px; padding: 15px;
            background: #16213e; border-radius: 8px;
        }
        .bulk-actions button {
            padding: 10px 20px; margin: 0 10px; border: none; border-radius: 4px;
            cursor: pointer; font-weight: bold;
        }
        .bulk-actions button:disabled {
            opacity: 0.5; cursor: not-allowed;
        }
        
        /* Scale controls */
        .scale-controls {
            display: flex; gap: 15px; margin-bottom: 12px;
            padding: 10px; background: #0a0a1a; border-radius: 4px;
        }
        .scale-group {
            flex: 1;
        }
        .scale-group label {
            display: block; font-size: 11px; color: #888; margin-bottom: 4px;
        }
        .scale-group input[type="range"] {
            width: 100%; cursor: pointer;
        }
        .scale-group .scale-value {
            font-size: 12px; color: #3498db; font-weight: bold;
        }
        .scale-buttons {
            display: flex; gap: 4px; margin-top: 4px;
        }
        .scale-buttons button {
            padding: 2px 8px; font-size: 11px; border: 1px solid #444;
            background: #222; color: #aaa; border-radius: 3px; cursor: pointer;
        }
        .scale-buttons button:hover {
            background: #333; color: #fff;
        }
        
        /* Pipeline status */
        .pipeline-status {
            position: fixed; top: 0; left: 0; right: 0;
            background: #0f3460; padding: 15px 20px;
            display: none; z-index: 999;
            box-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        .pipeline-status.active { display: block; }
        .pipeline-status h3 { margin: 0 0 10px 0; color: #fff; }
        .pipeline-log {
            max-height: 150px; overflow-y: auto;
            background: #0a0a1a; padding: 10px; border-radius: 4px;
            font-family: monospace; font-size: 12px; color: #aaa;
        }
        .pipeline-log .line { margin: 2px 0; }
        .pipeline-log .line.error { color: #e74c3c; }
        .pipeline-log .line.success { color: #27ae60; }
        
        /* Regenerate button */
        .regen-btn {
            padding: 6px 12px; background: #9b59b6; color: white;
            border: none; border-radius: 4px; cursor: pointer;
            font-size: 12px; margin-top: 8px;
        }
        .regen-btn:hover { background: #8e44ad; }
        .regen-btn:disabled { background: #555; cursor: not-allowed; }
    </style>
</head>
<body>
    <div class="pipeline-status" id="pipeline-status">
        <h3>🔄 Pipeline Running...</h3>
        <div class="pipeline-log" id="pipeline-log"></div>
    </div>
    
    <h1>QA Review - Amazon Publisher</h1>
    <div class="stats">
        <span>Total: <strong>{{ total }}</strong></span>
        <span class="pending">Pending: <strong id="pending-count">{{ pending }}</strong></span>
        <span class="approved">Approved: <strong id="approved-count">{{ approved }}</strong></span>
        <span class="rejected">Rejected: <strong id="rejected-count">{{ rejected }}</strong></span>
    </div>
    
    <div class="filters">
        <button class="active" onclick="filterCards('all')">All</button>
        <button onclick="filterCards('pending')">Pending</button>
        <button onclick="filterCards('approved')">Approved</button>
        <button onclick="filterCards('rejected')">Rejected</button>
    </div>
    
    <div class="bulk-actions">
        <button onclick="approveAllPending()" style="background: #27ae60; color: white;">
            ✓ Approve All Pending
        </button>
        <button onclick="regeneratePending()" style="background: #9b59b6; color: white;" id="regen-pending-btn">
            🔄 Regenerate Pending
        </button>
        <button onclick="continuePipeline()" style="background: #e67e22; color: white;" id="continue-btn">
            ▶ Continue Pipeline
        </button>
        <button onclick="location.reload()" style="background: #3498db; color: white;">
            ↻ Refresh
        </button>
    </div>
    
    <div class="grid">
        {% for product in products %}
        <div class="card {{ product.qa_status or 'pending' }}" 
             data-m="{{ product.m_number }}" 
             data-status="{{ product.qa_status or 'pending' }}"
             data-icon-scale="{{ product.icon_scale or '1.0' }}"
             data-text-scale="{{ product.text_scale or '1.0' }}">
            <div class="card-header">
                <h3>{{ product.m_number }} - {{ product.description }}</h3>
                <span class="size">{{ product.size }} / {{ product.color }}</span>
            </div>
            <div class="card-images">
                <img class="main-image" src="/image/{{ product.m_number }}/001?t={{ now }}" onclick="showModal(this.src)" alt="Main">
                <img src="/image/{{ product.m_number }}/002?t={{ now }}" onclick="showModal(this.src)" alt="Dimensions" onerror="this.style.display='none'">
                <img src="/image/{{ product.m_number }}/003?t={{ now }}" onclick="showModal(this.src)" alt="Peel & Stick" onerror="this.style.display='none'">
                <img src="/image/{{ product.m_number }}/004?t={{ now }}" onclick="showModal(this.src)" alt="Rear" onerror="this.style.display='none'">
                <img src="/image/{{ product.m_number }}/005?t={{ now }}" onclick="showModal(this.src)" alt="Lifestyle" onerror="this.style.display='none'">
            </div>
            <div class="card-body">
                <div class="product-info">
                    Layout: {{ product.layout_mode }} | Orientation: {{ product.orientation or 'landscape' }}
                </div>
                
                <!-- Scale Controls -->
                <div class="scale-controls">
                    <div class="scale-group">
                        <label>Icon Scale: <span class="scale-value" id="icon-val-{{ product.m_number }}">{{ product.icon_scale or '1.0' }}x</span></label>
                        <input type="range" min="0.5" max="2.0" step="0.05" 
                               value="{{ product.icon_scale or '1.0' }}"
                               id="icon-scale-{{ product.m_number }}"
                               oninput="updateScaleDisplay('{{ product.m_number }}', 'icon', this.value)">
                        <div class="scale-buttons">
                            <button onclick="setScale('{{ product.m_number }}', 'icon', 0.8)">0.8</button>
                            <button onclick="setScale('{{ product.m_number }}', 'icon', 1.0)">1.0</button>
                            <button onclick="setScale('{{ product.m_number }}', 'icon', 1.2)">1.2</button>
                            <button onclick="setScale('{{ product.m_number }}', 'icon', 1.5)">1.5</button>
                        </div>
                    </div>
                    <div class="scale-group">
                        <label>Text Scale: <span class="scale-value" id="text-val-{{ product.m_number }}">{{ product.text_scale or '1.0' }}x</span></label>
                        <input type="range" min="0.5" max="2.0" step="0.05" 
                               value="{{ product.text_scale or '1.0' }}"
                               id="text-scale-{{ product.m_number }}"
                               oninput="updateScaleDisplay('{{ product.m_number }}', 'text', this.value)">
                        <div class="scale-buttons">
                            <button onclick="setScale('{{ product.m_number }}', 'text', 0.8)">0.8</button>
                            <button onclick="setScale('{{ product.m_number }}', 'text', 1.0)">1.0</button>
                            <button onclick="setScale('{{ product.m_number }}', 'text', 1.35)">1.35</button>
                            <button onclick="setScale('{{ product.m_number }}', 'text', 1.5)">1.5</button>
                        </div>
                    </div>
                </div>
                
                <div class="status-buttons">
                    <button class="btn-pending {% if not product.qa_status or product.qa_status == 'pending' %}selected{% endif %}" 
                            onclick="setStatus('{{ product.m_number }}', 'pending', this)">Pending</button>
                    <button class="btn-approved {% if product.qa_status == 'approved' %}selected{% endif %}"
                            onclick="setStatus('{{ product.m_number }}', 'approved', this)">Approved</button>
                    <button class="btn-rejected {% if product.qa_status == 'rejected' %}selected{% endif %}"
                            onclick="setStatus('{{ product.m_number }}', 'rejected', this)">Rejected</button>
                </div>
                <div class="comment-box">
                    <textarea id="comment-{{ product.m_number }}" 
                              placeholder="QA comments (e.g., 'make icon bigger', 'move text down')..."
                    >{{ product.qa_comment or '' }}</textarea>
                </div>
                <button class="save-btn" onclick="saveProduct('{{ product.m_number }}')">Save Changes</button>
                <button class="regen-btn" onclick="regenerateSingle('{{ product.m_number }}')" id="regen-{{ product.m_number }}">
                    🔄 Regenerate This Product
                </button>
            </div>
        </div>
        {% endfor %}
    </div>
    
    <div class="toast" id="toast">Saved!</div>
    
    <div class="modal" id="modal" onclick="this.style.display='none'">
        <img id="modal-img" src="">
    </div>
    
    <script>
        function updateScaleDisplay(mNumber, type, value) {
            document.getElementById(`${type}-val-${mNumber}`).textContent = parseFloat(value).toFixed(2) + 'x';
            const card = document.querySelector(`[data-m="${mNumber}"]`);
            card.dataset[`${type}Scale`] = value;
        }
        
        function setScale(mNumber, type, value) {
            const slider = document.getElementById(`${type}-scale-${mNumber}`);
            slider.value = value;
            updateScaleDisplay(mNumber, type, value);
        }
        
        function setStatus(mNumber, status, btn) {
            const card = btn.closest('.card');
            card.querySelectorAll('.status-buttons button').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            card.dataset.status = status;
            card.className = 'card ' + status;
        }
        
        async function saveProduct(mNumber) {
            const card = document.querySelector(`[data-m="${mNumber}"]`);
            const status = card.dataset.status;
            const comment = document.getElementById(`comment-${mNumber}`).value;
            const iconScale = document.getElementById(`icon-scale-${mNumber}`).value;
            const textScale = document.getElementById(`text-scale-${mNumber}`).value;
            const btn = card.querySelector('.save-btn');
            
            btn.disabled = true;
            btn.textContent = 'Saving...';
            
            try {
                const response = await fetch('/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        m_number: mNumber, 
                        qa_status: status, 
                        qa_comment: comment,
                        icon_scale: iconScale,
                        text_scale: textScale
                    })
                });
                
                if (response.ok) {
                    btn.textContent = 'Saved!';
                    btn.classList.add('saved');
                    showToast('Saved ' + mNumber);
                    updateCounts();
                    setTimeout(() => {
                        btn.textContent = 'Save Changes';
                        btn.classList.remove('saved');
                        btn.disabled = false;
                    }, 1500);
                } else {
                    throw new Error('Save failed');
                }
            } catch (e) {
                btn.textContent = 'Error - Retry';
                btn.disabled = false;
            }
        }
        
        async function regenerateSingle(mNumber) {
            const btn = document.getElementById(`regen-${mNumber}`);
            btn.disabled = true;
            btn.textContent = '⏳ Regenerating...';
            
            // First save the current scale values
            await saveProduct(mNumber);
            
            try {
                const response = await fetch('/regenerate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ m_numbers: [mNumber] })
                });
                
                if (response.ok) {
                    showToast('Regenerating ' + mNumber + '...');
                    // Poll for completion
                    pollPipelineStatus(() => {
                        // Refresh images
                        refreshImages(mNumber);
                        btn.textContent = '🔄 Regenerate This Product';
                        btn.disabled = false;
                    });
                } else {
                    throw new Error('Regenerate failed');
                }
            } catch (e) {
                showToast('Error: ' + e.message, true);
                btn.textContent = '🔄 Regenerate This Product';
                btn.disabled = false;
            }
        }
        
        async function regeneratePending() {
            const btn = document.getElementById('regen-pending-btn');
            btn.disabled = true;
            btn.textContent = '⏳ Regenerating...';
            
            // Get all pending M numbers
            const pendingCards = document.querySelectorAll('.card.pending');
            const mNumbers = Array.from(pendingCards).map(c => c.dataset.m);
            
            if (mNumbers.length === 0) {
                showToast('No pending products to regenerate');
                btn.textContent = '🔄 Regenerate Pending';
                btn.disabled = false;
                return;
            }
            
            // Save all pending products first
            for (const m of mNumbers) {
                await saveProduct(m);
            }
            
            try {
                const response = await fetch('/regenerate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ m_numbers: mNumbers })
                });
                
                if (response.ok) {
                    showPipelineStatus();
                    pollPipelineStatus(() => {
                        hidePipelineStatus();
                        location.reload();
                    });
                } else {
                    throw new Error('Regenerate failed');
                }
            } catch (e) {
                showToast('Error: ' + e.message, true);
                btn.textContent = '🔄 Regenerate Pending';
                btn.disabled = false;
            }
        }
        
        async function continuePipeline() {
            const btn = document.getElementById('continue-btn');
            btn.disabled = true;
            btn.textContent = '⏳ Running...';
            
            try {
                const response = await fetch('/continue-pipeline', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    showPipelineStatus();
                    pollPipelineStatus(() => {
                        hidePipelineStatus();
                        showToast('Pipeline complete!');
                        btn.textContent = '▶ Continue Pipeline';
                        btn.disabled = false;
                    });
                } else {
                    const data = await response.json();
                    throw new Error(data.error || 'Pipeline failed');
                }
            } catch (e) {
                showToast('Error: ' + e.message, true);
                btn.textContent = '▶ Continue Pipeline';
                btn.disabled = false;
            }
        }
        
        function showPipelineStatus() {
            document.getElementById('pipeline-status').classList.add('active');
            document.body.style.paddingTop = '200px';
        }
        
        function hidePipelineStatus() {
            document.getElementById('pipeline-status').classList.remove('active');
            document.body.style.paddingTop = '20px';
        }
        
        async function pollPipelineStatus(onComplete) {
            const logDiv = document.getElementById('pipeline-log');
            let lastLength = 0;
            
            const poll = async () => {
                try {
                    const response = await fetch('/pipeline-status');
                    const data = await response.json();
                    
                    // Update log
                    if (data.log.length > lastLength) {
                        for (let i = lastLength; i < data.log.length; i++) {
                            const line = document.createElement('div');
                            line.className = 'line';
                            if (data.log[i].includes('ERROR')) line.className += ' error';
                            if (data.log[i].includes('success') || data.log[i].includes('Completed')) line.className += ' success';
                            line.textContent = data.log[i];
                            logDiv.appendChild(line);
                        }
                        logDiv.scrollTop = logDiv.scrollHeight;
                        lastLength = data.log.length;
                    }
                    
                    if (data.running) {
                        setTimeout(poll, 1000);
                    } else {
                        if (onComplete) onComplete();
                    }
                } catch (e) {
                    setTimeout(poll, 2000);
                }
            };
            
            poll();
        }
        
        function refreshImages(mNumber) {
            const card = document.querySelector(`[data-m="${mNumber}"]`);
            const images = card.querySelectorAll('img');
            const timestamp = Date.now();
            images.forEach(img => {
                const src = img.src.split('?')[0];
                img.src = src + '?t=' + timestamp;
            });
        }
        
        async function approveAllPending() {
            const pendingCards = document.querySelectorAll('.card.pending');
            for (const card of pendingCards) {
                const mNumber = card.dataset.m;
                card.querySelector('.btn-approved').click();
                await saveProduct(mNumber);
                await new Promise(r => setTimeout(r, 100));
            }
        }
        
        function filterCards(filter) {
            document.querySelectorAll('.filters button').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            
            document.querySelectorAll('.card').forEach(card => {
                if (filter === 'all' || card.dataset.status === filter) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
        
        function updateCounts() {
            const cards = document.querySelectorAll('.card');
            let pending = 0, approved = 0, rejected = 0;
            cards.forEach(card => {
                if (card.dataset.status === 'pending') pending++;
                else if (card.dataset.status === 'approved') approved++;
                else if (card.dataset.status === 'rejected') rejected++;
            });
            document.getElementById('pending-count').textContent = pending;
            document.getElementById('approved-count').textContent = approved;
            document.getElementById('rejected-count').textContent = rejected;
        }
        
        function showToast(msg, isError = false) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.className = 'toast' + (isError ? ' error' : '');
            toast.style.display = 'block';
            setTimeout(() => toast.style.display = 'none', 3000);
        }
        
        function showModal(src) {
            document.getElementById('modal-img').src = src;
            document.getElementById('modal').style.display = 'flex';
        }
    </script>
</body>
</html>
"""


def read_products():
    """Read products from CSV."""
    products = []
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("m_number"):
                products.append(row)
    return products


def save_product(m_number: str, qa_status: str, qa_comment: str, icon_scale: str = "", text_scale: str = ""):
    """Update a product's qa_status, qa_comment, and scale values in the CSV."""
    rows = []
    fieldnames = None
    
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row.get("m_number") == m_number:
                row["qa_status"] = qa_status
                row["qa_comment"] = qa_comment
                if icon_scale:
                    row["icon_scale"] = icon_scale
                if text_scale:
                    row["text_scale"] = text_scale
            rows.append(row)
    
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logging.info("Updated %s: status=%s, icon_scale=%s, text_scale=%s", 
                 m_number, qa_status, icon_scale, text_scale)


def create_retry_csv(m_numbers: list[str]) -> Path:
    """Create a temporary CSV with only the specified M numbers."""
    retry_path = Path("products_retry.csv")
    
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = [row for row in reader if row.get("m_number") in m_numbers]
    
    with retry_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    return retry_path


def run_pipeline_async(command: str, description: str):
    """Run a pipeline command asynchronously."""
    global PIPELINE_RUNNING, PIPELINE_LOG
    PIPELINE_RUNNING = True
    PIPELINE_LOG = [f"Starting: {description}"]
    
    def run():
        global PIPELINE_RUNNING, PIPELINE_LOG
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(CSV_PATH.parent)
            )
            
            for line in process.stdout:
                line = line.strip()
                if line:
                    PIPELINE_LOG.append(line)
                    logging.info(line)
            
            process.wait()
            
            if process.returncode == 0:
                PIPELINE_LOG.append("✓ Completed successfully")
            else:
                PIPELINE_LOG.append(f"✗ Failed with exit code {process.returncode}")
                
        except Exception as e:
            PIPELINE_LOG.append(f"ERROR: {str(e)}")
        finally:
            PIPELINE_RUNNING = False
    
    thread = threading.Thread(target=run)
    thread.start()


@app.route("/")
def index():
    import time
    products = read_products()
    pending = sum(1 for p in products if not p.get("qa_status") or p.get("qa_status") == "pending")
    approved = sum(1 for p in products if p.get("qa_status") == "approved")
    rejected = sum(1 for p in products if p.get("qa_status") == "rejected")
    
    return render_template_string(
        HTML_TEMPLATE,
        products=products,
        total=len(products),
        pending=pending,
        approved=approved,
        rejected=rejected,
        now=int(time.time()),
    )


@app.route("/image/<m_number>/<image_num>")
def serve_image(m_number, image_num):
    """Serve product image by number (001-005)."""
    for folder in EXPORTS_DIR.glob(f"{m_number}*"):
        images_dir = folder / "002 Images"
        if images_dir.exists():
            images = list(images_dir.glob(f"{m_number} - {image_num}*.png"))
            if images:
                return send_from_directory(images_dir, images[0].name)
    return "Image not found", 404


@app.route("/save", methods=["POST"])
def save():
    """Save product QA data including scale values."""
    data = request.json
    m_number = data.get("m_number")
    qa_status = data.get("qa_status", "pending")
    qa_comment = data.get("qa_comment", "")
    icon_scale = data.get("icon_scale", "")
    text_scale = data.get("text_scale", "")
    
    if not m_number:
        return jsonify({"error": "Missing m_number"}), 400
    
    save_product(m_number, qa_status, qa_comment, icon_scale, text_scale)
    return jsonify({"success": True})


@app.route("/regenerate", methods=["POST"])
def regenerate():
    """Regenerate images for specified products."""
    global PIPELINE_RUNNING
    
    if PIPELINE_RUNNING:
        return jsonify({"error": "Pipeline already running"}), 400
    
    data = request.json
    m_numbers = data.get("m_numbers", [])
    
    if not m_numbers:
        return jsonify({"error": "No products specified"}), 400
    
    # Create retry CSV
    retry_path = create_retry_csv(m_numbers)
    
    # Run image generation
    command = f'cmd /c "config.bat && python generate_images_v2.py --csv {retry_path.name}"'
    run_pipeline_async(command, f"Regenerating {len(m_numbers)} products")
    
    return jsonify({"success": True, "count": len(m_numbers)})


@app.route("/continue-pipeline", methods=["POST"])
def continue_pipeline():
    """Continue the pipeline: generate lifestyle images, upload to R2, create flatfile."""
    global PIPELINE_RUNNING
    
    if PIPELINE_RUNNING:
        return jsonify({"error": "Pipeline already running"}), 400
    
    products = read_products()
    pending = [p for p in products if not p.get("qa_status") or p.get("qa_status") == "pending"]
    
    if pending:
        return jsonify({
            "error": f"Cannot continue: {len(pending)} products still pending. Approve or reject all products first."
        }), 400
    
    approved = [p for p in products if p.get("qa_status") == "approved"]
    
    if not approved:
        return jsonify({"error": "No approved products to process"}), 400
    
    # Run the full pipeline continuation
    command = (
        'cmd /c "config.bat && '
        'python generate_lifestyle_images.py --csv products.csv && '
        'python generate_amazon_content.py --csv products.csv --upload-images --output amazon_flatfile.xlsx"'
    )
    run_pipeline_async(command, f"Continuing pipeline for {len(approved)} approved products")
    
    return jsonify({"success": True, "approved_count": len(approved)})


@app.route("/pipeline-status")
def pipeline_status():
    """Get current pipeline status."""
    return jsonify({
        "running": PIPELINE_RUNNING,
        "log": PIPELINE_LOG
    })


if __name__ == "__main__":
    logging.info("Starting QA Review Server v2 at http://localhost:5000")
    logging.info("CSV: %s", CSV_PATH.absolute())
    logging.info("Exports: %s", EXPORTS_DIR.absolute())
    logging.info("")
    logging.info("Features:")
    logging.info("  - Real-time icon/text scale adjustment")
    logging.info("  - Regenerate single product or all pending")
    logging.info("  - Continue Pipeline button (lifestyle + upload + flatfile)")
    app.run(debug=False, port=5000)
