#!/usr/bin/env python3
"""
Amazon Image Generator v2 - Template-based approach with dynamic layout.

Generates product images by:
1. Loading pre-designed SVG templates (per size/color)
2. Dynamically positioning icons and text based on layout mode
3. Exporting via Inkscape CLI
4. Optionally reviewing with Claude Vision API

Layout Modes:
  A - Icon(s) centered, no text
  B - Icon(s) top, 1 text line below
  C - Icon(s) top, 2+ text lines below
  D - Icon(s) bottom, 1 text line above
  E - Icon(s) bottom, 2+ text lines above
  F - Icon(s) center, 1 text above, 1 text below

Sizes: saville (115x95), dick (140x90), barzan (194x143), dracula (95 dia), baby_jesus (290x190)
Colors: silver, gold, white
"""

import argparse
import base64
import csv
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import math

from lxml import etree

# Namespaces
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
SODIPODI_NS = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"

NSMAP = {
    None: SVG_NS,
    "xlink": XLINK_NS,
    "inkscape": INKSCAPE_NS,
    "sodipodi": SODIPODI_NS,
}

# Size definitions (width_mm, height_mm, is_circular)
SIZES = {
    "saville": (115, 95, False),
    "dick": (140, 90, False),
    "barzan": (194, 143, False),
    "dracula": (95, 95, True),  # Circular, diameter = 95
    "baby_jesus": (290, 190, False),  # Can be portrait or landscape
}

COLORS = ["silver", "gold", "white"]

LAYOUT_MODES = ["A", "B", "C", "D", "E", "F"]

# Prohibition overlay colors
PROHIBITION_CIRCLE_COLOR = "#cc0000"
PROHIBITION_SLASH_COLOR = "#cc0000"
PROHIBITION_STROKE_WIDTH = 4  # mm


FONTS = {
    "arial_bold": ("Arial", "bold"),
    "arial_heavy": ("Arial Black", "normal"),  # Arial Black is the heavy variant
}

@dataclass
class ProductRow:
    """Represents a single product from the input CSV."""
    sku_parent: str
    size: str
    color: str
    layout_mode: str
    icon_files: list[str]
    text_line_1: str
    text_line_2: str
    text_line_3: str
    m_number: str = ""  # M Number for folder naming (e.g., M1075)
    description: str = ""  # Product description for folder naming
    sign_type: str = "informational"  # 'prohibition' or 'informational' (optional)
    orientation: str = "landscape"  # For baby_jesus: 'portrait' or 'landscape'
    font: str = "arial_bold"  # Font choice: 'arial_bold' or 'arial_heavy'
    icon_scale: float = 1.0  # Scale factor for icon size (0.5 = 50%, 1.5 = 150%)
    text_scale: float = 1.0  # Scale factor for text size (0.5 = 50%, 1.5 = 150%)


@dataclass
class SignBounds:
    """Defines the drawable area on the sign."""
    x: float  # Left edge (mm)
    y: float  # Top edge (mm)
    width: float  # Width (mm)
    height: float  # Height (mm)
    is_circular: bool = False
    padding: float = 5.0  # Inner padding (mm)

    @property
    def inner_x(self) -> float:
        return self.x + self.padding

    @property
    def inner_y(self) -> float:
        return self.y + self.padding

    @property
    def inner_width(self) -> float:
        return self.width - 2 * self.padding

    @property
    def inner_height(self) -> float:
        return self.height - 2 * self.padding

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


@dataclass
class LayoutResult:
    """Result of layout calculation."""
    icon_x: float
    icon_y: float
    icon_width: float
    icon_height: float
    text_elements: list[dict]  # [{text, x, y, font_size}, ...]


def _setup_logging(exports_dir: Path) -> None:
    """Configure logging to console and file."""
    exports_dir.mkdir(parents=True, exist_ok=True)
    log_path = exports_dir / "run.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(formatter)

    fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(sh)
    logger.addHandler(fh)


def _read_products_csv(csv_path: Path) -> list[ProductRow]:
    """Read and validate the input CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    rows: list[ProductRow] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"m_number", "size", "color", "layout_mode", "icon_files"}
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing required columns: {sorted(missing)}")

        for i, r in enumerate(reader, start=2):
            m_number = (r.get("m_number") or "").strip()
            if not m_number:
                logging.warning("Skipping row %s: empty m_number", i)
                continue

            size = (r.get("size") or "").strip().lower()
            if size not in SIZES:
                logging.warning("Skipping row %s: invalid size '%s'", i, size)
                continue

            color = (r.get("color") or "").strip().lower()
            if color not in COLORS:
                logging.warning("Skipping row %s: invalid color '%s'", i, color)
                continue

            layout_mode = (r.get("layout_mode") or "").strip().upper()
            if layout_mode not in LAYOUT_MODES:
                logging.warning("Skipping row %s: invalid layout_mode '%s'", i, layout_mode)
                continue

            sign_type = (r.get("sign_type") or "informational").strip().lower()
            if sign_type not in ("prohibition", "informational"):
                sign_type = "informational"

            icon_files_raw = (r.get("icon_files") or "").strip()
            icon_files = [f.strip() for f in icon_files_raw.split(",") if f.strip()]

            orientation = (r.get("orientation") or "landscape").strip().lower()
            if orientation not in ("portrait", "landscape"):
                orientation = "landscape"

            description = (r.get("description") or "").strip()
            sku_parent = (r.get("sku_parent") or m_number).strip()  # Use m_number as fallback
            font = (r.get("font") or "arial_bold").strip().lower()
            if font not in FONTS:
                font = "arial_bold"

            # Parse scale factors from CSV (default 1.0)
            icon_scale_str = (r.get("icon_scale") or "").strip()
            text_scale_str = (r.get("text_scale") or "").strip()
            icon_scale = float(icon_scale_str) if icon_scale_str else 1.0
            text_scale = float(text_scale_str) if text_scale_str else 1.0
            
            rows.append(
                ProductRow(
                    sku_parent=sku_parent,
                    size=size,
                    color=color,
                    layout_mode=layout_mode,
                    sign_type=sign_type,
                    icon_files=icon_files,
                    text_line_1=(r.get("text_line_1") or "").strip(),
                    text_line_2=(r.get("text_line_2") or "").strip(),
                    text_line_3=(r.get("text_line_3") or "").strip(),
                    m_number=m_number,
                    description=description,
                    orientation=orientation,
                    font=font,
                    icon_scale=icon_scale,
                    text_scale=text_scale,
                )
            )
    return rows


# Template sign positions (extracted from SVG structure)
# Format: {size: (sign_x, sign_y, sign_width, sign_height)} in mm
# These are the actual positions of the sign graphic within each template
TEMPLATE_SIGN_BOUNDS = {
    # silver_saville: sign at ~(25, 19) with size 103x83 in 159.4x139.4 canvas
    # Adding extra padding to keep content well within visible area
    "saville": (30, 24, 93, 73),  # Inset by 5mm from actual sign edges
    # Other sizes - adjust when templates are created
    "dick": (25, 30, 110, 60),  # Placeholder with padding
    "barzan": (25, 25, 164, 113),  # Placeholder with padding
    "dracula": (37, 27, 85, 85),  # Circular with padding
    "baby_jesus": (25, 25, 240, 140),  # Placeholder with padding
}


def _load_layout_bounds(csv_path: Path) -> dict:
    """
    Load layout bounding boxes from CSV file.
    Returns dict keyed by (template, size, orientation, layout_mode, element).
    """
    bounds = {}
    if not csv_path.exists():
        return bounds
    
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (
                row.get("template", "main"),
                row.get("size", ""),
                row.get("orientation", "landscape"),
                row.get("layout_mode", ""),
                row.get("element", ""),
            )
            bounds[key] = {
                "x": float(row.get("x", 0)),
                "y": float(row.get("y", 0)),
                "width": float(row.get("width", 0)),
                "height": float(row.get("height", 0)),
            }
    return bounds


# Global layout bounds loaded from CSV
LAYOUT_BOUNDS_CSV = Path("assets/layout_modes.csv")
LAYOUT_BOUNDS = {}


def _get_sign_bounds(size: str, orientation: str = "landscape") -> SignBounds:
    """Get the drawable bounds for a sign size based on template structure."""
    width_mm, height_mm, is_circular = SIZES[size]

    # Get actual sign position from template
    if size in TEMPLATE_SIGN_BOUNDS:
        sign_x, sign_y, sign_w, sign_h = TEMPLATE_SIGN_BOUNDS[size]
    else:
        # Fallback: assume centered with margin
        margin = 20
        sign_x = margin
        sign_y = margin
        sign_w = width_mm - 2 * margin
        sign_h = height_mm - 2 * margin

    # For baby_jesus, swap dimensions if portrait
    if size == "baby_jesus" and orientation == "portrait":
        sign_w, sign_h = sign_h, sign_w

    return SignBounds(
        x=sign_x,
        y=sign_y,
        width=sign_w,
        height=sign_h,
        is_circular=is_circular,
        padding=4.0 if is_circular else 3.0,  # Reduced padding for more usable space
    )


def _calculate_layout(
    bounds: SignBounds,
    layout_mode: str,
    num_icons: int,
    text_lines: list[str],
    font_name: str = "Arial",
    icon_scale: float = 1.0,
    text_scale: float = 1.0,
    size: str = "",
    orientation: str = "landscape",
) -> LayoutResult:
    """
    Calculate positions and sizes for icons and text based on layout mode.
    
    First checks LAYOUT_BOUNDS (from CSV) for exact coordinates.
    Falls back to calculated positions if not found.

    Layout Modes:
      A - Icon(s) centered, no text
      B - Icon(s) top, 1 text line below
      C - Icon(s) top, 2+ text lines below
      D - Icon(s) bottom, 1 text line above
      E - Icon(s) bottom, 2+ text lines above
      F - Icon(s) center, 1 text above, 1 text below
    """
    global LAYOUT_BOUNDS
    
    # Load layout bounds from CSV if not already loaded
    if not LAYOUT_BOUNDS and LAYOUT_BOUNDS_CSV.exists():
        LAYOUT_BOUNDS = _load_layout_bounds(LAYOUT_BOUNDS_CSV)
    
    # Check if we have CSV-defined bounds for this layout
    icon_key = ("main", size, orientation, layout_mode, "icon")
    text1_key = ("main", size, orientation, layout_mode, "text_1")
    text2_key = ("main", size, orientation, layout_mode, "text_2")
    text3_key = ("main", size, orientation, layout_mode, "text_3")
    
    # Filter empty text lines
    active_lines = [t for t in text_lines if t]
    
    # If CSV bounds exist for this layout, use them directly
    if icon_key in LAYOUT_BOUNDS:
        icon_bounds = LAYOUT_BOUNDS[icon_key]
        base_width = icon_bounds["width"]
        base_height = icon_bounds["height"]
        base_x = icon_bounds["x"]
        base_y = icon_bounds["y"]
        
        # Apply icon_scale multiplier - scale from center
        icon_width = base_width * icon_scale
        icon_height = base_height * icon_scale
        # Adjust position to keep icon centered after scaling
        icon_x = base_x + (base_width - icon_width) / 2
        icon_y = base_y + (base_height - icon_height) / 2
        
        text_elements = []
        
        # Add text elements from CSV bounds
        for idx, line in enumerate(active_lines):
            text_key = ("main", size, orientation, layout_mode, f"text_{idx + 1}")
            if text_key in LAYOUT_BOUNDS:
                tb = LAYOUT_BOUNDS[text_key]
                # Simple linear relationship: font_size = box_width / (num_chars * k)
                # where k is a constant that accounts for SVG rendering
                # Calibrated: 7 chars in 90mm box should give font ~4mm
                # So k = 90 / (7 * 4) = 3.2
                num_chars = len(line) if line else 1
                font_size = tb["width"] / (num_chars * 3.2)
                # Also cap by height
                max_by_height = tb["height"] / 3.0
                font_size = min(font_size, max_by_height)
                # Apply text_scale multiplier
                font_size = font_size * text_scale
                text_elements.append({
                    "text": line,
                    "x": tb["x"] + tb["width"] / 2,  # Center of text box
                    "y": tb["y"] + tb["height"] * 0.75,  # Position near bottom of box
                    "font_size": font_size,
                    "anchor": "middle",
                })
        
        logging.debug("Using CSV bounds for %s/%s/%s", size, orientation, layout_mode)
        return LayoutResult(
            icon_x=icon_x,
            icon_y=icon_y,
            icon_width=icon_width,
            icon_height=icon_height,
            text_elements=text_elements,
        )
    
    # Fallback to calculated positions
    inner_w = bounds.inner_width
    inner_h = bounds.inner_height
    inner_x = bounds.inner_x
    inner_y = bounds.inner_y

    # Font sizes - increased for better visual presence
    max_font_size = 5.0 * text_scale
    min_font_size = 2.0 * text_scale
    line_spacing = 2.0
    
    # Icon scale factor
    icon_size_multiplier = icon_scale

    text_elements = []

    if layout_mode == "A":
        # Icon(s) centered, no text
        icon_width = inner_w * 0.7 * icon_size_multiplier
        icon_height = inner_h * 0.7 * icon_size_multiplier
        icon_x = bounds.center_x - icon_width / 2
        icon_y = bounds.center_y - icon_height / 2

    elif layout_mode == "B":
        # Icon(s) top, 1 text line below - RULES-BASED: maximize visual presence
        # Rule: Icon takes 65% of height, large and prominent
        # Rule: Text fills bottom area, bold and readable
        
        icon_height = inner_h * 0.65  # Icon is 65% of inner height
        icon_width = icon_height  # Square aspect ratio
        icon_x = bounds.center_x - icon_width / 2
        icon_y = inner_y  # Start at top of inner area
        
        # Text positioned below icon
        icon_bottom = icon_y + icon_height
        text_zone_top = icon_bottom + inner_h * 0.02  # Minimal gap

        if active_lines:
            # Text sized to fit width, with larger max
            font_size = _fit_text_width(active_lines[0], inner_w * 0.95, max_font_size * 2.0, min_font_size)
            text_y = text_zone_top + font_size * 1.0
            text_elements.append({
                "text": active_lines[0],
                "x": bounds.center_x,
                "y": text_y,
                "font_size": font_size,
                "anchor": "middle",
            })

    elif layout_mode == "C":
        # Icon(s) top, 2+ text lines below
        num_lines = len(active_lines) if active_lines else 1
        # Calculate text sizes first to determine space needed
        text_sizes = [_fit_text_width(line, inner_w * 0.9, max_font_size, min_font_size) for line in active_lines]
        avg_font = sum(text_sizes) / len(text_sizes) if text_sizes else max_font_size
        text_block_height = num_lines * avg_font * line_spacing + avg_font
        
        icon_area_height = inner_h - text_block_height
        icon_height = icon_area_height * 0.85 * icon_size_multiplier
        icon_width = min(inner_w * 0.6, icon_height) * icon_size_multiplier
        icon_x = bounds.center_x - icon_width / 2
        icon_y = inner_y + (icon_area_height - icon_height) / 2

        text_start_y = inner_y + icon_area_height + avg_font * 0.8
        for idx, line in enumerate(active_lines):
            font_size = text_sizes[idx] if idx < len(text_sizes) else min_font_size
            text_elements.append({
                "text": line,
                "x": bounds.center_x,
                "y": text_start_y + idx * avg_font * line_spacing,
                "font_size": font_size,
                "anchor": "middle",
            })

    elif layout_mode == "D":
        # Icon(s) bottom, 1 text line above
        text_height = max_font_size * 1.5
        icon_height = (inner_h - text_height) * 0.8 * icon_size_multiplier
        icon_width = min(inner_w * 0.6, icon_height) * icon_size_multiplier
        icon_x = bounds.center_x - icon_width / 2
        icon_y = inner_y + text_height + (inner_h - text_height - icon_height) / 2

        if active_lines:
            font_size = _fit_text_width(active_lines[0], inner_w * 0.9, max_font_size, min_font_size)
            text_elements.append({
                "text": active_lines[0],
                "x": bounds.center_x,
                "y": inner_y + font_size,
                "font_size": font_size,
                "anchor": "middle",
            })

    elif layout_mode == "E":
        # Icon(s) bottom, 2+ text lines above
        num_lines = len(active_lines)
        text_sizes = [_fit_text_width(line, inner_w * 0.9, max_font_size, min_font_size) for line in active_lines]
        avg_font = sum(text_sizes) / len(text_sizes) if text_sizes else max_font_size
        text_block_height = num_lines * avg_font * line_spacing
        
        icon_area_height = inner_h - text_block_height
        icon_height = icon_area_height * 0.85 * icon_size_multiplier
        icon_width = min(inner_w * 0.5, icon_height) * icon_size_multiplier
        icon_x = bounds.center_x - icon_width / 2
        icon_y = inner_y + text_block_height + (icon_area_height - icon_height) / 2

        for idx, line in enumerate(active_lines):
            font_size = text_sizes[idx] if idx < len(text_sizes) else min_font_size
            text_elements.append({
                "text": line,
                "x": bounds.center_x,
                "y": inner_y + (idx + 1) * avg_font * line_spacing,
                "font_size": font_size,
                "anchor": "middle",
            })

    elif layout_mode == "F":
        # Icon(s) center, 1 text above, 1 text below
        text_area_each = max_font_size * 1.8
        icon_area_height = inner_h - 2 * text_area_each
        icon_height = icon_area_height * 0.9 * icon_size_multiplier
        icon_width = min(inner_w * 0.6, icon_height) * icon_size_multiplier
        icon_x = bounds.center_x - icon_width / 2
        icon_y = inner_y + text_area_each + (icon_area_height - icon_height) / 2

        if len(active_lines) >= 1:
            font_size = _fit_text_width(active_lines[0], inner_w * 0.85, max_font_size, min_font_size)
            text_elements.append({
                "text": active_lines[0],
                "x": bounds.center_x,
                "y": inner_y + font_size * 1.2,
                "font_size": font_size,
                "anchor": "middle",
            })
        if len(active_lines) >= 2:
            font_size = _fit_text_width(active_lines[1], inner_w * 0.85, max_font_size, min_font_size)
            text_elements.append({
                "text": active_lines[1],
                "x": bounds.center_x,
                "y": inner_y + inner_h - font_size * 0.3,
                "font_size": font_size,
                "anchor": "middle",
            })

    else:
        # Fallback to centered
        icon_width = inner_w * 0.6 * icon_size_multiplier
        icon_height = inner_h * 0.6 * icon_size_multiplier
        icon_x = bounds.center_x - icon_width / 2
        icon_y = bounds.center_y - icon_height / 2

    return LayoutResult(
        icon_x=icon_x,
        icon_y=icon_y,
        icon_width=icon_width,
        icon_height=icon_height,
        text_elements=text_elements,
    )


def _fit_text_width(text: str, max_width_mm: float, max_font: float, min_font: float) -> float:
    """
    Calculate font size to fit text within max_width.
    Very conservative calculation - SVG mm font-size renders larger than expected.
    """
    if not text:
        return max_font

    # Very conservative ratio - actual rendering is much wider than theoretical
    # Using 1.0 as ratio (each char takes full font-size width on average)
    char_width_ratio = 1.0
    
    # Calculate with large safety margin (0.7x)
    required_font = (max_width_mm / (len(text) * char_width_ratio)) * 0.7
    
    # Clamp to min/max range
    return max(min_font, min(max_font, required_font))


def _load_template_svg(templates_dir: Path, color: str, size: str, template_type: str, orientation: str = "landscape") -> etree._Element:
    """
    Load a template SVG file.
    Naming convention: {color}_{size}_{type}.svg for landscape
                       {color}_{size}_portrait_{type}.svg for portrait
    e.g., silver_saville_main.svg or silver_dick_portrait_main.svg
    """
    if orientation == "portrait":
        filename = f"{color}_{size}_portrait_{template_type}.svg"
    else:
        filename = f"{color}_{size}_{template_type}.svg"
    template_path = templates_dir / filename

    if not template_path.exists():
        # Fallback to landscape if portrait not found
        if orientation == "portrait":
            fallback = f"{color}_{size}_{template_type}.svg"
            fallback_path = templates_dir / fallback
            if fallback_path.exists():
                logging.warning("Portrait template not found, using landscape: %s", fallback)
                template_path = fallback_path
            else:
                raise FileNotFoundError(f"Template not found: {template_path}")
        else:
            raise FileNotFoundError(f"Template not found: {template_path}")

    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(template_path), parser)
    return tree.getroot()


def _load_icon(icons_dir: Path, icon_filename: str) -> Optional[tuple[str, any]]:
    """
    Load an icon file (SVG or PNG).
    Returns tuple of (type, data) where:
      - type is 'svg' or 'png'
      - data is etree._Element for SVG, or (base64_data, width, height) for PNG
    """
    # Try exact match first
    icon_path = icons_dir / icon_filename
    if not icon_path.exists():
        # Try case-insensitive search
        icon_lower = icon_filename.lower()
        for f in icons_dir.iterdir():
            if f.is_file() and f.name.lower() == icon_lower:
                icon_path = f
                break
        else:
            # Try without numeric prefix (e.g., "022 DOG.svg" -> "DOG.svg")
            parts = icon_filename.split(" ", 1)
            if len(parts) == 2:
                return _load_icon(icons_dir, parts[1])
            return None

    suffix = icon_path.suffix.lower()
    
    if suffix == ".svg":
        parser = etree.XMLParser(remove_blank_text=False)
        tree = etree.parse(str(icon_path), parser)
        return ("svg", tree.getroot())
    
    elif suffix in (".png", ".jpg", ".jpeg"):
        # Read and encode as base64
        with open(icon_path, "rb") as f:
            img_data = f.read()
        b64_data = base64.b64encode(img_data).decode("utf-8")
        
        # Try to get image dimensions using basic PNG header parsing
        width, height = 100, 100  # Default fallback
        if suffix == ".png" and len(img_data) >= 24:
            # PNG header: width at bytes 16-20, height at bytes 20-24 (big-endian)
            width = int.from_bytes(img_data[16:20], "big")
            height = int.from_bytes(img_data[20:24], "big")
        
        mime = "image/png" if suffix == ".png" else "image/jpeg"
        return ("png", (b64_data, width, height, mime))
    
    return None


def _load_icon_svg(icons_dir: Path, icon_filename: str) -> Optional[etree._Element]:
    """Load an icon SVG file (legacy wrapper)."""
    result = _load_icon(icons_dir, icon_filename)
    if result and result[0] == "svg":
        return result[1]
    return None


def _inject_icon(
    root: etree._Element,
    icon_root: etree._Element,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """
    Inject an icon SVG into the template at the specified position and size.
    Creates a new group with the icon content, scaled and positioned.
    """
    # Get icon's original viewBox or dimensions
    icon_viewbox = icon_root.get("viewBox")
    if icon_viewbox:
        parts = icon_viewbox.split()
        icon_w = float(parts[2])
        icon_h = float(parts[3])
    else:
        icon_w = float(icon_root.get("width", "100").replace("mm", "").replace("px", ""))
        icon_h = float(icon_root.get("height", "100").replace("mm", "").replace("px", ""))

    # Calculate scale to fit within bounds while maintaining aspect ratio
    scale_x = width / icon_w if icon_w else 1
    scale_y = height / icon_h if icon_h else 1
    scale = min(scale_x, scale_y)

    # Center the icon within the bounds
    scaled_w = icon_w * scale
    scaled_h = icon_h * scale
    offset_x = x + (width - scaled_w) / 2
    offset_y = y + (height - scaled_h) / 2

    # Create a group for the icon
    icon_group = etree.SubElement(root, f"{{{SVG_NS}}}g")
    icon_group.set("id", "injected_icon")
    icon_group.set("transform", f"translate({offset_x},{offset_y}) scale({scale})")

    # Copy icon content (skip defs, copy visible elements)
    for child in icon_root:
        tag_local = etree.QName(child).localname
        if tag_local not in ("defs", "sodipodi:namedview", "namedview", "metadata"):
            icon_group.append(child)


def _inject_png_icon(
    root: etree._Element,
    png_data: tuple,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """
    Inject a PNG icon into the SVG as an embedded image.
    png_data is (base64_data, orig_width, orig_height, mime_type)
    """
    b64_data, orig_w, orig_h, mime = png_data
    
    # Calculate size to fit within bounds while maintaining aspect ratio
    scale_x = width / orig_w if orig_w else 1
    scale_y = height / orig_h if orig_h else 1
    scale = min(scale_x, scale_y)
    
    scaled_w = orig_w * scale
    scaled_h = orig_h * scale
    
    # Center within bounds
    offset_x = x + (width - scaled_w) / 2
    offset_y = y + (height - scaled_h) / 2
    
    # Create image element
    img_elem = etree.SubElement(root, f"{{{SVG_NS}}}image")
    img_elem.set("x", str(offset_x))
    img_elem.set("y", str(offset_y))
    img_elem.set("width", str(scaled_w))
    img_elem.set("height", str(scaled_h))
    img_elem.set(f"{{{XLINK_NS}}}href", f"data:{mime};base64,{b64_data}")
    img_elem.set("preserveAspectRatio", "xMidYMid meet")


def _inject_icons_stacked(
    root: etree._Element,
    icons: list[tuple[str, any]],
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """
    Inject multiple icons stacked vertically.
    icons is a list of (type, data) tuples from _load_icon.
    """
    if not icons:
        return

    num_icons = len(icons)
    icon_height = height / num_icons
    spacing = 2  # mm between icons

    for idx, (icon_type, icon_data) in enumerate(icons):
        icon_y = y + idx * (icon_height + spacing)
        actual_height = icon_height - spacing if idx < num_icons - 1 else icon_height
        if icon_type == "svg":
            _inject_icon(root, icon_data, x, icon_y, width, actual_height)
        elif icon_type == "png":
            _inject_png_icon(root, icon_data, x, icon_y, width, actual_height)


def _add_text_element(
    root: etree._Element,
    text: str,
    x: float,
    y: float,
    font_size: float,
    anchor: str = "middle",
    font_family: str = "Arial",
    font_weight: str = "bold",
    fill: str = "#000000",
) -> None:
    """Add a text element to the SVG."""
    text_elem = etree.SubElement(root, f"{{{SVG_NS}}}text")
    text_elem.set("x", str(x))
    text_elem.set("y", str(y))
    text_elem.set(
        "style",
        f"font-family:{font_family};font-weight:{font_weight};font-size:{font_size}mm;"
        f"text-anchor:{anchor};fill:{fill};",
    )
    text_elem.text = text


def _add_prohibition_overlay(
    root: etree._Element,
    center_x: float,
    center_y: float,
    radius: float,
) -> None:
    """Add prohibition circle and slash overlay."""
    # Red circle
    circle = etree.SubElement(root, f"{{{SVG_NS}}}circle")
    circle.set("cx", str(center_x))
    circle.set("cy", str(center_y))
    circle.set("r", str(radius))
    circle.set(
        "style",
        f"fill:none;stroke:{PROHIBITION_CIRCLE_COLOR};"
        f"stroke-width:{PROHIBITION_STROKE_WIDTH}mm;",
    )

    # Diagonal slash (top-right to bottom-left)
    offset = radius * 0.707  # cos(45°)
    line = etree.SubElement(root, f"{{{SVG_NS}}}line")
    line.set("x1", str(center_x + offset))
    line.set("y1", str(center_y - offset))
    line.set("x2", str(center_x - offset))
    line.set("y2", str(center_y + offset))
    line.set(
        "style",
        f"stroke:{PROHIBITION_SLASH_COLOR};stroke-width:{PROHIBITION_STROKE_WIDTH}mm;"
        "stroke-linecap:round;",
    )


def _export_png(svg_path: Path, png_path: Path, width_px: int, height_px: int, dpi: int = 300, export_area: str = "page", max_dimension: int = 10000) -> bool:
    """Export SVG to PNG using Inkscape CLI.
    
    Args:
        export_area: 'page' for canvas only, 'drawing' for all elements including outside canvas
        max_dimension: Maximum pixel dimension for longest side (Amazon limit is 10000)
    """
    cmd = [
        "inkscape",
        str(svg_path),
        "--export-type=png",
        f"--export-filename={png_path}",
        f"--export-dpi={dpi}",
    ]
    
    if export_area == "drawing":
        cmd.append("--export-area-drawing")
    else:
        cmd.extend([f"--export-width={width_px}", f"--export-height={height_px}"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logging.error("Inkscape export failed: %s", result.stderr)
            return False
        
        # Resize if image exceeds max dimension (Amazon limit)
        if png_path.exists():
            from PIL import Image
            with Image.open(png_path) as img:
                w, h = img.size
                if w > max_dimension or h > max_dimension:
                    # Calculate new size maintaining aspect ratio
                    if w > h:
                        new_w = max_dimension
                        new_h = int(h * max_dimension / w)
                    else:
                        new_h = max_dimension
                        new_w = int(w * max_dimension / h)
                    logging.info("Resizing %s from %dx%d to %dx%d (Amazon max: %d)", 
                                png_path.name, w, h, new_w, new_h, max_dimension)
                    resized = img.resize((new_w, new_h), Image.LANCZOS)
                    resized.save(png_path)
        
        return True
    except subprocess.TimeoutExpired:
        logging.error("Inkscape export timed out")
        return False
    except FileNotFoundError:
        logging.error("Inkscape not found in PATH")
        return False


def _review_with_claude(image_path: Path, product: ProductRow, api_key: str) -> dict:
    """
    Send generated image to Claude Vision API for review.
    Returns a dict with 'approved', 'score', 'feedback'.
    """
    try:
        import anthropic
    except ImportError:
        logging.warning("anthropic package not installed, skipping AI review")
        return {"approved": True, "score": None, "feedback": "AI review skipped (package not installed)"}

    if not api_key:
        return {"approved": True, "score": None, "feedback": "AI review skipped (no API key)"}

    # Read and encode image
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Review this product sign image for Amazon listing quality.

Product details:
- SKU: {product.sku_parent}
- Size: {product.size}
- Layout: {product.layout_mode}
- Sign type: {product.sign_type}
- Text: {product.text_line_1} / {product.text_line_2} / {product.text_line_3}

Evaluate:
1. Text readability (is it clear and properly sized?)
2. Icon visibility (is it clear and well-positioned?)
3. Overall balance (is the layout visually balanced?)
4. Professional appearance (does it look like a quality product image?)

If adjustments are needed, suggest percentage changes for icon_scale and text_scale (e.g., 1.2 = 20% larger, 0.8 = 20% smaller).

Respond with JSON only:
{{"approved": true/false, "score": 1-10, "feedback": "brief feedback", "icon_scale": 1.0, "text_scale": 1.0}}
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        result_text = response.content[0].text
        logging.debug("Claude raw response: %s", result_text)
        
        # Extract JSON from response (may be wrapped in markdown code blocks)
        import re
        json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
        else:
            logging.warning("No JSON found in Claude response: %s", result_text[:200])
            return {"approved": True, "score": None, "feedback": result_text[:200]}
    except Exception as e:
        logging.warning("Claude review failed: %s", e)
        return {"approved": True, "score": None, "feedback": f"Review error: {e}"}


def _review_with_openai(image_path: Path, product: ProductRow, api_key: str) -> dict:
    """
    Send generated image to OpenAI GPT-4 Vision API for review.
    Returns a dict with 'approved', 'score', 'feedback', 'icon_scale', 'text_scale'.
    """
    try:
        import openai
    except ImportError:
        logging.warning("openai package not installed, skipping AI review")
        return {"approved": True, "score": None, "feedback": "AI review skipped (package not installed)"}

    if not api_key:
        return {"approved": True, "score": None, "feedback": "AI review skipped (no API key)"}

    # Read and encode image
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    client = openai.OpenAI(api_key=api_key)

    prompt = f"""You are a graphic design expert reviewing a product sign image for Amazon listing quality.

Product details:
- SKU: {product.sku_parent}
- Size: {product.size} (physical sign dimensions)
- Layout: {product.layout_mode}
- Sign type: {product.sign_type}
- Text: {product.text_line_1} / {product.text_line_2} / {product.text_line_3}

Critically evaluate for VISUAL PRESENCE and IMPACT:
1. Is the icon large enough to be immediately recognizable? Should it be bigger?
2. Is the text bold and readable at a glance? Should it be larger?
3. Is the icon positioned optimally (not too centered, good use of space)?
4. Does the overall design have strong visual impact for a product listing?

Be critical - if elements are too small or poorly positioned, suggest specific scale adjustments.
icon_scale: 1.0 = current size, 1.3 = 30% larger, 0.8 = 20% smaller
text_scale: 1.0 = current size, 1.5 = 50% larger, etc.

Respond with JSON only:
{{"approved": true/false, "score": 1-10, "feedback": "specific feedback", "icon_scale": 1.0, "text_scale": 1.0}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}",
                                "detail": "high"
                            }
                        },
                    ],
                }
            ],
        )

        result_text = response.choices[0].message.content
        logging.debug("OpenAI raw response: %s", result_text)
        
        # Extract JSON from response
        import re
        json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
        else:
            logging.warning("No JSON found in OpenAI response: %s", result_text[:200])
            return {"approved": True, "score": None, "feedback": result_text[:200]}
    except Exception as e:
        logging.warning("OpenAI review failed: %s", e)
        return {"approved": True, "score": None, "feedback": f"Review error: {e}"}


def _inject_graphic_design(
    template_root: etree._Element,
    product: ProductRow,
    icons: list,
    layout,
) -> None:
    """Inject icons and text into a template based on the calculated layout."""
    # Inject icons
    if icons:
        _inject_icons_stacked(
            template_root,
            icons,
            layout.icon_x,
            layout.icon_y,
            layout.icon_width,
            layout.icon_height,
        )

    # Add prohibition overlay (only if sign_type is prohibition)
    if product.sign_type == "prohibition":
        icon_center_x = layout.icon_x + layout.icon_width / 2
        icon_center_y = layout.icon_y + layout.icon_height / 2
        overlay_radius = min(layout.icon_width, layout.icon_height) / 2 * 1.1
        _add_prohibition_overlay(template_root, icon_center_x, icon_center_y, overlay_radius)

    # Add text elements with font from product
    font_family, font_weight = FONTS.get(product.font, ("Arial", "bold"))
    for text_elem in layout.text_elements:
        _add_text_element(
            template_root,
            text_elem["text"],
            text_elem["x"],
            text_elem["y"],
            text_elem["font_size"],
            text_elem.get("anchor", "middle"),
            font_family=font_family,
            font_weight=font_weight,
        )


def _generate_main_image(
    product: ProductRow,
    templates_dir: Path,
    icons_dir: Path,
    output_path: Path,
    bounds: SignBounds,
    icons: list,
    icon_scale: float = 1.0,
    text_scale: float = 1.0,
    dry_run: bool = False,
) -> bool:
    """Generate a single main image with given scale parameters. Returns True on success."""
    text_lines = [product.text_line_1, product.text_line_2, product.text_line_3]
    
    # Calculate layout with scale factors
    layout = _calculate_layout(
        bounds=bounds,
        layout_mode=product.layout_mode,
        num_icons=len(product.icon_files),
        text_lines=text_lines,
        icon_scale=icon_scale,
        text_scale=text_scale,
        size=product.size,
        orientation=product.orientation,
    )

    # Load fresh template
    try:
        template_root = _load_template_svg(templates_dir, product.color, product.size, "main", product.orientation)
    except FileNotFoundError as e:
        logging.error("Template not found: %s", e)
        return False

    # Inject graphic design (icons + text)
    _inject_graphic_design(template_root, product, icons, layout)

    # Save modified SVG to temp file
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
        tmp_svg_path = Path(tmp.name)
        tree = etree.ElementTree(template_root)
        tree.write(str(tmp_svg_path), encoding="utf-8", xml_declaration=True)

    # Get template canvas dimensions
    svg_width = template_root.get("width", "159.4mm").replace("mm", "")
    svg_height = template_root.get("height", "139.4mm").replace("mm", "")
    canvas_width_mm = float(svg_width)
    canvas_height_mm = float(svg_height)

    # Convert mm to pixels at 300 DPI
    dpi = 300
    width_px = int(canvas_width_mm / 25.4 * dpi)
    height_px = int(canvas_height_mm / 25.4 * dpi)

    if dry_run:
        logging.info("[DRY RUN] Would export: %s (%dx%d px)", output_path, width_px, height_px)
        return True
    
    return _export_png(tmp_svg_path, output_path, width_px, height_px, dpi)


def _create_m_number_folder_structure(
    exports_dir: Path,
    product: ProductRow,
    template_folder: Path,
) -> Path | None:
    """Create M Number folder structure based on template.
    
    Returns the path to the created M Number folder, or None if m_number is not set.
    """
    if not product.m_number:
        return None
    
    # Build folder name: M1075 No Dogs Silver Saville
    color_title = product.color.title()  # silver -> Silver
    size_title = product.size.title()  # saville -> Saville
    folder_name = f"{product.m_number} {product.description} {color_title} {size_title}"
    
    m_folder = exports_dir / folder_name
    
    # Copy folder structure from template
    if template_folder.exists():
        import shutil
        if m_folder.exists():
            # Don't overwrite existing folder structure, just ensure subfolders exist
            pass
        else:
            # Ignore desktop.ini and other Windows system files that can cause issues with Google Drive
            def ignore_system_files(directory, files):
                return [f for f in files if f.lower() in ('desktop.ini', 'thumbs.db', '.ds_store')]
            shutil.copytree(template_folder, m_folder, ignore=ignore_system_files)
    else:
        # Create basic structure if template doesn't exist
        m_folder.mkdir(parents=True, exist_ok=True)
        (m_folder / "000 Archive").mkdir(exist_ok=True)
        (m_folder / "000 IMAGE GENERATION").mkdir(exist_ok=True)
        (m_folder / "001 Design" / "000 Archive").mkdir(parents=True, exist_ok=True)
        (m_folder / "001 Design" / "001 MASTER FILE").mkdir(exist_ok=True)
        (m_folder / "001 Design" / "002 MUTOH").mkdir(exist_ok=True)
        (m_folder / "001 Design" / "003 MIMAKI").mkdir(exist_ok=True)
        (m_folder / "001 Design" / "004 ROLAND").mkdir(exist_ok=True)
        (m_folder / "001 Design" / "005 IMAGE GENERATION").mkdir(exist_ok=True)
        (m_folder / "001 Design" / "006 HULK").mkdir(exist_ok=True)
        (m_folder / "001 Design" / "007 EPSON").mkdir(exist_ok=True)
        (m_folder / "001 Design" / "008 ROLF").mkdir(exist_ok=True)
        (m_folder / "002 Images").mkdir(exist_ok=True)
        (m_folder / "003 Blanks").mkdir(exist_ok=True)
        (m_folder / "004 SOPs").mkdir(exist_ok=True)
    
    return m_folder


def _generate_master_design_file(
    product: ProductRow,
    templates_dir: Path,
    icons: list,
    layout,
    m_folder: Path,
) -> bool:
    """Generate master design SVG file and save to M Number folder."""
    if not product.m_number:
        return False
    
    # Load master design template (with portrait support)
    if product.orientation == "portrait":
        template_name = f"{product.color}_{product.size}_portrait_master_design_file.svg"
    else:
        template_name = f"{product.color}_{product.size}_master_design_file.svg"
    template_path = templates_dir / template_name
    
    if not template_path.exists():
        # Fallback to landscape if portrait not found
        if product.orientation == "portrait":
            fallback_name = f"{product.color}_{product.size}_master_design_file.svg"
            fallback_path = templates_dir / fallback_name
            if fallback_path.exists():
                logging.warning("Portrait master design not found, using landscape: %s", fallback_name)
                template_path = fallback_path
            else:
                logging.warning("Master design template not found: %s", template_path)
                return False
        else:
            logging.warning("Master design template not found: %s", template_path)
            return False
    
    try:
        tree = etree.parse(str(template_path))
        template_root = tree.getroot()
    except Exception as e:
        logging.error("Failed to load master design template: %s", e)
        return False
    
    # Inject graphic design (icons + text)
    _inject_graphic_design(template_root, product, icons, layout)
    
    # Save to 001 Design/001 MASTER FILE folder
    master_file_dir = m_folder / "001 Design" / "001 MASTER FILE"
    master_file_dir.mkdir(parents=True, exist_ok=True)
    
    master_file_name = f"{product.m_number} MASTER FILE.svg"
    master_file_path = master_file_dir / master_file_name
    
    try:
        tree = etree.ElementTree(template_root)
        tree.write(str(master_file_path), encoding="utf-8", xml_declaration=True)
        logging.info("Created master design file: %s", master_file_path)
        return True
    except Exception as e:
        logging.error("Failed to save master design file: %s", e)
        return False


def _generate_product_images(
    product: ProductRow,
    templates_dir: Path,
    icons_dir: Path,
    exports_dir: Path,
    dry_run: bool = False,
    ai_review: bool = False,
    ai_provider: str = "openai",
    api_key: str = "",
    max_ai_iterations: int = 3,
    main_only: bool = False,
) -> bool:
    """Generate all images for a single product with optional AI-driven adjustment."""
    # Require m_number for output
    if not product.m_number:
        logging.warning("Skipping product %s: no m_number specified", product.sku_parent)
        return False
    
    m_number = product.m_number
    logging.info("Processing %s (size=%s, color=%s, layout=%s, icon_scale=%.2f, text_scale=%.2f)", 
                 m_number, product.size, product.color, product.layout_mode, product.icon_scale, product.text_scale)

    # Get sign bounds
    bounds = _get_sign_bounds(product.size, product.orientation)

    # Load icons once (supports both SVG and PNG)
    icons = []
    for icon_file in product.icon_files:
        icon_result = _load_icon(icons_dir, icon_file)
        if icon_result is None:
            logging.warning("Icon not found: %s (skipping product %s)", icon_file, m_number)
            return False
        icons.append(icon_result)

    # Create M Number folder structure first
    template_folder = Path("examples/EMPTY COPY FOLDER")
    m_folder = _create_m_number_folder_structure(exports_dir, product, template_folder)
    
    if not m_folder:
        logging.error("Failed to create M Number folder for %s", m_number)
        return False
    
    logging.info("Created M Number folder: %s", m_folder.name)
    
    # Images go directly to 002 Images folder with M Number naming
    images_dir = m_folder / "002 Images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # Use scale factors from product (set via CSV tuning)
    icon_scale = product.icon_scale
    text_scale = product.text_scale
    
    # File naming: M1075 - 001.png, M1075 - 002.png, etc.
    main_png = images_dir / f"{m_number} - 001.png"

    # No AI review - just generate once
    if not _generate_main_image(
        product, templates_dir, icons_dir, main_png, bounds, icons,
        icon_scale, text_scale, dry_run
    ):
        return False
    logging.info("Exported: %s", main_png.name)

    # Get canvas dimensions for additional images
    try:
        template_root = _load_template_svg(templates_dir, product.color, product.size, "main", product.orientation)
        svg_width = template_root.get("width", "159.4mm").replace("mm", "")
        svg_height = template_root.get("height", "139.4mm").replace("mm", "")
        canvas_width_mm = float(svg_width)
        canvas_height_mm = float(svg_height)
        dpi = 300
        width_px = int(canvas_width_mm / 25.4 * dpi)
        height_px = int(canvas_height_mm / 25.4 * dpi)
    except FileNotFoundError:
        width_px, height_px, dpi = 1882, 1647, 300  # Default fallback

    # Calculate layout once for reuse across templates
    text_lines = [product.text_line_1, product.text_line_2, product.text_line_3]
    layout = _calculate_layout(
        bounds=bounds,
        layout_mode=product.layout_mode,
        num_icons=len(product.icon_files),
        text_lines=text_lines,
        icon_scale=icon_scale,
        text_scale=text_scale,
        size=product.size,
        orientation=product.orientation,
    )

    # Skip additional images if main_only mode (for fast QA preview)
    if main_only:
        logging.info("Main-only mode: skipping dimensions, peel_and_stick, rear images")
        return True

    # Generate dimensions image with graphic design
    try:
        dim_template = _load_template_svg(templates_dir, product.color, product.size, "dimensions", product.orientation)
        _inject_graphic_design(dim_template, product, icons, layout)
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp_dim_path = Path(tmp.name)
            tree = etree.ElementTree(dim_template)
            tree.write(str(tmp_dim_path), encoding="utf-8", xml_declaration=True)

        dim_png = images_dir / f"{m_number} - 002.png"
        if dry_run:
            logging.info("[DRY RUN] Would export: %s", dim_png)
        else:
            if _export_png(tmp_dim_path, dim_png, width_px, height_px, dpi):
                logging.info("Exported: %s", dim_png.name)
        tmp_dim_path.unlink(missing_ok=True)
    except FileNotFoundError:
        logging.warning("Dimensions template not found for %s/%s", product.color, product.size)

    # Generate peel_and_stick with graphic design (same position as main)
    try:
        peel_template = _load_template_svg(templates_dir, product.color, product.size, "peel_and_stick", product.orientation)
        _inject_graphic_design(peel_template, product, icons, layout)
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp_peel_path = Path(tmp.name)
            tree = etree.ElementTree(peel_template)
            tree.write(str(tmp_peel_path), encoding="utf-8", xml_declaration=True)

        # Get peel_and_stick canvas dimensions (may differ from main)
        peel_width = peel_template.get("width", "159.4mm").replace("mm", "")
        peel_height = peel_template.get("height", "139.4mm").replace("mm", "")
        peel_width_px = int(float(peel_width) / 25.4 * dpi)
        peel_height_px = int(float(peel_height) / 25.4 * dpi)

        peel_png = images_dir / f"{m_number} - 003.png"
        if dry_run:
            logging.info("[DRY RUN] Would export: %s", peel_png)
        else:
            # Use export_area="drawing" to include elements outside canvas
            if _export_png(tmp_peel_path, peel_png, peel_width_px, peel_height_px, dpi, export_area="drawing"):
                logging.info("Exported: %s", peel_png.name)
        tmp_peel_path.unlink(missing_ok=True)
    except FileNotFoundError:
        pass  # Optional template

    # Generate rear image (static, no graphic design needed)
    try:
        rear_template = _load_template_svg(templates_dir, product.color, product.size, "rear", product.orientation)
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp_rear_path = Path(tmp.name)
            tree = etree.ElementTree(rear_template)
            tree.write(str(tmp_rear_path), encoding="utf-8", xml_declaration=True)

        rear_png = images_dir / f"{m_number} - 004.png"
        if dry_run:
            logging.info("[DRY RUN] Would export: %s", rear_png)
        else:
            if _export_png(tmp_rear_path, rear_png, width_px, height_px, dpi):
                logging.info("Exported: %s", rear_png.name)
        tmp_rear_path.unlink(missing_ok=True)
    except FileNotFoundError:
        pass  # Optional template

    # Generate master design file
    if not dry_run:
        _generate_master_design_file(product, templates_dir, icons, layout, m_folder)

    return True


def main():
    parser = argparse.ArgumentParser(description="Generate Amazon product images from templates")
    parser.add_argument("--csv", type=Path, default=Path("products.csv"), help="Input CSV file")
    parser.add_argument("--templates", type=Path, default=Path("assets"), help="Templates directory")
    parser.add_argument("--icons", type=Path, default=Path("001 ICONS"), help="Icons directory")
    parser.add_argument("--exports", type=Path, default=Path("exports"), help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview without exporting")
    parser.add_argument("--ai-review", action="store_true", help="Enable AI Vision review")
    parser.add_argument("--ai-provider", type=str, default="openai", choices=["openai", "claude"],
                        help="AI provider for review (default: openai)")
    parser.add_argument("--api-key", type=str, 
                        default=os.environ.get("OPENAI_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")),
                        help="API key (or set OPENAI_API_KEY or ANTHROPIC_API_KEY env var)")
    parser.add_argument("--main-only", action="store_true", 
                        help="Generate only the main image (001) for faster QA preview")
    parser.add_argument("--m-number", type=str, default=None,
                        help="Process only a specific M number (e.g., M1220)")

    args = parser.parse_args()

    _setup_logging(args.exports)
    logging.info("=" * 60)
    logging.info("Amazon Image Generator v2 - Starting")
    logging.info("CSV: %s", args.csv)
    logging.info("Templates: %s", args.templates)
    logging.info("Icons: %s", args.icons)
    logging.info("Exports: %s", args.exports)
    logging.info("Dry run: %s", args.dry_run)
    logging.info("AI review: %s (provider: %s)", args.ai_review, args.ai_provider if args.ai_review else "N/A")
    logging.info("=" * 60)

    # Validate directories
    if not args.templates.exists():
        logging.error("Templates directory not found: %s", args.templates)
        sys.exit(1)
    if not args.icons.exists():
        logging.error("Icons directory not found: %s", args.icons)
        sys.exit(1)

    # Read products
    try:
        products = _read_products_csv(args.csv)
    except Exception as e:
        logging.error("Failed to read CSV: %s", e)
        sys.exit(1)

    logging.info("Loaded %d products from CSV", len(products))

    # Filter to specific M number if requested
    if args.m_number:
        products = [p for p in products if p.m_number == args.m_number]
        if not products:
            logging.error("M number %s not found in CSV", args.m_number)
            sys.exit(1)
        logging.info("Filtered to M number: %s", args.m_number)

    # Process each product
    success_count = 0
    fail_count = 0

    for product in products:
        try:
            if _generate_product_images(
                product,
                args.templates,
                args.icons,
                args.exports,
                args.dry_run,
                args.ai_review,
                args.ai_provider,
                args.api_key,
                main_only=args.main_only,
            ):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            logging.error("Error processing %s: %s", product.sku_parent, e)
            fail_count += 1

    logging.info("=" * 60)
    logging.info("Completed: %d success, %d failed", success_count, fail_count)
    logging.info("=" * 60)

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
