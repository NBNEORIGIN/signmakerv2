#!/usr/bin/env python3
"""
eBay Listings Generator from Amazon Flatfile

Generates eBay product listings using the Amazon flatfile as the source of truth.
This ensures consistency between Amazon and eBay listings while allowing for
platform-specific SEO and formatting adjustments.
"""

import argparse
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import pandas as pd
import requests

from ebay_auth import get_ebay_auth_from_env, EbayAuth
from ebay_setup_policies import load_policy_ids

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# eBay category for signs - Business Signs (leaf category)
EBAY_CATEGORY_ID = "166675"

# Default ad rate for Promoted Listings General strategy (Cost Per Sale)
# This is the percentage of sale price charged when item sells via ad click
DEFAULT_AD_RATE_PERCENT = "5.0"  # 5% ad fee on sale


@dataclass
class FlatfileProduct:
    """Product data from Amazon flatfile."""
    sku: str
    title: str
    description: str
    color: str
    size: str
    price: float
    image_urls: list[str] = field(default_factory=list)
    parent_sku: Optional[str] = None
    bullet_points: list[str] = field(default_factory=list)


def read_flatfile(flatfile_path: Path) -> tuple[Optional[dict], list[FlatfileProduct]]:
    """
    Read Amazon flatfile and extract parent and child products.
    
    Returns:
        Tuple of (parent_data dict or None, list of child FlatfileProduct)
    """
    df = pd.read_excel(flatfile_path, sheet_name='Template', header=2)
    
    parent_data = None
    children = []
    
    for _, row in df.iterrows():
        sku = str(row.get('item_sku', '')).strip()
        if not sku or sku == 'nan':
            continue
        
        parent_child = str(row.get('parent_child', '')).strip().lower()
        
        # Collect image URLs and URL-encode the filename part
        image_urls = []
        for img_col in ['main_image_url', 'other_image_url1', 'other_image_url2', 
                        'other_image_url3', 'other_image_url4', 'other_image_url5',
                        'other_image_url6', 'other_image_url7', 'other_image_url8']:
            url = row.get(img_col)
            if pd.notna(url) and str(url).startswith('http'):
                # URL-encode the filename to handle spaces
                url_str = str(url)
                if '/' in url_str:
                    base_url = url_str.rsplit('/', 1)[0]
                    filename = url_str.rsplit('/', 1)[1]
                    encoded_url = f"{base_url}/{quote(filename)}"
                    image_urls.append(encoded_url)
                else:
                    image_urls.append(url_str)
        
        # Collect bullet points
        bullet_points = []
        for i in range(1, 11):
            bp = row.get(f'bullet_point{i}')
            if pd.notna(bp) and str(bp).strip():
                bullet_points.append(str(bp).strip())
        
        if parent_child == 'parent':
            parent_data = {
                'sku': sku,
                'title': str(row.get('item_name', '')).strip(),
                'description': str(row.get('product_description', '')).strip(),
                'bullet_points': bullet_points,
            }
        else:
            # Child product
            price = row.get('list_price_with_tax')
            if pd.isna(price):
                price = 9.99  # Default price
            
            product = FlatfileProduct(
                sku=sku,
                title=str(row.get('item_name', '')).strip(),
                description=str(row.get('product_description', '')).strip(),
                color=str(row.get('color_name', '')).strip(),
                size=str(row.get('size_name', '')).strip(),
                price=float(price),
                image_urls=image_urls,
                parent_sku=str(row.get('parent_sku', '')).strip() if pd.notna(row.get('parent_sku')) else None,
                bullet_points=bullet_points,
            )
            children.append(product)
    
    logging.info("Read flatfile: %d children, parent=%s", len(children), parent_data.get('sku') if parent_data else None)
    return parent_data, children


class EbayMarketingManager:
    """Manager for eBay Marketing API (Promoted Listings)."""
    
    def __init__(self, auth: EbayAuth, marketplace_id: str = "EBAY_GB"):
        self.auth = auth
        self.marketplace_id = marketplace_id
        self.marketing_base = f"{auth.api_base}/sell/marketing/v1"
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Make authenticated API request."""
        url = f"{self.marketing_base}/{endpoint}"
        headers = self.auth.get_auth_headers()
        headers["Content-Language"] = "en-GB"
        
        response = requests.request(
            method,
            url,
            headers=headers,
            json=data,
            params=params,
        )
        
        if response.status_code == 201:
            # For POST requests that return location header
            location = response.headers.get("Location", "")
            campaign_id = location.split("/")[-1] if location else ""
            return {"campaignId": campaign_id, "location": location}
        
        if response.status_code == 204:
            return {}
        
        if not response.ok:
            logging.error("Marketing API Error: %s %s", response.status_code, response.text)
            response.raise_for_status()
        
        return response.json() if response.text else {}
    
    def create_general_campaign(
        self,
        campaign_name: str,
        ad_rate_percent: str = DEFAULT_AD_RATE_PERCENT,
    ) -> Optional[str]:
        """
        Create a Promoted Listings General strategy campaign (Cost Per Sale).
        
        Args:
            campaign_name: Name for the campaign
            ad_rate_percent: Percentage of sale charged as ad fee (e.g., "5.0" for 5%)
            
        Returns:
            Campaign ID if successful
        """
        # Get current time + 1 minute in eBay format (must be in future)
        from datetime import datetime, timezone, timedelta
        start_date = (datetime.now(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        campaign_data = {
            "campaignName": campaign_name,
            "marketplaceId": self.marketplace_id,
            "startDate": start_date,
            "fundingStrategy": {
                "fundingModel": "COST_PER_SALE",
                "bidPercentage": ad_rate_percent,
            },
        }
        
        try:
            result = self._make_request("POST", "ad_campaign", data=campaign_data)
            campaign_id = result.get("campaignId")
            logging.info("Created Promoted Listings campaign: %s (ID: %s) at %s%% ad rate",
                        campaign_name, campaign_id, ad_rate_percent)
            return campaign_id
        except requests.HTTPError as e:
            logging.error("Failed to create campaign: %s", e)
            return None
    
    def add_listing_to_campaign(
        self,
        campaign_id: str,
        listing_id: str,
        bid_percentage: str = DEFAULT_AD_RATE_PERCENT,
        inventory_reference_id: Optional[str] = None,
    ) -> bool:
        """
        Add a listing to an existing Promoted Listings campaign.
        
        Args:
            campaign_id: The campaign to add the listing to
            listing_id: The eBay listing ID to promote
            bid_percentage: Ad rate for this listing
            inventory_reference_id: Optional inventory item group key for variation listings
            
        Returns:
            True if successful
        """
        # Try inventory reference approach first for variation listings
        if inventory_reference_id:
            ad_data = {
                "inventoryReferenceId": inventory_reference_id,
                "inventoryReferenceType": "INVENTORY_ITEM_GROUP",
                "bidPercentage": bid_percentage,
            }
            try:
                self._make_request("POST", f"ad_campaign/{campaign_id}/create_ads_by_inventory_reference", data=ad_data)
                logging.info("Added inventory group %s to campaign %s", inventory_reference_id, campaign_id)
                return True
            except requests.HTTPError as e:
                logging.warning("Inventory reference approach failed, trying listing ID: %s", e)
        
        # Fallback to listing ID approach
        ad_data = {
            "listingId": listing_id,
            "bidPercentage": bid_percentage,
        }
        
        try:
            self._make_request("POST", f"ad_campaign/{campaign_id}/ad", data=ad_data)
            logging.info("Added listing %s to campaign %s", listing_id, campaign_id)
            return True
        except requests.HTTPError as e:
            logging.error("Failed to add listing to campaign: %s", e)
            return False
    
    def get_campaigns(self) -> list:
        """Get existing campaigns (all statuses)."""
        try:
            result = self._make_request(
                "GET",
                "ad_campaign",
                params={"marketplace_id": self.marketplace_id},
            )
            return result.get("campaigns", [])
        except requests.HTTPError:
            return []
    
    def find_or_create_general_campaign(
        self,
        campaign_name: str = "Auto Promoted Listings",
        ad_rate_percent: str = DEFAULT_AD_RATE_PERCENT,
    ) -> Optional[str]:
        """
        Find an existing general campaign or create a new one.
        
        Returns campaign ID.
        """
        # Check for existing campaigns
        campaigns = self.get_campaigns()
        for campaign in campaigns:
            if campaign.get("campaignName") == campaign_name:
                logging.info("Found existing campaign: %s (ID: %s)",
                            campaign_name, campaign.get("campaignId"))
                return campaign.get("campaignId")
        
        # Create new campaign
        return self.create_general_campaign(campaign_name, ad_rate_percent)


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
        title: str,
        description: str,
        image_urls: list[str],
        aspects: dict,
    ) -> None:
        """Create or replace an inventory item."""
        inventory_item = {
            "availability": {
                "shipToLocationAvailability": {
                    "quantity": 100,
                }
            },
            "condition": "NEW",
            "product": {
                "title": title[:80],  # eBay title limit
                "description": description,
                "aspects": aspects,
                "imageUrls": image_urls[:12] if image_urls else [],
            },
        }
        
        self._make_request("PUT", f"inventory_item/{sku}", data=inventory_item)
        logging.info("Created/updated inventory item: %s", sku)
    
    def get_offers_by_sku(self, sku: str) -> list:
        """Get existing offers for a SKU."""
        try:
            result = self._make_request(
                "GET", "offer",
                params={"sku": sku, "marketplace_id": self.marketplace_id},
            )
            return result.get("offers", [])
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return []
            raise
    
    def withdraw_offer_by_sku(self, sku: str) -> bool:
        """Withdraw any published offers for a SKU."""
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
        """Delete all offers for a SKU."""
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
    
    def create_offer(
        self,
        sku: str,
        price: float,
        policy_ids: dict,
        category_id: str = EBAY_CATEGORY_ID,
    ) -> str:
        """Create an offer for an inventory item."""
        offer = {
            "sku": sku,
            "marketplaceId": self.marketplace_id,
            "format": "FIXED_PRICE",
            "availableQuantity": 100,
            "categoryId": category_id,
            "listingPolicies": {
                "fulfillmentPolicyId": policy_ids["fulfillmentPolicyId"],
                "returnPolicyId": policy_ids["returnPolicyId"],
                "paymentPolicyId": policy_ids["paymentPolicyId"],
            },
            "pricingSummary": {
                "price": {
                    "value": str(price),
                    "currency": "GBP",
                }
            },
            "merchantLocationKey": os.environ.get("EBAY_MERCHANT_LOCATION_KEY", "default"),
        }
        
        result = self._make_request("POST", "offer", data=offer)
        offer_id = result["offerId"]
        logging.info("Created offer: %s for SKU: %s at £%.2f", offer_id, sku, price)
        return offer_id
    
    def delete_inventory_item_group(self, group_key: str) -> bool:
        """Delete an inventory item group."""
        try:
            self._make_request("DELETE", f"inventory_item_group/{group_key}")
            logging.info("Deleted inventory item group: %s", group_key)
            return True
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return True  # Already doesn't exist
            logging.warning("Could not delete inventory group %s: %s", group_key, e)
            return False

    def create_or_replace_inventory_item_group(
        self,
        group_key: str,
        title: str,
        description: str,
        image_urls: list[str],
        aspects: dict,
        variation_specs: dict[str, list[str]],
        sku_list: list[str],
        variant_images: Optional[list[dict]] = None,
    ) -> None:
        """
        Create or replace an inventory item group for multi-variation listings.
        
        Args:
            variant_images: List of dicts mapping variation values to images, e.g.:
                [{"value": "Silver", "imageUrls": ["url1", "url2"]}, ...]
        """
        specifications = []
        for aspect_name, values in variation_specs.items():
            specifications.append({
                "name": aspect_name,
                "values": values,
            })
        
        group_data = {
            "title": title[:80],
            "description": description,
            "imageUrls": image_urls[:12],
            "aspects": aspects,
            "variantSKUs": sku_list,
            "variesBy": {
                "aspectsImageVariesBy": ["Size"],  # Images vary by size (each size has dimension annotations)
                "specifications": specifications,
            },
        }
        
        # Add variant image mapping if provided
        if variant_images:
            group_data["variantSKUs"] = sku_list
            group_data["variesBy"]["variantImages"] = variant_images
        
        self._make_request("PUT", f"inventory_item_group/{group_key}", data=group_data)
        logging.info("Created/updated inventory item group: %s with %d SKUs", group_key, len(sku_list))
    
    def publish_inventory_item_group(
        self,
        group_key: str,
        policy_ids: dict,
        category_id: str = EBAY_CATEGORY_ID,
    ) -> Optional[str]:
        """Publish an inventory item group as a multi-variation listing."""
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
            result = self._make_request("POST", "offer/publish_by_inventory_item_group", data=publish_data)
            listing_id = result.get("listingId")
            logging.info("Published inventory group %s as listing: %s", group_key, listing_id)
            return listing_id
        except requests.HTTPError as e:
            logging.error("Failed to publish inventory group %s: %s", group_key, e)
            if hasattr(e, 'response') and e.response is not None:
                logging.error("Response: %s", e.response.text)
            return None


def build_ebay_description(product: FlatfileProduct, parent_data: Optional[dict] = None) -> str:
    """Build eBay-optimized HTML description from flatfile data."""
    # Use parent description if available, otherwise product description
    main_desc = parent_data.get('description', '') if parent_data else product.description
    if not main_desc:
        main_desc = product.description
    
    # Get bullet points (prefer parent's if available)
    bullets = parent_data.get('bullet_points', []) if parent_data else product.bullet_points
    if not bullets:
        bullets = product.bullet_points
    
    html_parts = [
        '<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">',
        f'<h2>{product.title}</h2>',
    ]
    
    if main_desc:
        html_parts.append(f'<p>{main_desc}</p>')
    
    if bullets:
        html_parts.append('<h3>Features:</h3><ul>')
        for bullet in bullets:
            html_parts.append(f'<li>{bullet}</li>')
        html_parts.append('</ul>')
    
    html_parts.append('</div>')
    
    return '\n'.join(html_parts)


def create_variation_listing_from_flatfile(
    manager: EbayInventoryManager,
    parent_data: Optional[dict],
    products: list[FlatfileProduct],
    policy_ids: dict,
    dry_run: bool = False,
) -> Optional[str]:
    """
    Create a multi-variation eBay listing from flatfile data.
    
    Returns the listing ID if successful.
    """
    if not products:
        return None
    
    # Determine group key from parent SKU or first product
    group_key = parent_data['sku'] if parent_data else products[0].sku.split('_')[0]
    group_key = re.sub(r'[^a-zA-Z0-9_]', '_', group_key.lower())
    
    logging.info("Creating variation listing: %s with %d products", group_key, len(products))
    
    # Collect unique variation values
    size_values = set()
    color_values = set()
    
    # Step 0: Clean up any existing groups/offers for these SKUs
    # Delete old inventory item groups that might contain these SKUs
    old_group_keys = ["no_entry_sign_self_adhesive", "noentry_parent1"]
    for old_key in old_group_keys:
        manager.delete_inventory_item_group(old_key)
    
    # Withdraw and delete existing offers
    for product in products:
        manager.withdraw_offer_by_sku(product.sku)
        manager.delete_offer_by_sku(product.sku)
    
    # Step 1: Create inventory items for each variation
    sku_list = []
    all_images = []
    
    for product in products:
        size_values.add(product.size)
        color_values.add(product.color)
        
        # Build aspects for this variation
        aspects = {
            "Size": [product.size],
            "Colour": [product.color],
            "Brand": ["NorthByNorthEast"],
            "Material": ["Aluminium"],
            "Type": ["Safety Sign"],
        }
        
        # Build description
        description = build_ebay_description(product, parent_data)
        
        if dry_run:
            logging.info("  [DRY RUN] Would create inventory item: %s (%s, %s) at £%.2f",
                        product.sku, product.size, product.color, product.price)
        else:
            manager.create_or_replace_inventory_item(
                sku=product.sku,
                title=product.title,
                description=description,
                image_urls=product.image_urls,
                aspects=aspects,
            )
        
        sku_list.append(product.sku)
        all_images.extend(product.image_urls[:3])
    
    # Step 2: Create offers for each SKU
    if not dry_run:
        for product in products:
            try:
                existing_offers = manager.get_offers_by_sku(product.sku)
                if not existing_offers:
                    manager.create_offer(product.sku, product.price, policy_ids)
            except requests.HTTPError as e:
                logging.warning("Could not create offer for %s: %s", product.sku, e)
    
    # Step 3: Build common aspects (exclude variation aspects)
    common_aspects = {
        "Brand": ["NorthByNorthEast"],
        "Material": ["Aluminium"],
        "Type": ["Safety Sign"],
    }
    
    # Step 4: Build variant image mapping
    # eBay only supports one aspectsImageVariesBy dimension, but we need images
    # to vary by Size+Colour combination. We'll use Size as the image-varying aspect
    # since each size has distinct dimension annotations in the images.
    size_images = {}
    for product in products:
        size = product.size
        if size not in size_images:
            size_images[size] = []
        # Add this product's main image to the size group
        if product.image_urls:
            main_img = product.image_urls[0]
            if main_img not in size_images[size]:
                size_images[size].append(main_img)
    
    # Build variantImages structure for eBay API - map by Size
    variant_images = []
    for size, urls in size_images.items():
        variant_images.append({
            "value": size,
            "imageUrls": urls[:4],  # Max 4 images per variant value
        })
    
    logging.info("Built variant image mapping for %d sizes", len(variant_images))
    for vi in variant_images:
        logging.info("  %s: %d images", vi["value"], len(vi["imageUrls"]))
    
    # Step 5: Create inventory item group
    group_title = parent_data['title'] if parent_data else products[0].title
    # Ensure title fits eBay limit
    if len(group_title) > 80:
        group_title = group_title[:77] + "..."
    
    group_description = build_ebay_description(products[0], parent_data)
    
    variation_specs = {
        "Size": sorted(list(size_values)),
        "Colour": sorted(list(color_values)),
    }
    
    if dry_run:
        logging.info("  [DRY RUN] Would create inventory group: %s", group_key)
        logging.info("  [DRY RUN] Sizes: %s", variation_specs["Size"])
        logging.info("  [DRY RUN] Colours: %s", variation_specs["Colour"])
        return "DRY_RUN"
    
    manager.create_or_replace_inventory_item_group(
        group_key=group_key,
        title=group_title,
        description=group_description,
        image_urls=all_images[:12],
        aspects=common_aspects,
        variation_specs=variation_specs,
        sku_list=sku_list,
        variant_images=variant_images,
    )
    
    # Step 5: Publish the group
    listing_id = manager.publish_inventory_item_group(group_key, policy_ids)
    return listing_id


def main():
    parser = argparse.ArgumentParser(description="Generate eBay listings from Amazon flatfile")
    parser.add_argument("flatfile", type=Path, help="Path to Amazon flatfile (.xlsm)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating listings")
    parser.add_argument("--promote", action="store_true", help="Auto-promote listing with General strategy (Cost Per Sale)")
    parser.add_argument("--ad-rate", type=str, default=DEFAULT_AD_RATE_PERCENT, 
                       help=f"Ad rate percentage for Promoted Listings (default: {DEFAULT_AD_RATE_PERCENT}%%)")
    args = parser.parse_args()
    
    if not args.flatfile.exists():
        logging.error("Flatfile not found: %s", args.flatfile)
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
        marketplace_id = policy_ids.get("marketplaceId", "EBAY_GB")
        manager = EbayInventoryManager(auth, marketplace_id=marketplace_id)
        marketing_manager = EbayMarketingManager(auth, marketplace_id=marketplace_id) if args.promote else None
    except ValueError as e:
        logging.error("eBay auth error: %s", e)
        return 1
    
    # Read flatfile
    parent_data, products = read_flatfile(args.flatfile)
    
    if not products:
        logging.error("No products found in flatfile")
        return 1
    
    logging.info("Found %d products in flatfile", len(products))
    for p in products:
        logging.info("  %s: %s (%s) - £%.2f - %d images", 
                    p.sku, p.size, p.color, p.price, len(p.image_urls))
    
    # Create variation listing
    listing_id = create_variation_listing_from_flatfile(
        manager=manager,
        parent_data=parent_data,
        products=products,
        policy_ids=policy_ids,
        dry_run=args.dry_run,
    )
    
    if listing_id:
        logging.info("\n=== SUCCESS ===")
        logging.info("Created listing: %s", listing_id)
        if listing_id != "DRY_RUN":
            logging.info("View at: https://www.ebay.co.uk/itm/%s", listing_id)
            
            # Auto-promote if requested
            if args.promote and marketing_manager:
                logging.info("\n=== PROMOTING LISTING ===")
                # Wait for listing to propagate in eBay's system
                logging.info("Waiting 10 seconds for listing to propagate...")
                time.sleep(10)
                
                campaign_id = marketing_manager.find_or_create_general_campaign(
                    campaign_name="Signage Auto Promotion",
                    ad_rate_percent=args.ad_rate,
                )
                if campaign_id:
                    # Get the inventory group key from parent SKU
                    group_key = parent_data['sku'] if parent_data else products[0].sku.split('_')[0]
                    group_key = re.sub(r'[^a-zA-Z0-9_]', '_', group_key.lower())
                    
                    success = marketing_manager.add_listing_to_campaign(
                        campaign_id=campaign_id,
                        listing_id=listing_id,
                        bid_percentage=args.ad_rate,
                        inventory_reference_id=group_key,
                    )
                    if success:
                        logging.info("Listing promoted with %s%% ad rate (General/Cost Per Sale)", args.ad_rate)
                    else:
                        logging.warning("Failed to add listing to campaign")
                else:
                    logging.warning("Failed to create/find campaign for promotion")
        return 0
    else:
        logging.error("\n=== FAILED ===")
        return 1


if __name__ == "__main__":
    exit(main())
