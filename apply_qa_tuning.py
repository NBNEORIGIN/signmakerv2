#!/usr/bin/env python3
"""
AI-Assisted QA Tuning

Reads qa_comment from products.csv and uses Claude to interpret
the feedback and apply changes to the CSV.
"""

import argparse
import csv
import json
import logging
import os
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def interpret_qa_comment(product_row: dict, api_key: str) -> dict:
    """Use Claude to interpret the qa_comment and suggest CSV changes."""
    import anthropic
    
    qa_comment = product_row.get("qa_comment", "").strip()
    if not qa_comment:
        return {}
    
    current_state = {
        "m_number": product_row.get("m_number", ""),
        "description": product_row.get("description", ""),
        "text_line_1": product_row.get("text_line_1", ""),
        "text_line_2": product_row.get("text_line_2", ""),
        "text_line_3": product_row.get("text_line_3", ""),
        "layout_mode": product_row.get("layout_mode", ""),
        "icon_scale": product_row.get("icon_scale", ""),
        "text_scale": product_row.get("text_scale", ""),
    }
    
    prompt = f"""You are a product image QA assistant. Interpret this feedback and suggest CSV changes.

Current state: {json.dumps(current_state)}
Feedback: "{qa_comment}"

Fields you can modify:
- text_line_1, text_line_2, text_line_3: Text on sign
- icon_scale: Icon size (1.0=normal, 1.3=30% larger, 0.7=30% smaller)
- text_scale: Text size (1.0=normal, 1.5=50% larger)
- layout_mode: A-F (B=icon+1line, C=icon+multiline, D=text above, F=text above+below)

Respond with JSON only, including only changed fields:
{{"text_line_1": "value", "icon_scale": "1.2"}}
If unclear, respond: {{}}"""

    client = anthropic.Anthropic(api_key=api_key)
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.content[0].text.strip()
        if response_text.startswith("{"):
            end_idx = response_text.rfind("}") + 1
            return json.loads(response_text[:end_idx])
        return {}
    except Exception as e:
        logging.error("Failed to interpret: %s", e)
        return {}


def apply_tuning(csv_path: Path, api_key: str, dry_run: bool = False) -> int:
    """Read CSV, interpret qa_comments, and apply changes."""
    rows = []
    fieldnames = []
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = [dict(row) for row in reader]
    
    if not rows:
        logging.error("No products found")
        return 0
    
    updated_count = 0
    
    for row in rows:
        m_number = row.get("m_number", "").strip()
        qa_status = row.get("qa_status", "").strip().lower()
        qa_comment = row.get("qa_comment", "").strip()
        
        if not qa_comment or qa_status == "approved":
            continue
        
        logging.info("Processing %s: '%s'", m_number, qa_comment)
        suggestions = interpret_qa_comment(row, api_key)
        
        if suggestions:
            logging.info("  Suggestions: %s", suggestions)
            if not dry_run:
                for key, value in suggestions.items():
                    if key in fieldnames:
                        row[key] = str(value)
                row["qa_comment"] = f"[APPLIED] {qa_comment}"
                updated_count += 1
        else:
            logging.info("  No changes suggested")
    
    if not dry_run and updated_count > 0:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        logging.info("Updated %d products in %s", updated_count, csv_path)
    
    return updated_count


def main():
    parser = argparse.ArgumentParser(description="Apply AI-assisted QA tuning")
    parser.add_argument("--csv", type=Path, default=Path("products.csv"))
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    args = parser.parse_args()
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logging.error("ANTHROPIC_API_KEY not set")
        return 1
    
    if not args.csv.exists():
        logging.error("CSV not found: %s", args.csv)
        return 1
    
    updated = apply_tuning(args.csv, api_key, args.dry_run)
    logging.info("Done. %d products %s", updated, "would be updated" if args.dry_run else "updated")
    return 0


if __name__ == "__main__":
    exit(main())
