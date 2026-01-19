#!/usr/bin/env python3
"""
AI Lifestyle Image Generator

Generates lifestyle/context images for products using DALL-E 3.
Takes the main product image and creates contextual scenes.
"""

import argparse
import base64
import io
import logging
import os
from pathlib import Path

from openai import OpenAI
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# Scene templates based on sign type/text
SCENE_PROMPTS = {
    "no_dogs": "A professional office building entrance door, modern glass and metal design, clean corporate environment, natural daylight, photorealistic",
    "keep_dogs_on_lead": "A public park entrance gate with green grass and trees visible, wooden fence posts, dog walking area, sunny day, natural outdoor setting, photorealistic",
    "dogs_on_lead": "A public park entrance gate with green grass and trees visible, wooden fence posts, dog walking area, sunny day, natural outdoor setting, photorealistic",
    "dogs_must_be_on_lead": "A public park entrance gate with green grass and trees visible, wooden fence posts, dog walking area, sunny day, natural outdoor setting, photorealistic",
    "no_entry": "A warehouse or industrial facility entrance, metal door with safety markings, professional workplace setting, good lighting, photorealistic",
    "staff_only": "A modern office corridor with a door leading to a staff area, professional corporate interior, clean walls, natural lighting, photorealistic",
    "fire_exit": "An emergency exit corridor in a commercial building, well-lit hallway, safety compliant environment, photorealistic",
    "no_smoking": "A building entrance area with glass doors, modern commercial property, outdoor covered area, photorealistic",
    "private": "A private office door in a corporate building, professional wood or glass door, executive area, photorealistic",
    "private_property": "A residential driveway entrance with brick pillars, iron gate, private home setting, well-maintained garden, photorealistic",
    "keep_gate_closed": "A farm or country property gate, wooden five-bar gate, rural setting with fields visible, gravel driveway, photorealistic",
    "cctv": "A commercial building exterior corner, security camera visible, modern office park, professional environment, photorealistic",
    "parking": "A car park entrance with parking bays visible, tarmac surface, commercial or retail setting, good lighting, photorealistic",
    "default": "A professional office or commercial building wall, clean painted surface, good lighting, modern interior design, photorealistic",
}


def get_scene_prompt(sign_text: str) -> str:
    """Get appropriate scene prompt based on sign text."""
    text_lower = sign_text.lower().replace(" ", "_")
    
    for key, prompt in SCENE_PROMPTS.items():
        if key in text_lower:
            return prompt
    
    return SCENE_PROMPTS["default"]


def generate_lifestyle_image_dalle(
    product_image_path: Path,
    sign_text: str,
    api_key: str,
    output_path: Path,
) -> bool:
    """
    Generate a lifestyle image using DALL-E 3.
    
    This creates a contextual background scene and describes where the sign should appear.
    Since DALL-E 3 can't directly composite images, we generate a scene with a placeholder
    for the sign and then composite programmatically.
    
    Args:
        product_image_path: Path to the main product image
        sign_text: Text on the sign (for context)
        api_key: OpenAI API key
        output_path: Where to save the lifestyle image
        
    Returns:
        True if successful
    """
    client = OpenAI(api_key=api_key)
    
    # Get scene prompt based on sign type
    scene_base = get_scene_prompt(sign_text)
    
    # Generate background scene with a clear area for sign placement
    prompt = f"""{scene_base}

The image should have a clear, well-lit wall or door surface where a small rectangular sign could be mounted. 
Leave a visible flat area (about 15-20% of the image) on a wall or door that would be suitable for mounting a sign.
The area should be at eye level, well-lit, and clearly visible.
Professional product photography style, high quality, 4K resolution."""

    logging.info("Generating lifestyle background for '%s'...", sign_text)
    
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        image_url = response.data[0].url
        
        # Download the generated image
        import urllib.request
        with urllib.request.urlopen(image_url) as response_data:
            background_data = response_data.read()
        
        background = Image.open(io.BytesIO(background_data))
        
        # Load the product image
        product = Image.open(product_image_path)
        
        # Composite the product onto the background
        lifestyle = composite_product_on_background(product, background)
        
        # Save the result
        lifestyle.save(output_path, "PNG", quality=95)
        logging.info("Saved lifestyle image: %s", output_path)
        
        return True
        
    except Exception as e:
        logging.error("Failed to generate lifestyle image: %s", e)
        return False


def composite_product_on_background(
    product: Image.Image,
    background: Image.Image,
    position: str = "center",
    scale: float = 0.45,
    blur_radius: float = 3.0,
) -> Image.Image:
    """
    Composite product image onto background with blur effect.
    
    Args:
        product: Product image (with or without transparency)
        background: Background scene image
        position: Where to place product (center, center-right, center-left)
        scale: Size of product relative to background (0.0-1.0)
        blur_radius: Gaussian blur radius for background (0 = no blur)
        
    Returns:
        Composited image
    """
    from PIL import ImageFilter
    
    # Apply subtle blur to background to make product stand out
    if blur_radius > 0:
        background = background.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    
    # Resize product to fit nicely on background
    bg_width, bg_height = background.size
    
    # Calculate product size (larger scale for prominence)
    max_product_width = int(bg_width * scale)
    max_product_height = int(bg_height * scale)
    
    # Maintain aspect ratio
    product_ratio = product.width / product.height
    if product_ratio > 1:
        new_width = max_product_width
        new_height = int(new_width / product_ratio)
    else:
        new_height = max_product_height
        new_width = int(new_height * product_ratio)
    
    product_resized = product.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Calculate position
    if position == "center":
        x = (bg_width - new_width) // 2
        y = (bg_height - new_height) // 2
    elif position == "center-right":
        x = int(bg_width * 0.65) - new_width // 2
        y = (bg_height - new_height) // 2
    elif position == "center-left":
        x = int(bg_width * 0.35) - new_width // 2
        y = (bg_height - new_height) // 2
    else:
        x = (bg_width - new_width) // 2
        y = (bg_height - new_height) // 2
    
    # Create composite
    result = background.copy()
    
    # Handle transparency if product has alpha channel
    if product_resized.mode == 'RGBA':
        result.paste(product_resized, (x, y), product_resized)
    else:
        result.paste(product_resized, (x, y))
    
    return result


def generate_lifestyle_for_product(
    m_folder: Path,
    sign_text: str,
    api_key: str,
    force: bool = False,
) -> Path | None:
    """
    Generate a lifestyle image for a product in its M folder.
    
    Args:
        m_folder: Path to the M number folder
        sign_text: Text on the sign
        api_key: OpenAI API key
        force: If True, regenerate even if file exists
        
    Returns:
        Path to generated lifestyle image, or None if failed
    """
    images_dir = m_folder / "002 Images"
    if not images_dir.exists():
        logging.warning("Images directory not found: %s", images_dir)
        return None
    
    # Find the main image (001)
    main_images = list(images_dir.glob("*001*.png"))
    if not main_images:
        logging.warning("Main image not found in %s", images_dir)
        return None
    
    main_image = main_images[0]
    m_number = m_folder.name.split()[0]  # Extract M1075 from folder name
    
    # Output path for lifestyle image
    lifestyle_path = images_dir / f"{m_number} - 005.png"
    
    # Skip if file already exists (unless force=True)
    if lifestyle_path.exists() and not force:
        logging.info("Skipping %s: lifestyle image already exists (use --force to regenerate)", m_number)
        return lifestyle_path
    
    if generate_lifestyle_image_dalle(main_image, sign_text, api_key, lifestyle_path):
        return lifestyle_path
    
    return None


def read_lifestyle_products_from_csv(csv_path: Path, require_approved: bool = True) -> dict[str, dict]:
    """
    Read products from CSV and return those with lifestyle_image='yes'.
    
    Args:
        csv_path: Path to the CSV file
        require_approved: If True, only include products with qa_status='approved'
    
    Returns dict mapping m_number to product info (description, text_line_1).
    """
    import csv
    
    products = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            m_number = (row.get("m_number") or "").strip()
            lifestyle = (row.get("lifestyle_image") or "").strip().lower()
            qa_status = (row.get("qa_status") or "").strip().lower()
            
            # Check lifestyle_image='yes'
            if not (m_number and lifestyle == "yes"):
                continue
            
            # Check qa_status if required
            if require_approved and qa_status != "approved":
                logging.info("Skipping %s: qa_status is '%s', not 'approved'", m_number, qa_status or "pending")
                continue
            
            products[m_number] = {
                "description": (row.get("description") or "").strip(),
                "text_line_1": (row.get("text_line_1") or "").strip(),
            }
    
    return products


def main():
    parser = argparse.ArgumentParser(description="Generate lifestyle images for products")
    parser.add_argument("--csv", type=Path, default=Path("products_test.csv"), help="Input CSV file")
    parser.add_argument("--exports", type=Path, default=Path("exports"), help="Exports directory")
    parser.add_argument("--m-number", type=str, help="Specific M number to process (e.g., M1075)")
    parser.add_argument("--sign-text", type=str, help="Sign text for context")
    parser.add_argument("--force", action="store_true", help="Regenerate even if file exists")
    parser.add_argument("--skip-qa-check", action="store_true", help="Skip qa_status='approved' requirement")
    args = parser.parse_args()
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logging.error("OPENAI_API_KEY environment variable not set")
        return 1
    
    if args.m_number:
        # Process specific product (--force or check CSV)
        m_folders = list(args.exports.glob(f"{args.m_number}*"))
        if not m_folders:
            logging.error("M folder not found for %s", args.m_number)
            return 1
        
        m_folder = m_folders[0]
        sign_text = args.sign_text or m_folder.name.split()[1]  # Extract description from folder name
        
        # Check CSV if not forcing
        if not args.force:
            lifestyle_products = read_lifestyle_products_from_csv(args.csv, require_approved=not args.skip_qa_check)
            if args.m_number not in lifestyle_products:
                logging.info("Skipping %s: not eligible for lifestyle image (use --force to override)", args.m_number)
                return 0
        
        result = generate_lifestyle_for_product(m_folder, sign_text, api_key, force=args.force)
        if result:
            logging.info("Generated: %s", result)
        else:
            logging.error("Failed to generate lifestyle image")
            return 1
    else:
        # Process products from CSV where lifestyle_image='yes' and qa_status='approved'
        lifestyle_products = read_lifestyle_products_from_csv(args.csv, require_approved=not args.skip_qa_check)
        
        if not lifestyle_products:
            logging.info("No eligible products found (need lifestyle_image='yes' and qa_status='approved')")
            return 0
        
        logging.info("Found %d eligible products for lifestyle images", len(lifestyle_products))
        
        success = 0
        failed = 0
        skipped = 0
        
        for m_number, product_info in lifestyle_products.items():
            m_folders = list(args.exports.glob(f"{m_number}*"))
            if not m_folders:
                logging.warning("M folder not found for %s, skipping", m_number)
                skipped += 1
                continue
            
            m_folder = m_folders[0]
            # Use --sign-text override if provided, otherwise use product data
            sign_text = args.sign_text or product_info["text_line_1"] or product_info["description"] or "Sign"
            
            logging.info("Processing %s (%s)...", m_number, sign_text)
            
            result = generate_lifestyle_for_product(m_folder, sign_text, api_key, force=args.force)
            if result:
                success += 1
            else:
                failed += 1
        
        logging.info("Completed: %d success, %d failed, %d skipped", success, failed, skipped)
    
    return 0


if __name__ == "__main__":
    exit(main())
