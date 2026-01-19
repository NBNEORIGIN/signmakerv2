"""
QA Review Server - Interactive web interface for reviewing and approving product images.
Runs a local Flask server that allows updating qa_status and qa_comment directly from the browser.
"""

import csv
import logging
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

# Configuration
CSV_PATH = Path("products.csv")
EXPORTS_DIR = Path("exports")

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
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); 
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
    </style>
</head>
<body>
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
            Approve All Pending
        </button>
        <button onclick="location.reload()" style="background: #3498db; color: white;">
            Refresh
        </button>
    </div>
    
    <div class="grid">
        {% for product in products %}
        <div class="card {{ product.qa_status or 'pending' }}" data-m="{{ product.m_number }}" data-status="{{ product.qa_status or 'pending' }}">
            <div class="card-header">
                <h3>{{ product.m_number }} - {{ product.description }}</h3>
                <span class="size">{{ product.size }} / {{ product.color }}</span>
            </div>
            <div class="card-images">
                <img class="main-image" src="/image/{{ product.m_number }}/001" onclick="showModal(this.src)" alt="Main">
                <img src="/image/{{ product.m_number }}/002" onclick="showModal(this.src)" alt="Dimensions" onerror="this.style.display='none'">
                <img src="/image/{{ product.m_number }}/003" onclick="showModal(this.src)" alt="Peel & Stick" onerror="this.style.display='none'">
                <img src="/image/{{ product.m_number }}/004" onclick="showModal(this.src)" alt="Rear" onerror="this.style.display='none'">
                <img src="/image/{{ product.m_number }}/005" onclick="showModal(this.src)" alt="Lifestyle" onerror="this.style.display='none'">
            </div>
            <div class="card-body">
                <div class="product-info">
                    Layout: {{ product.layout_mode }} | 
                    {% if product.icon_scale %}Icon: {{ product.icon_scale }}x{% endif %}
                    {% if product.text_scale %}Text: {{ product.text_scale }}x{% endif %}
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
            </div>
        </div>
        {% endfor %}
    </div>
    
    <div class="toast" id="toast">Saved!</div>
    
    <div class="modal" id="modal" onclick="this.style.display='none'">
        <img id="modal-img" src="">
    </div>
    
    <script>
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
            const btn = card.querySelector('.save-btn');
            
            btn.disabled = true;
            btn.textContent = 'Saving...';
            
            try {
                const response = await fetch('/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ m_number: mNumber, qa_status: status, qa_comment: comment })
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
        
        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.style.display = 'block';
            setTimeout(() => toast.style.display = 'none', 2000);
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


def save_product(m_number: str, qa_status: str, qa_comment: str):
    """Update a product's qa_status and qa_comment in the CSV."""
    rows = []
    fieldnames = None
    
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row.get("m_number") == m_number:
                row["qa_status"] = qa_status
                row["qa_comment"] = qa_comment
            rows.append(row)
    
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logging.info("Updated %s: status=%s, comment=%s", m_number, qa_status, qa_comment[:50] if qa_comment else "")


@app.route("/")
def index():
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
    """Save product QA data."""
    data = request.json
    m_number = data.get("m_number")
    qa_status = data.get("qa_status", "pending")
    qa_comment = data.get("qa_comment", "")
    
    if not m_number:
        return jsonify({"error": "Missing m_number"}), 400
    
    save_product(m_number, qa_status, qa_comment)
    return jsonify({"success": True})


if __name__ == "__main__":
    logging.info("Starting QA Review Server at http://localhost:5000")
    logging.info("CSV: %s", CSV_PATH.absolute())
    logging.info("Exports: %s", EXPORTS_DIR.absolute())
    app.run(debug=False, port=5000)
