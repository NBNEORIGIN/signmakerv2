#!/usr/bin/env python3
"""
Copy exported M folders to shared location.
Copies from local exports/ to G:\My Drive\001 NBNE\001 M
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# Shared destination for all staff
SHARED_M_FOLDER = Path(r"G:\My Drive\001 NBNE\001 M")


def copy_exports_to_shared(exports_dir: Path, m_numbers: list[str] = None) -> int:
    """
    Copy M folders from exports to shared location.
    
    Args:
        exports_dir: Local exports directory
        m_numbers: Optional list of specific M numbers to copy. If None, copies all.
    
    Returns:
        Number of folders copied
    """
    if not exports_dir.exists():
        logging.error("Exports directory not found: %s", exports_dir)
        return 0
    
    if not SHARED_M_FOLDER.exists():
        logging.warning("Shared folder does not exist, creating: %s", SHARED_M_FOLDER)
        SHARED_M_FOLDER.mkdir(parents=True, exist_ok=True)
    
    # Find M folders in exports
    m_folders = [f for f in exports_dir.iterdir() if f.is_dir() and f.name.startswith("M")]
    
    if m_numbers:
        # Filter to specific M numbers
        m_folders = [f for f in m_folders if any(f.name.startswith(m) for m in m_numbers)]
    
    if not m_folders:
        logging.info("No M folders found to copy")
        return 0
    
    logging.info("Found %d M folders to copy", len(m_folders))
    
    copied = 0
    for idx, folder in enumerate(m_folders, 1):
        dest = SHARED_M_FOLDER / folder.name
        
        logging.info("Progress: %d/%d - Copying %s...", idx, len(m_folders), folder.name)
        sys.stdout.flush()
        
        try:
            if dest.exists():
                # Remove existing and replace
                shutil.rmtree(dest)
            
            shutil.copytree(folder, dest)
            copied += 1
            logging.info("  ✓ Copied to %s", dest)
        except Exception as e:
            logging.error("  ✗ Failed to copy %s: %s", folder.name, e)
    
    logging.info("Copied %d/%d M folders to shared location", copied, len(m_folders))
    return copied


def main():
    parser = argparse.ArgumentParser(description="Copy M folders to shared location")
    parser.add_argument("--exports", type=Path, default=Path("exports"), 
                       help="Local exports directory")
    parser.add_argument("--m-numbers", type=str, nargs="*",
                       help="Specific M numbers to copy (e.g., M1150 M1151)")
    args = parser.parse_args()
    
    logging.info("=== Copying M folders to shared location ===")
    logging.info("Source: %s", args.exports.absolute())
    logging.info("Destination: %s", SHARED_M_FOLDER)
    
    copied = copy_exports_to_shared(args.exports, args.m_numbers)
    
    if copied > 0:
        logging.info("=== Copy complete! ===")
        return 0
    else:
        logging.warning("No folders were copied")
        return 1


if __name__ == "__main__":
    sys.exit(main())
