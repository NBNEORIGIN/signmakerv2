#!/usr/bin/env python3
"""
Fix Etsy JPEG Images

Re-converts PNG images to Etsy-compatible JPEGs and re-uploads to R2.
This fixes the "error decoding image" issue with Etsy/Shop Uploader.
"""

import argparse
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

MAX_WORKERS = 8


def convert_png_to_jpeg(png_path: Path, output_path: Path, background_color=(255, 255, 255)) -> Path:
    """Convert PNG to Etsy-compatible JPEG."""
    img = Image.open(png_path)
    
    # Strip ICC profile to avoid compatibility issues
    img.info.pop('icc_profile', None)
    
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, background_color)
        if img.mode == "P":
            img = img.convert("RGBA")
        if img.mode == "RGBA":
            background.paste(img, mask=img.split()[3])
        else:
            background.paste(img)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    
    # Save with optimized JPEG for Etsy compatibility
    img.save(output_path, "JPEG", quality=85, optimize=True)
    return output_path


def get_s3_client():
    """Create S3 client for Cloudflare R2."""
    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key_id = os.environ.get("R2_ACCESS_KEY_ID")
    secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
    )


def process_image(args_tuple):
    """Process a single image: convert and upload."""
    png_path, s3_client, bucket_name, public_url = args_tuple
    
    try:
        # Convert to JPEG
        jpg_path = png_path.with_suffix(".jpg")
        convert_png_to_jpeg(png_path, jpg_path)
        
        # Upload to R2
        key = jpg_path.name
        s3_client.upload_file(
            str(jpg_path),
            bucket_name,
            key,
            ExtraArgs={"ContentType": "image/jpeg"},
        )
        
        # Clean up local JPEG
        jpg_path.unlink(missing_ok=True)
        
        url = f"{public_url}/{key}"
        logging.info("Uploaded: %s", key)
        return (png_path.stem, url, None)
        
    except Exception as e:
        logging.error("Failed %s: %s", png_path.name, e)
        return (png_path.stem, None, str(e))


def main():
    parser = argparse.ArgumentParser(description="Fix Etsy JPEG images")
    parser.add_argument("--exports", type=Path, default=Path("exports"), help="Exports directory")
    parser.add_argument("--m-number", type=str, help="Process only this M number (e.g., M1179)")
    args = parser.parse_args()
    
    # Validate R2 config
    required_vars = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "R2_PUBLIC_URL"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        logging.error("Missing environment variables: %s", missing)
        logging.error("Run config.bat first")
        return 1
    
    bucket_name = os.environ.get("R2_BUCKET_NAME")
    public_url = os.environ.get("R2_PUBLIC_URL")
    
    # Find all PNG images
    all_pngs = []
    
    if args.m_number:
        # Process single M number
        m_folders = list(args.exports.glob(f"{args.m_number} *"))
        if not m_folders:
            logging.error("M folder not found: %s", args.m_number)
            return 1
    else:
        # Process all M folders
        m_folders = [f for f in args.exports.iterdir() if f.is_dir() and f.name.startswith("M")]
    
    for m_folder in m_folders:
        images_dir = m_folder / "002 Images"
        if images_dir.exists():
            for png in images_dir.glob("*.png"):
                all_pngs.append(png)
    
    if not all_pngs:
        logging.info("No PNG images found")
        return 0
    
    logging.info("Found %d PNG images to convert and upload", len(all_pngs))
    
    # Process in parallel
    s3_client = get_s3_client()
    tasks = [(png, s3_client, bucket_name, public_url) for png in all_pngs]
    
    success = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_image, task): task[0] for task in tasks}
        for future in as_completed(futures):
            name, url, error = future.result()
            if url:
                success += 1
            else:
                failed += 1
            
            if (success + failed) % 10 == 0:
                logging.info("Progress: %d/%d", success + failed, len(all_pngs))
    
    logging.info("=" * 50)
    logging.info("COMPLETE: %d success, %d failed", success, failed)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
