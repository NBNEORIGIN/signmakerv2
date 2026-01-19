#!/usr/bin/env python3
"""
QA Review Page Generator

Generates an HTML page for reviewing all product images before publishing.
"""

import argparse
import csv
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def generate_qa_review_page(
    csv_path: Path,
    exports_dir: Path,
    output_path: Path,
) -> bool:
    """
    Generate HTML review page for all products.
    
    Args:
        csv_path: Path to products CSV
        exports_dir: Path to exports directory
        output_path: Path for output HTML file
        
    Returns:
        True if successful
    """
    products = []
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            m_number = (row.get("m_number") or "").strip()
            if not m_number:
                continue
            
            products.append({
                "m_number": m_number,
                "description": (row.get("description") or "").strip(),
                "size": (row.get("size") or "").strip(),
                "color": (row.get("color") or "").strip(),
                "text_line_1": (row.get("text_line_1") or "").strip(),
                "orientation": (row.get("orientation") or "landscape").strip(),
                "qa_status": (row.get("qa_status") or "pending").strip().lower(),
                "qa_comment": (row.get("qa_comment") or "").strip(),
                "icon_scale": (row.get("icon_scale") or "").strip(),
                "text_scale": (row.get("text_scale") or "").strip(),
            })
    
    if not products:
        logging.error("No products found in CSV")
        return False
    
    # Build HTML
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='UTF-8'>",
        "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "  <title>Product QA Review</title>",
        "  <style>",
        "    * { box-sizing: border-box; }",
        "    body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }",
        "    h1 { text-align: center; color: #333; }",
        "    .summary { text-align: center; margin-bottom: 20px; padding: 15px; background: #fff; border-radius: 8px; }",
        "    .summary span { margin: 0 15px; padding: 5px 15px; border-radius: 4px; }",
        "    .pending-count { background: #fff3cd; color: #856404; }",
        "    .approved-count { background: #d4edda; color: #155724; }",
        "    .rejected-count { background: #f8d7da; color: #721c24; }",
        "    .product { background: #fff; margin-bottom: 30px; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
        "    .product-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #eee; }",
        "    .product-title { font-size: 1.4em; font-weight: bold; }",
        "    .product-meta { color: #666; font-size: 0.9em; }",
        "    .status { padding: 5px 15px; border-radius: 4px; font-weight: bold; text-transform: uppercase; font-size: 0.8em; }",
        "    .status-pending { background: #fff3cd; color: #856404; }",
        "    .status-approved { background: #d4edda; color: #155724; }",
        "    .status-rejected { background: #f8d7da; color: #721c24; }",
        "    .images { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }",
        "    .image-card { text-align: center; }",
        "    .image-card img { max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; transition: transform 0.2s; }",
        "    .image-card img:hover { transform: scale(1.02); }",
        "    .image-card p { margin: 8px 0 0; font-size: 0.85em; color: #666; }",
        "    .missing { background: #f8d7da; padding: 20px; text-align: center; color: #721c24; border-radius: 4px; }",
        "    .tuning-info { background: #fff3cd; padding: 10px 15px; border-radius: 4px; margin-bottom: 15px; font-size: 0.9em; }",
        "    .instructions { background: #e7f3ff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }",
        "    .instructions h3 { margin-top: 0; }",
        "    .instructions code { background: #fff; padding: 2px 6px; border-radius: 3px; }",
        "    footer { text-align: center; margin-top: 30px; color: #666; font-size: 0.85em; }",
        "  </style>",
        "</head>",
        "<body>",
        f"  <h1>Product QA Review</h1>",
    ]
    
    # Count statuses
    pending = sum(1 for p in products if p["qa_status"] == "pending")
    approved = sum(1 for p in products if p["qa_status"] == "approved")
    rejected = sum(1 for p in products if p["qa_status"] == "rejected")
    
    html_parts.append("  <div class='summary'>")
    html_parts.append(f"    <span class='pending-count'>Pending: {pending}</span>")
    html_parts.append(f"    <span class='approved-count'>Approved: {approved}</span>")
    html_parts.append(f"    <span class='rejected-count'>Rejected: {rejected}</span>")
    html_parts.append("  </div>")
    
    html_parts.append("  <div class='instructions'>")
    html_parts.append("    <h3>How to use this page:</h3>")
    html_parts.append("    <ol>")
    html_parts.append("      <li>Review each product's images below</li>")
    html_parts.append("      <li>Click any image to view full size</li>")
    html_parts.append("      <li>Update <code>qa_status</code> in products.csv:</li>")
    html_parts.append("      <ul>")
    html_parts.append("        <li><code>approved</code> - Ready to publish</li>")
    html_parts.append("        <li><code>rejected</code> - Needs fixes</li>")
    html_parts.append("        <li><code>pending</code> - Not yet reviewed</li>")
    html_parts.append("      </ul>")
    html_parts.append("      <li>Only <code>approved</code> products will be included in the Amazon flatfile</li>")
    html_parts.append("    </ol>")
    html_parts.append("  </div>")
    
    # Generate product cards
    for product in products:
        m_number = product["m_number"]
        description = product["description"]
        size = product["size"].title()
        color = product["color"].title()
        qa_status = product["qa_status"]
        qa_comment = product["qa_comment"]
        icon_scale = product["icon_scale"]
        text_scale = product["text_scale"]
        
        # Find the product folder
        folder_pattern = f"{m_number}*"
        matching_folders = list(exports_dir.glob(folder_pattern))
        
        status_class = f"status-{qa_status}"
        
        html_parts.append(f"  <div class='product' id='{m_number}'>")
        html_parts.append("    <div class='product-header'>")
        html_parts.append(f"      <div>")
        html_parts.append(f"        <span class='product-title'>{m_number} - {description}</span>")
        html_parts.append(f"        <div class='product-meta'>{size} | {color} | {product['text_line_1']}</div>")
        html_parts.append(f"      </div>")
        html_parts.append(f"      <span class='status {status_class}'>{qa_status}</span>")
        html_parts.append("    </div>")
        
        # Show tuning info if present
        tuning_parts = []
        if icon_scale:
            tuning_parts.append(f"Icon scale: {icon_scale}")
        if text_scale:
            tuning_parts.append(f"Text scale: {text_scale}")
        if qa_comment:
            tuning_parts.append(f"Comment: {qa_comment}")
        
        if tuning_parts:
            html_parts.append("    <div class='tuning-info'>")
            html_parts.append(f"      <strong>Tuning:</strong> {' | '.join(tuning_parts)}")
            html_parts.append("    </div>")
        
        if matching_folders:
            folder = matching_folders[0]
            images_dir = folder / "002 Images"
            
            html_parts.append("    <div class='images'>")
            
            image_labels = [
                ("001", "Main Image"),
                ("002", "Dimensions"),
                ("003", "Peel & Stick"),
                ("004", "Rear"),
                ("005", "Lifestyle"),
            ]
            
            for img_num, label in image_labels:
                img_files = list(images_dir.glob(f"*{img_num}*.png"))
                if img_files:
                    img_path = img_files[0]
                    # Use relative path from HTML file location
                    rel_path = img_path.relative_to(output_path.parent)
                    html_parts.append(f"      <div class='image-card'>")
                    html_parts.append(f"        <a href='{rel_path}' target='_blank'>")
                    html_parts.append(f"          <img src='{rel_path}' alt='{label}' loading='lazy'>")
                    html_parts.append(f"        </a>")
                    html_parts.append(f"        <p>{label}</p>")
                    html_parts.append(f"      </div>")
            
            html_parts.append("    </div>")
        else:
            html_parts.append(f"    <div class='missing'>Images not found. Run image generation first.</div>")
        
        html_parts.append("  </div>")
    
    html_parts.append(f"  <footer>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</footer>")
    html_parts.append("</body>")
    html_parts.append("</html>")
    
    # Write HTML file
    output_path.write_text("\n".join(html_parts), encoding="utf-8")
    logging.info("Generated QA review page: %s", output_path)
    logging.info("Products: %d total (%d pending, %d approved, %d rejected)", 
                 len(products), pending, approved, rejected)
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate QA review HTML page")
    parser.add_argument("--csv", type=Path, default=Path("products.csv"), help="Input CSV file")
    parser.add_argument("--exports", type=Path, default=Path("exports"), help="Exports directory")
    parser.add_argument("--output", type=Path, default=Path("qa_review.html"), help="Output HTML file")
    args = parser.parse_args()
    
    if not args.csv.exists():
        logging.error("CSV file not found: %s", args.csv)
        return 1
    
    if not args.exports.exists():
        logging.error("Exports directory not found: %s", args.exports)
        return 1
    
    if generate_qa_review_page(args.csv, args.exports, args.output):
        return 0
    return 1


if __name__ == "__main__":
    exit(main())
