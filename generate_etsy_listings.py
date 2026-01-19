#!/usr/bin/env python3
"""
Etsy Listings Generator

Reads products from CSV, generates Etsy-optimized content using Claude API,
and creates listings via Etsy Open API v3.
"""

import argparse
import csv
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import anthropic
import requests

from etsy_auth import EtsyAuth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# Etsy API base URL
ETSY_API_BASE = "https://openapi.etsy.com/v3/application"

# Product size dimensions in cm (length x width)
SIZE_DIMENSIONS_CM = {
    "saville": (11.5, 9.5),
    "dick": (15.0, 10.0),
    "barzan": (21.0, 14.8),
    "baby_jesus": (11.5, 9.5),
    "dracula": (11.5, 9.5),
    "a5": (21.0, 14.8),
    "a4": (29.7, 21.0),
    "a3": (42.0, 29.7),
}

# Size display names
SIZE_DISPLAY_NAMES = {
    "saville": "11.5 x 9.5 cm",
    "dick": "15 x 10 cm",
    "barzan": "21 x 14.8 cm",
    "baby_jesus": "11.5 x 9.5 cm",
    "dracula": "11.5 x 9.5 cm",
    "a5": "A5 (21 x 14.8 cm)",
    "a4": "A4 (29.7 x 21 cm)",
    "a3": "A3 (42 x 29.7 cm)",
}

# Color display names
COLOR_DISPLAY_NAMES = {
    "silver": "Silver",
    "white": "White",
    "gold": "Gold",
}

# Material descriptions
MATERIALS = {
    "1mm_aluminium": "1mm brushed aluminium with UV-printed design",
    "3mm_aluminium_composite": "3mm aluminium composite with UV-printed design",
    "acrylic": "premium acrylic with UV-printed design",
    "pvc": "durable PVC with UV-printed design",
}

# Mounting type descriptions
MOUNTING_TYPES = {
    "self_adhesive": {
        "description": "Self-adhesive backing (peel and stick) - NO drilling required",
        "title_suffix": "Self-Adhesive",
    },
    "pre_drilled": {
        "description": "Pre-drilled 4mm fixing holes for easy screw mounting",
        "title_suffix": "Pre-Drilled",
    },
    "magnetic": {
        "description": "Magnetic backing for repositionable mounting on metal surfaces",
        "title_suffix": "Magnetic",
    },
    "suction": {
        "description": "Suction cup mounting for glass and smooth surfaces",
        "title_suffix": "Suction Mount",
    },
}

# Etsy taxonomy ID for Signs (Home & Living > Home Decor > Signs)
# You may need to adjust this based on your specific category
ETSY_TAXONOMY_ID = 1031  # Signs category


@dataclass
class EtsyContent:
    """Generated Etsy listing content."""
    title: str
    description: str
    tags: list[str]
    materials: list[str]


@dataclass
class ProductData:
    """Product data for Etsy listing generation."""
    m_number: str
    description: str
    size: str
    color: str
    text_lines: list[str]
    material: str = "1mm_aluminium"
    mounting_type: str = "self_adhesive"
    image_paths: list[Path] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    etsy_listing_id: Optional[str] = None
    
    @property
    def mounting_info(self) -> dict:
        return MOUNTING_TYPES.get(self.mounting_type.lower(), MOUNTING_TYPES["self_adhesive"])
    
    @property
    def size_cm(self) -> tuple[float, float]:
        return SIZE_DIMENSIONS_CM.get(self.size.lower(), (11.5, 9.5))
    
    @property
    def material_display(self) -> str:
        return MATERIALS.get(self.material.lower(), self.material)
    
    @property
    def color_display(self) -> str:
        return COLOR_DISPLAY_NAMES.get(self.color.lower(), self.color.title())
    
    @property
    def size_display(self) -> str:
        return SIZE_DISPLAY_NAMES.get(self.size.lower(), self.size.title())


def generate_etsy_content_with_claude(
    product: ProductData,
    api_key: str,
) -> EtsyContent:
    """
    Generate Etsy-optimized content using Claude API.
    
    Args:
        product: Product data
        api_key: Anthropic API key
        
    Returns:
        EtsyContent with title, description, tags, and materials
    """
    client = anthropic.Anthropic(api_key=api_key)
    
    sign_text = " ".join([t for t in product.text_lines if t])
    length_cm, width_cm = product.size_cm
    mounting = product.mounting_info
    
    prompt = f"""Generate Etsy UK product listing content for a sign product.

PRODUCT DETAILS:
- Sign Text: "{sign_text}"
- Size: {length_cm} x {width_cm} cm
- Color/Finish: {product.color_display}
- Material: {product.material_display}
- Mounting: {mounting["description"]}
- Features: Weatherproof, UV-resistant print, rounded corners
- Use: Indoor/outdoor signage for offices, warehouses, car parks, shops, etc.

REQUIREMENTS:
1. TITLE (max 140 characters): Etsy titles should be descriptive and keyword-rich. Include sign type, size, material, and key feature. Format: "[Sign Text] Sign - [Size] [Material] [Mounting Type] - [Use Case]"

2. DESCRIPTION (200-400 words): Engaging, detailed description. Use line breaks for readability. Include:
   - Opening hook about the product
   - Material and quality details
   - Size specifications
   - Mounting method explanation
   - Use cases and applications
   - Care instructions
   - Shipping note (made to order)

3. TAGS (exactly 13): Etsy allows max 13 tags, each max 20 characters. Include:
   - Primary keywords (sign type)
   - Material keywords
   - Use case keywords
   - Style keywords
   - Gift-related if applicable

4. MATERIALS (3-5 items): List of materials used, e.g., "Brushed Aluminium", "UV Print", "Self-Adhesive Backing"

Respond in JSON format:
{{
    "title": "...",
    "description": "...",
    "tags": ["tag1", "tag2", ...],
    "materials": ["material1", "material2", ...]
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    response_text = message.content[0].text
    
    # Extract JSON from response
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if not json_match:
        raise ValueError(f"Could not parse JSON from Claude response: {response_text[:200]}")
    
    data = json.loads(json_match.group())
    
    # Enforce Etsy limits
    title = data["title"][:140]
    tags = [tag[:20] for tag in data["tags"][:13]]
    
    return EtsyContent(
        title=title,
        description=data["description"],
        tags=tags,
        materials=data["materials"][:5],
    )


def read_products_from_csv(csv_path: Path, qa_filter: str = "approved") -> list[ProductData]:
    """Read products from CSV file."""
    products = []
    skipped = 0
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            m_number = (row.get("m_number") or "").strip()
            if not m_number:
                continue
            
            qa_status = (row.get("qa_status") or "pending").strip().lower()
            if qa_filter != "all" and qa_status != qa_filter:
                skipped += 1
                continue
            
            text_lines = [
                (row.get("text_line_1") or "").strip(),
                (row.get("text_line_2") or "").strip(),
                (row.get("text_line_3") or "").strip(),
            ]
            
            material = (row.get("material") or "1mm_aluminium").strip().lower()
            mounting_type = (row.get("mounting_type") or "self_adhesive").strip().lower()
            
            # Check for existing Etsy listing ID
            etsy_listing_id = (row.get("etsy_listing_id") or "").strip() or None
            
            products.append(ProductData(
                m_number=m_number,
                description=(row.get("description") or "").strip(),
                size=(row.get("size") or "saville").strip().lower(),
                color=(row.get("color") or "silver").strip().lower(),
                text_lines=text_lines,
                material=material,
                mounting_type=mounting_type,
                etsy_listing_id=etsy_listing_id,
            ))
    
    if skipped > 0:
        logging.info("Skipped %d products (qa_status != '%s')", skipped, qa_filter)
    
    return products


def find_product_images(product: ProductData, exports_dir: Path) -> list[Path]:
    """Find product images in exports directory."""
    # Build expected folder name pattern
    folder_patterns = [
        f"{product.m_number} {product.description} {product.color_display} {product.size.title()}",
        f"{product.m_number}*",
    ]
    
    for pattern in folder_patterns:
        matches = list(exports_dir.glob(pattern))
        if matches:
            m_folder = matches[0]
            images_dir = m_folder / "002 Images"
            if images_dir.exists():
                return sorted(images_dir.glob("*.png"))
    
    return []


class EtsyClient:
    """Etsy API client for listing management."""
    
    def __init__(self, auth: EtsyAuth):
        self.auth = auth
        self.shop_id = auth.shop_id
        if not self.shop_id:
            raise ValueError("Shop ID not found - ensure authentication is complete")
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        files: Optional[dict] = None,
        retry_count: int = 3,
    ) -> dict:
        """Make authenticated API request with retry logic."""
        url = f"{ETSY_API_BASE}{endpoint}"
        headers = self.auth.get_headers()
        
        # Remove Content-Type for multipart/form-data (files)
        if files:
            del headers["Content-Type"]
        
        for attempt in range(retry_count):
            try:
                if method == "GET":
                    response = requests.get(url, headers=headers, params=data)
                elif method == "POST":
                    if files:
                        response = requests.post(url, headers=headers, data=data, files=files)
                    else:
                        response = requests.post(url, headers=headers, json=data)
                elif method == "PUT":
                    response = requests.put(url, headers=headers, json=data)
                elif method == "PATCH":
                    response = requests.patch(url, headers=headers, json=data)
                elif method == "DELETE":
                    response = requests.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logging.warning("Rate limited, waiting %d seconds...", retry_after)
                    time.sleep(retry_after)
                    continue
                
                if response.status_code >= 400:
                    logging.error("API error %d: %s", response.status_code, response.text)
                    if attempt < retry_count - 1:
                        time.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                
                return response.json() if response.text else {}
                
            except requests.RequestException as e:
                logging.error("Request failed: %s", e)
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
        
        return {}
    
    def get_shipping_profiles(self) -> list[dict]:
        """Get available shipping profiles for the shop."""
        result = self._request("GET", f"/shops/{self.shop_id}/shipping-profiles")
        return result.get("results", [])
    
    def create_draft_listing(
        self,
        title: str,
        description: str,
        price: float,
        quantity: int,
        tags: list[str],
        materials: list[str],
        shipping_profile_id: int,
        taxonomy_id: int = ETSY_TAXONOMY_ID,
    ) -> dict:
        """
        Create a draft listing on Etsy.
        
        Returns:
            API response with listing_id
        """
        data = {
            "title": title,
            "description": description,
            "price": price,
            "quantity": quantity,
            "taxonomy_id": taxonomy_id,
            "who_made": "i_did",
            "when_made": "made_to_order",
            "is_supply": False,
            "shipping_profile_id": shipping_profile_id,
            "tags": tags,
            "materials": materials,
            "should_auto_renew": True,
            "is_customizable": False,
            "is_digital": False,
            "type": "physical",
        }
        
        return self._request("POST", f"/shops/{self.shop_id}/listings", data=data)
    
    def upload_listing_image(
        self,
        listing_id: int,
        image_path: Path,
        rank: int = 1,
    ) -> dict:
        """
        Upload an image to a listing.
        
        Args:
            listing_id: Etsy listing ID
            image_path: Path to image file
            rank: Image position (1 = main image)
        """
        # Determine correct mimetype based on file extension
        suffix = image_path.suffix.lower()
        if suffix in (".jpg", ".jpeg"):
            mimetype = "image/jpeg"
        elif suffix == ".png":
            mimetype = "image/png"
        else:
            mimetype = "image/jpeg"  # Default to JPEG
        
        with image_path.open("rb") as f:
            files = {
                "image": (image_path.name, f, mimetype),
            }
            data = {
                "rank": rank,
            }
            return self._request(
                "POST",
                f"/shops/{self.shop_id}/listings/{listing_id}/images",
                data=data,
                files=files,
            )
    
    def upload_listing_image_from_url(
        self,
        listing_id: int,
        image_url: str,
        rank: int = 1,
    ) -> dict:
        """
        Upload an image to a listing from URL.
        
        Note: Etsy API doesn't directly support URL upload,
        so we download and re-upload.
        """
        import tempfile
        
        response = requests.get(image_url)
        response.raise_for_status()
        
        # Determine file extension from URL
        if image_url.lower().endswith(".jpg") or image_url.lower().endswith(".jpeg"):
            suffix = ".jpg"
        else:
            suffix = ".png"
        
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = Path(tmp.name)
        
        try:
            return self.upload_listing_image(listing_id, tmp_path, rank)
        finally:
            tmp_path.unlink()
    
    def publish_listing(self, listing_id: int) -> dict:
        """Publish a draft listing (make it active)."""
        data = {
            "state": "active",
        }
        return self._request("PUT", f"/shops/{self.shop_id}/listings/{listing_id}", data=data)
    
    def get_listing(self, listing_id: int) -> dict:
        """Get listing details."""
        return self._request("GET", f"/listings/{listing_id}")


def update_csv_with_listing_ids(
    csv_path: Path,
    products: list[ProductData],
) -> None:
    """Update CSV file with Etsy listing IDs."""
    # Read existing CSV
    rows = []
    fieldnames = []
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    
    # Add etsy_listing_id column if not present
    if "etsy_listing_id" not in fieldnames:
        fieldnames.append("etsy_listing_id")
    
    # Create lookup of listing IDs
    listing_ids = {p.m_number: p.etsy_listing_id for p in products if p.etsy_listing_id}
    
    # Update rows
    for row in rows:
        m_number = row.get("m_number", "")
        if m_number in listing_ids:
            row["etsy_listing_id"] = listing_ids[m_number]
    
    # Write back
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logging.info("Updated %s with Etsy listing IDs", csv_path)


def main():
    parser = argparse.ArgumentParser(description="Generate Etsy listings from product CSV")
    parser.add_argument("--csv", type=Path, default=Path("products.csv"), help="Input CSV file")
    parser.add_argument("--exports", type=Path, default=Path("exports"), help="Exports directory with product images")
    parser.add_argument("--price", type=float, default=9.99, help="Listing price in GBP")
    parser.add_argument("--quantity", type=int, default=999, help="Stock quantity")
    parser.add_argument("--qa-filter", type=str, default="approved", help="QA status filter")
    parser.add_argument("--dry-run", action="store_true", help="Generate content without creating listings")
    parser.add_argument("--skip-existing", action="store_true", help="Skip products with existing Etsy listing IDs")
    parser.add_argument("--publish", action="store_true", help="Publish listings (make active) after creation")
    parser.add_argument("--use-r2-urls", action="store_true", help="Use R2 image URLs instead of local files")
    args = parser.parse_args()
    
    # Get API keys
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    etsy_api_key = os.environ.get("ETSY_API_KEY")
    
    if not anthropic_key:
        logging.error("ANTHROPIC_API_KEY environment variable not set")
        return 1
    
    if not etsy_api_key and not args.dry_run:
        logging.error("ETSY_API_KEY environment variable not set")
        return 1
    
    # Initialize Etsy auth and client
    etsy_client = None
    shipping_profile_id = None
    
    if not args.dry_run:
        auth = EtsyAuth(api_key=etsy_api_key)
        
        if not auth.is_authenticated:
            logging.error("Not authenticated with Etsy. Run: python etsy_auth.py --authorize")
            return 1
        
        etsy_client = EtsyClient(auth)
        
        # Get shipping profile
        profiles = etsy_client.get_shipping_profiles()
        if not profiles:
            logging.error("No shipping profiles found. Create one in Etsy Shop Manager first.")
            return 1
        
        shipping_profile_id = profiles[0]["shipping_profile_id"]
        logging.info("Using shipping profile: %s (ID: %d)", profiles[0]["title"], shipping_profile_id)
    
    # Read products
    products = read_products_from_csv(args.csv, qa_filter=args.qa_filter)
    logging.info("Loaded %d products from %s", len(products), args.csv)
    
    # Filter out products with existing listings if requested
    if args.skip_existing:
        original_count = len(products)
        products = [p for p in products if not p.etsy_listing_id]
        logging.info("Filtered to %d products without existing Etsy listings", len(products))
    
    # Find images for each product
    for product in products:
        product.image_paths = find_product_images(product, args.exports)
        if product.image_paths:
            logging.info("Found %d images for %s", len(product.image_paths), product.m_number)
    
    # Process each product
    created_count = 0
    failed_count = 0
    
    for product in products:
        logging.info("Processing %s...", product.m_number)
        
        try:
            # Generate content
            content = generate_etsy_content_with_claude(product, anthropic_key)
            logging.info("  Title: %s", content.title[:60] + "..." if len(content.title) > 60 else content.title)
            
            if args.dry_run:
                logging.info("  [DRY RUN] Would create listing with %d tags, %d materials",
                           len(content.tags), len(content.materials))
                continue
            
            # Create draft listing
            result = etsy_client.create_draft_listing(
                title=content.title,
                description=content.description,
                price=args.price,
                quantity=args.quantity,
                tags=content.tags,
                materials=content.materials,
                shipping_profile_id=shipping_profile_id,
            )
            
            listing_id = result.get("listing_id")
            if not listing_id:
                logging.error("  Failed to create listing: %s", result)
                failed_count += 1
                continue
            
            product.etsy_listing_id = str(listing_id)
            logging.info("  Created draft listing: %d", listing_id)
            
            # Upload images
            images_to_upload = product.image_paths[:10]  # Etsy max 10 images
            for rank, img_path in enumerate(images_to_upload, 1):
                try:
                    etsy_client.upload_listing_image(listing_id, img_path, rank=rank)
                    logging.info("  Uploaded image %d: %s", rank, img_path.name)
                except Exception as e:
                    logging.warning("  Failed to upload image %s: %s", img_path.name, e)
            
            # Publish if requested
            if args.publish:
                try:
                    etsy_client.publish_listing(listing_id)
                    logging.info("  Published listing")
                except Exception as e:
                    logging.warning("  Failed to publish: %s", e)
            
            created_count += 1
            
            # Rate limiting - be nice to Etsy API
            time.sleep(1)
            
        except Exception as e:
            logging.error("  Failed to process %s: %s", product.m_number, e)
            failed_count += 1
    
    # Update CSV with listing IDs
    if not args.dry_run and created_count > 0:
        update_csv_with_listing_ids(args.csv, products)
    
    # Summary
    logging.info("=" * 50)
    logging.info("SUMMARY")
    logging.info("  Total products: %d", len(products))
    logging.info("  Created: %d", created_count)
    logging.info("  Failed: %d", failed_count)
    if args.dry_run:
        logging.info("  (Dry run - no listings created)")
    
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    exit(main())
