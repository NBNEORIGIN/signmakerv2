#!/usr/bin/env python3
"""
eBay Listings Generator

Generates eBay product listings using the Inventory API.
Reads from products.csv, generates content via Claude API, and creates listings on eBay.
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
from urllib.parse import quote
from collections import defaultdict

import anthropic
import requests

from ebay_auth import get_ebay_auth_from_env, EbayAuth
from ebay_setup_policies import load_policy_ids

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

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

# Color display names
COLOR_DISPLAY_NAMES = {
    "silver": "Silver",
    "white": "White",
    "gold": "Gold",
}

# Size display names - must be unique for variations
SIZE_DISPLAY_NAMES = {
    "saville": "Small (11.5 x 9.5 cm)",
    "dick": "Medium (15 x 10 cm)",
    "barzan": "Large (21 x 14.8 cm)",
    "baby_jesus": "Compact (11.5 x 9.5 cm)",
    "dracula": "Mini (11.5 x 9.5 cm)",
    "a5": "A5 (21 x 14.8 cm)",
    "a4": "A4 (29.7 x 21 cm)",
    "a3": "A3 (42 x 29.7 cm)",
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

# eBay category for signs - Business Signs (leaf category)
EBAY_CATEGORY_ID = "166675"  # Business, Office & Industrial > Retail & Shop Fitting > Business Signs


@dataclass
class EbayContent:
    """Generated eBay listing content."""
    title: str
    description: str
    aspects: dict


@dataclass
class ProductData:
    """Product data for eBay listing generation."""
    m_number: str
    description: str
    size: str
    color: str
    text_lines: list[str]
    material: str = "1mm_aluminium"
    mounting_type: str = "self_adhesive"
    image_urls: list[str] = field(default_factory=list)
    
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


def generate_content_with_claude(
    product: ProductData,
    api_key: str,
    brand_name: str = "NorthByNorthEast",
) -> EbayContent:
    """
    Generate eBay-optimized content using Claude API.
    """
    client = anthropic.Anthropic(api_key=api_key)
    
    sign_text = " ".join([t for t in product.text_lines if t])
    length_cm, width_cm = product.size_cm
    mounting = product.mounting_info
    
    prompt = f"""Generate eBay UK product listing content for a sign product.

PRODUCT DETAILS:
- Sign Text: "{sign_text}"
- Size: {length_cm} x {width_cm} cm
- Color/Finish: {product.color_display}
- Material: {product.material_display}
- Mounting: {mounting["description"]}
- Features: Weatherproof, UV-resistant print, rounded corners
- Use: Indoor/outdoor signage for offices, warehouses, car parks, shops, etc.

REQUIREMENTS:
1. TITLE (max 80 characters): Concise, keyword-rich. Format: "[Sign Text] Sign {length_cm}x{width_cm}cm {product.color_display} Aluminium {mounting["title_suffix"]}". eBay titles are shorter than Amazon.

2. DESCRIPTION (HTML format, 200-400 words): Professional product description with:
   - Brief intro paragraph
   - Key features as bullet list (<ul><li>)
   - Dimensions and specifications
   - Use cases
   - Brand mention: {brand_name}
   Use simple HTML: <p>, <ul>, <li>, <strong>, <br>

3. ITEM SPECIFICS (aspects): Key-value pairs for eBay's structured data:
   - Type: Safety Sign
   - Material: Aluminium
   - Colour: {product.color_display}
   - Mounting: {mounting["title_suffix"]}
   - Indoor/Outdoor: Indoor & Outdoor
   - Width: {width_cm}cm
   - Height: {length_cm}cm
   - Brand: {brand_name}
   - MPN: {product.m_number}

Respond in JSON format:
{{
    "title": "...",
    "description": "...",
    "aspects": {{
        "Type": "Safety Sign",
        "Material": "Aluminium",
        ...
    }}
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = message.content[0].text
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if not json_match:
        raise ValueError(f"Could not parse JSON from Claude response: {response_text[:200]}")
    
    data = json.loads(json_match.group())
    
    # Convert aspects to eBay format (values must be arrays)
    aspects = {}
    for key, value in data["aspects"].items():
        if isinstance(value, list):
            aspects[key] = value
        else:
            aspects[key] = [str(value)]
    
    return EbayContent(
        title=data["title"][:80],
        description=data["description"],
        aspects=aspects,
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
            
            products.append(ProductData(
                m_number=m_number,
                description=(row.get("description") or "").strip(),
                size=(row.get("size") or "saville").strip().lower(),
                color=(row.get("color") or "silver").strip().lower(),
                text_lines=text_lines,
                material=(row.get("material") or "1mm_aluminium").strip().lower(),
                mounting_type=(row.get("mounting_type") or "self_adhesive").strip().lower(),
            ))
    
    if skipped > 0:
        logging.info("Skipped %d products (qa_status != '%s')", skipped, qa_filter)
    
    return products


class EbayInventoryManager:
    """Manager for eBay Inventory API operations."""
    
    def __init__(self, auth: EbayAuth, marketplace_id: str = "EBAY_GB"):
        self.auth = auth
        self.marketplace_id = marketplace_id
        self.inventory_base = f"{auth.api_base}/sell/inventory/v1"
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
        content_language: str = "en-GB",
    ) -> dict:
        """Make authenticated API request."""
        url = f"{self.inventory_base}/{endpoint}"
        headers = self.auth.get_auth_headers()
        headers["Content-Language"] = content_language
        
        response = requests.request(
            method,
            url,
            headers=headers,
            json=data,
            params=params,
        )
        
        if response.status_code == 204:
            return {}
        
        if not response.ok:
            logging.error("API Error: %s %s", response.status_code, response.text)
            response.raise_for_status()
        
        return response.json() if response.text else {}
    
    def create_or_replace_inventory_item(
        self,
        sku: str,
        product: ProductData,
        content: EbayContent,
    ) -> None:
        """
        Create or replace an inventory item.
        
        This is the first step - creates the product in eBay's inventory system.
        """
        length_cm, width_cm = product.size_cm
        
        inventory_item = {
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": 100,  # Default stock quantity
                }
            },
            "condition": "NEW",
            "product": {
                "title": content.title,
                "description": content.description,
                "aspects": content.aspects,
                "imageUrls": product.image_urls[:12] if product.image_urls else [],
            },
        }
        
        self._make_request(
            "PUT",
            f"inventory_item/{sku}",
            data=inventory_item,
        )
        logging.info("Created/updated inventory item: %s", sku)
    
    def create_offer(
        self,
        sku: str,
        price: float,
        policy_ids: dict,
        category_id: str = EBAY_CATEGORY_ID,
        currency: str = "GBP",
    ) -> str:
        """
        Create an offer for an inventory item.
        
        Returns the offer ID.
        """
        offer = {
            "sku": sku,
            "marketplaceId": self.marketplace_id,
            "format": "FIXED_PRICE",
            "availableQuantity": 100,
            "categoryId": category_id,
            "listingDescription": None,  # Uses product description from inventory item
            "listingPolicies": {
                "fulfillmentPolicyId": policy_ids["fulfillmentPolicyId"],
                "returnPolicyId": policy_ids["returnPolicyId"],
                "paymentPolicyId": policy_ids["paymentPolicyId"],
            },
            "pricingSummary": {
                "price": {
                    "value": str(price),
                    "currency": currency,
                }
            },
            "merchantLocationKey": os.environ.get("EBAY_MERCHANT_LOCATION_KEY", "default"),
        }
        
        result = self._make_request("POST", "offer", data=offer)
        offer_id = result["offerId"]
        logging.info("Created offer: %s for SKU: %s", offer_id, sku)
        return offer_id
    
    def get_offers_by_sku(self, sku: str) -> list:
        """Get existing offers for a SKU."""
        try:
            result = self._make_request(
                "GET",
                "offer",
                params={"sku": sku, "marketplace_id": self.marketplace_id},
            )
            return result.get("offers", [])
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise
    
    def publish_offer(self, offer_id: str) -> str:
        """
        Publish an offer to make it a live listing.
        
        Returns the listing ID.
        """
        result = self._make_request("POST", f"offer/{offer_id}/publish")
        listing_id = result.get("listingId")
        logging.info("Published offer %s as listing: %s", offer_id, listing_id)
        return listing_id
    
    def create_listing(
        self,
        product: ProductData,
        content: EbayContent,
        price: float,
        policy_ids: dict,
    ) -> Optional[str]:
        """
        Complete flow to create a listing: inventory item -> offer -> publish.
        
        Returns the listing ID if successful.
        """
        sku = product.m_number
        
        # Step 1: Create/update inventory item
        self.create_or_replace_inventory_item(sku, product, content)
        
        # Step 2: Check for existing offers
        existing_offers = self.get_offers_by_sku(sku)
        
        if existing_offers:
            # Use existing offer
            offer_id = existing_offers[0]["offerId"]
            offer_status = existing_offers[0].get("status")
            
            if offer_status == "PUBLISHED":
                listing_id = existing_offers[0].get("listing", {}).get("listingId")
                logging.info("SKU %s already has published listing: %s", sku, listing_id)
                return listing_id
            
            logging.info("Found existing unpublished offer: %s", offer_id)
        else:
            # Step 3: Create new offer
            offer_id = self.create_offer(sku, price, policy_ids)
        
        # Step 4: Publish offer
        try:
            listing_id = self.publish_offer(offer_id)
            return listing_id
        except requests.HTTPError as e:
            logging.error("Failed to publish offer %s: %s", offer_id, e)
            if hasattr(e, 'response') and e.response is not None:
                logging.error("Response: %s", e.response.text)
            return None

    def create_or_replace_inventory_item_group(
        self,
        group_key: str,
        title: str,
        description: str,
        image_urls: list[str],
        aspects: dict,
        variation_specs: dict[str, list[str]],
        sku_list: list[str],
    ) -> None:
        """
        Create or replace an inventory item group for multi-variation listings.
        
        Args:
            group_key: Unique identifier for the group (e.g., base product name)
            title: Listing title for the group
            description: HTML description for the listing
            image_urls: Images for the main listing
            aspects: Common aspects shared by all variations
            variation_specs: Dict mapping aspect name to list of values (e.g., {"Size": ["Small", "Large"]})
            sku_list: List of SKUs to include in this group
        """
        # Build specifications with values
        specifications = []
        for aspect_name, values in variation_specs.items():
            specifications.append({
                "name": aspect_name,
                "values": values,
            })
        
        group_data = {
            "title": title,
            "description": description,
            "imageUrls": image_urls[:12],
            "aspects": aspects,
            "variantSKUs": sku_list,
            "variesBy": {
                "aspectsImageVariesBy": list(variation_specs.keys())[:1],  # First aspect varies images
                "specifications": specifications,
            },
        }
        
        self._make_request(
            "PUT",
            f"inventory_item_group/{group_key}",
            data=group_data,
        )
        logging.info("Created/updated inventory item group: %s with %d SKUs", group_key, len(sku_list))

    def withdraw_offer_by_sku(self, sku: str) -> bool:
        """
        Withdraw/end any published offers for a SKU.
        
        This is needed before adding a SKU to a variation group.
        """
        try:
            offers = self.get_offers_by_sku(sku)
            for offer in offers:
                if offer.get("status") == "PUBLISHED":
                    offer_id = offer["offerId"]
                    try:
                        self._make_request("POST", f"offer/{offer_id}/withdraw")
                        logging.info("Withdrew offer %s for SKU %s", offer_id, sku)
                    except requests.HTTPError as e:
                        logging.warning("Could not withdraw offer %s: %s", offer_id, e)
            return True
        except Exception as e:
            logging.error("Failed to withdraw offers for SKU %s: %s", sku, e)
            return False

    def delete_offer_by_sku(self, sku: str) -> bool:
        """
        Delete all offers for a SKU (must be withdrawn first).
        """
        try:
            offers = self.get_offers_by_sku(sku)
            for offer in offers:
                offer_id = offer["offerId"]
                try:
                    self._make_request("DELETE", f"offer/{offer_id}")
                    logging.info("Deleted offer %s for SKU %s", offer_id, sku)
                except requests.HTTPError as e:
                    logging.warning("Could not delete offer %s: %s", offer_id, e)
            return True
        except Exception as e:
            logging.error("Failed to delete offers for SKU %s: %s", sku, e)
            return False

    def publish_inventory_item_group(
        self,
        group_key: str,
        policy_ids: dict,
        category_id: str = EBAY_CATEGORY_ID,
    ) -> Optional[str]:
        """
        Publish an inventory item group as a multi-variation listing.
        
        Returns the listing ID if successful.
        """
        publish_data = {
            "inventoryItemGroupKey": group_key,
            "marketplaceId": self.marketplace_id,
            "listingPolicies": {
                "fulfillmentPolicyId": policy_ids["fulfillmentPolicyId"],
                "returnPolicyId": policy_ids["returnPolicyId"],
                "paymentPolicyId": policy_ids["paymentPolicyId"],
            },
            "categoryId": category_id,
        }
        
        try:
            result = self._make_request(
                "POST",
                "offer/publish_by_inventory_item_group",
                data=publish_data,
            )
            listing_id = result.get("listingId")
            logging.info("Published inventory group %s as listing: %s", group_key, listing_id)
            return listing_id
        except requests.HTTPError as e:
            logging.error("Failed to publish inventory group %s: %s", group_key, e)
            if hasattr(e, 'response') and e.response is not None:
                logging.error("Response: %s", e.response.text)
            return None

    def create_variation_listing(
        self,
        group_key: str,
        products: list[ProductData],
        contents: list[EbayContent],
        prices: dict[str, float],
        policy_ids: dict,
        brand: str,
    ) -> Optional[str]:
        """
        Create a multi-variation listing from a group of related products.
        
        Args:
            group_key: Unique identifier for the group
            products: List of ProductData for each variation
            contents: List of EbayContent for each variation
            prices: Dict mapping SKU to price
            policy_ids: eBay policy IDs
            brand: Brand name
            
        Returns the listing ID if successful.
        """
        if not products:
            return None
        
        # Collect all unique size and color values for variation specs
        size_values = set()
        color_values = set()
        
        # Step 0: Withdraw any existing single-SKU listings for these products
        for product in products:
            self.withdraw_offer_by_sku(product.m_number)
            self.delete_offer_by_sku(product.m_number)
        
        # Step 1: Create inventory items for each variation
        sku_list = []
        for product, content in zip(products, contents):
            sku = product.m_number
            
            # Get display values for size and color
            size_display = SIZE_DISPLAY_NAMES.get(product.size, product.size)
            color_display = COLOR_DISPLAY_NAMES.get(product.color, product.color.title())
            
            size_values.add(size_display)
            color_values.add(color_display)
            
            # Add variation-specific aspects
            variation_aspects = {
                "Size": [size_display],
                "Colour": [color_display],
            }
            content.aspects.update(variation_aspects)
            
            self.create_or_replace_inventory_item(sku, product, content)
            sku_list.append(sku)
        
        # Step 2: Create offers for each SKU (required before publishing group)
        for product in products:
            sku = product.m_number
            price = prices.get(sku, 9.99)
            try:
                # Check if offer already exists
                existing_offers = self.get_offers_by_sku(sku)
                if not existing_offers:
                    self.create_offer(sku, price, policy_ids)
            except requests.HTTPError as e:
                logging.warning("Could not create offer for %s: %s", sku, e)
        
        # Step 3: Determine common aspects (exclude variation aspects)
        first_content = contents[0]
        common_aspects = {k: v for k, v in first_content.aspects.items() 
                        if k not in ["Size", "Colour"]}
        
        # Step 4: Create inventory item group
        # Use first product's images for main listing
        first_product = products[0]
        
        # Generate group title (without size/color specifics)
        base_desc = first_product.description.replace("Self Adhesive", "").strip()
        group_title = f"{base_desc} Sign - Multiple Sizes & Colours - {MOUNTING_TYPES.get(first_product.mounting_type, {}).get('title_suffix', 'Self-Adhesive')}"
        if len(group_title) > 80:
            group_title = group_title[:77] + "..."
        
        # Combine all variation images
        all_images = []
        for product in products:
            all_images.extend(product.image_urls[:3])
        all_images = all_images[:12]  # eBay limit
        
        # Build variation specifications with actual values
        variation_specs = {
            "Size": sorted(list(size_values)),
            "Colour": sorted(list(color_values)),
        }
        
        self.create_or_replace_inventory_item_group(
            group_key=group_key,
            title=group_title,
            description=first_content.description,
            image_urls=all_images,
            aspects=common_aspects,
            variation_specs=variation_specs,
            sku_list=sku_list,
        )
        
        # Step 5: Publish the group
        listing_id = self.publish_inventory_item_group(group_key, policy_ids)
        return listing_id


def get_image_urls_from_exports(
    m_number: str,
    description: str,
    color: str,
    size: str,
    exports_dir: Path,
) -> list[str]:
    """
    Get image URLs from R2 (assumes images already uploaded by Amazon pipeline).
    
    Falls back to checking local exports folder for image filenames.
    If no local files found, constructs expected R2 URLs based on naming convention.
    """
    r2_public_url = os.environ.get("R2_PUBLIC_URL", "")
    if not r2_public_url:
        return []
    
    # Build expected folder name
    color_display = COLOR_DISPLAY_NAMES.get(color.lower(), color.title())
    folder_name = f"{m_number} {description} {color_display} {size.title()}"
    images_dir = exports_dir / folder_name / "002 Images"
    
    if images_dir.exists():
        urls = []
        for img_file in sorted(images_dir.glob("*.png")):
            url = f"{r2_public_url.rstrip('/')}/{img_file.name}"
            urls.append(url)
        if urls:
            return urls
    
    # Fallback: construct expected R2 URLs based on naming convention
    # Images are named like: M1098 - 001.png, M1098 - 002.png, etc.
    logging.info("Using constructed R2 URLs for %s", m_number)
    urls = []
    for i in range(1, 5):  # Up to 4 images
        filename = f"{m_number} - {i:03d}.png"
        url = f"{r2_public_url.rstrip('/')}/{quote(filename)}"
        urls.append(url)
    
    return urls


def group_products_for_variations(products: list[ProductData]) -> dict[str, list[ProductData]]:
    """
    Group products by their base description for variation listings.
    
    Products with the same description but different size/color become variations.
    Returns dict mapping group_key to list of products.
    """
    groups = defaultdict(list)
    
    for product in products:
        # Create group key from base description and mounting type
        # This groups all size/color variations together
        base_desc = product.description.replace("Self Adhesive", "").strip()
        group_key = f"{base_desc}_{product.mounting_type}".replace(" ", "_").lower()
        groups[group_key].append(product)
    
    return dict(groups)


def update_csv_with_ebay_ids(
    csv_path: Path,
    ebay_ids: dict[str, str],
) -> None:
    """Update products.csv with eBay listing IDs."""
    rows = []
    fieldnames = None
    
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        
        if "ebay_listing_id" not in fieldnames:
            fieldnames.append("ebay_listing_id")
        
        for row in reader:
            m_number = row.get("m_number", "").strip()
            if m_number in ebay_ids:
                row["ebay_listing_id"] = ebay_ids[m_number]
            rows.append(row)
    
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    logging.info("Updated %s with %d eBay listing IDs", csv_path, len(ebay_ids))


def main():
    parser = argparse.ArgumentParser(description="Generate eBay listings")
    parser.add_argument("--csv", type=Path, default=Path("products.csv"), help="Input CSV file")
    parser.add_argument("--exports", type=Path, default=Path("exports"), help="Exports directory")
    parser.add_argument("--price", type=float, default=9.99, help="Default price in GBP")
    parser.add_argument("--brand", type=str, default="NorthByNorthEast", help="Brand name")
    parser.add_argument("--qa-filter", type=str, default="approved", help="QA status filter")
    parser.add_argument("--dry-run", action="store_true", help="Generate content without creating listings")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of products to process")
    parser.add_argument("--variations", action="store_true", help="Create multi-variation listings (group by product type)")
    args = parser.parse_args()
    
    # Get API keys
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        logging.error("ANTHROPIC_API_KEY environment variable not set")
        return 1
    
    # Load policy IDs
    try:
        policy_ids = load_policy_ids()
    except FileNotFoundError as e:
        logging.error(str(e))
        return 1
    
    # Initialize eBay auth
    try:
        auth = get_ebay_auth_from_env()
        inventory_manager = EbayInventoryManager(auth, marketplace_id=policy_ids.get("marketplaceId", "EBAY_GB"))
    except ValueError as e:
        logging.error("eBay auth error: %s", e)
        return 1
    
    # Read products
    products = read_products_from_csv(args.csv, qa_filter=args.qa_filter)
    if args.limit:
        products = products[:args.limit]
    logging.info("Loaded %d products from %s", len(products), args.csv)
    
    # Process each product
    ebay_ids = {}
    success_count = 0
    error_count = 0
    
    if args.variations:
        # Group products for variation listings
        product_groups = group_products_for_variations(products)
        logging.info("Grouped into %d variation listings", len(product_groups))
        
        for group_idx, (group_key, group_products) in enumerate(product_groups.items(), 1):
            logging.info("\n[Group %d/%d] %s (%d variations)", 
                        group_idx, len(product_groups), group_key, len(group_products))
            
            try:
                # Get image URLs and generate content for each variation
                contents = []
                for product in group_products:
                    product.image_urls = get_image_urls_from_exports(
                        product.m_number,
                        product.description,
                        product.color,
                        product.size,
                        args.exports,
                    )
                    content = generate_content_with_claude(product, anthropic_key, args.brand)
                    contents.append(content)
                    logging.info("  - %s: %s (%s)", product.m_number, product.size, product.color)
                    time.sleep(0.5)  # Rate limit Claude API
                
                if args.dry_run:
                    logging.info("  [DRY RUN] Would create variation listing with %d SKUs", len(group_products))
                    success_count += len(group_products)
                    continue
                
                # Create variation listing
                prices = {p.m_number: args.price for p in group_products}
                listing_id = inventory_manager.create_variation_listing(
                    group_key=group_key,
                    products=group_products,
                    contents=contents,
                    prices=prices,
                    policy_ids=policy_ids,
                    brand=args.brand,
                )
                
                if listing_id:
                    for product in group_products:
                        ebay_ids[product.m_number] = listing_id
                    success_count += len(group_products)
                    logging.info("  Created variation listing: %s", listing_id)
                else:
                    error_count += len(group_products)
                
                time.sleep(2)  # Rate limiting between groups
                
            except Exception as e:
                logging.error("Failed to process group %s: %s", group_key, e)
                error_count += len(group_products)
    else:
        # Original single-listing mode
        for i, product in enumerate(products, 1):
            logging.info("[%d/%d] Processing %s...", i, len(products), product.m_number)
            
            try:
                # Get image URLs
                product.image_urls = get_image_urls_from_exports(
                    product.m_number,
                    product.description,
                    product.color,
                    product.size,
                    args.exports,
                )
                
                # Generate content
                content = generate_content_with_claude(product, anthropic_key, args.brand)
                logging.info("  Title: %s", content.title)
                
                if args.dry_run:
                    logging.info("  [DRY RUN] Would create listing")
                    success_count += 1
                    continue
                
                # Create listing
                listing_id = inventory_manager.create_listing(
                    product,
                    content,
                    args.price,
                    policy_ids,
                )
                
                if listing_id:
                    ebay_ids[product.m_number] = listing_id
                    success_count += 1
                else:
                    error_count += 1
                
                # Rate limiting - be gentle with eBay API
                time.sleep(1)
                
            except Exception as e:
                logging.error("Failed to process %s: %s", product.m_number, e)
                error_count += 1
    
    # Update CSV with eBay IDs
    if ebay_ids and not args.dry_run:
        update_csv_with_ebay_ids(args.csv, ebay_ids)
    
    # Summary
    logging.info("\n=== Summary ===")
    logging.info("Processed: %d products", len(products))
    logging.info("Success: %d", success_count)
    logging.info("Errors: %d", error_count)
    
    if ebay_ids:
        logging.info("\nCreated listings:")
        shown_listings = set()
        for m_number, listing_id in ebay_ids.items():
            if listing_id not in shown_listings:
                logging.info("  %s: %s", m_number, listing_id)
                shown_listings.add(listing_id)
    
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    exit(main())
