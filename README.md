# Signage Publisher REV 2.0

Multi-channel product listing publisher for Amazon, eBay, and Etsy with automated image generation and AI content.

## Features

- **Image Generation**: Creates product images from SVG templates (main, dimensions, peel & stick, rear, lifestyle)
- **AI Content**: Generates SEO-optimized titles, descriptions, bullet points using Claude API
- **Lifestyle Images**: AI-generated contextual product photos using DALL-E 3
- **Image Hosting**: Automatic upload to Cloudflare R2 with public URLs
- **Multi-Channel Publishing**:
  - **Amazon**: Flatfile XLSX export for bulk upload
  - **eBay**: Direct API publishing with Promoted Listings support
  - **Etsy**: Shop Uploader XLSX generation

## Quick Start

**Double-click `PUBLISH.bat`** to open the main menu and select your channel.

## Setup

### Prerequisites

1. **Python 3.11+** - Download from [python.org](https://python.org)
2. **Inkscape** - Download from [inkscape.org](https://inkscape.org/release/)
   - Must be added to system PATH

### Installation

1. Double-click `install_dependencies.bat` to install Python packages
2. Copy `config_template.bat` to `config.bat`
3. Edit `config.bat` with your API keys (already configured if provided)

## Usage

### Main Menu (Recommended)

Double-click **`PUBLISH.bat`** to open the interactive menu with all options.

---

## End-to-End Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: Create products.csv with product data                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: Run Amazon Pipeline [1]                                │
│  - Generates images (main, dimensions, peel & stick, rear)      │
│  - Generates lifestyle images                                   │
│  - Generates AI content (titles, descriptions, bullets)         │
│  - Uploads images to Cloudflare R2                              │
│  - Creates amazon_flatfile.xlsx                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: Staff adds EAN codes to amazon_flatfile.xlsx           │
│  → Upload to Amazon Seller Central                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: Create XLSM flatfile in 003 FLATFILES/                 │
│  - Copy from template                                           │
│  - Add channel-specific pricing                                 │
│  - Add product data from amazon_flatfile.xlsx                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: Run eBay Pipeline [2]                                  │
│  - Publishes listings directly to eBay                          │
│  - Creates multi-variation listings                             │
│  - Auto-promotes with 5% ad rate (optional)                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: Run Etsy Pipeline [3]                                  │
│  - Converts PNG images to JPEG (white background)               │
│  - Generates Shop Uploader XLSX file                            │
│  → Staff uploads to shopuploader.com                            │
└─────────────────────────────────────────────────────────────────┘
```

---

### Channel-Specific Commands

#### Amazon Pipeline

```batch
run_full_pipeline.bat
```

Or via menu: **Option [1]**

**Output**: `amazon_flatfile.xlsx` + images in `exports/`

**Next step**: Add EAN codes, then upload to Amazon Seller Central

---

#### eBay Pipeline

```batch
run_ebay_flatfile.bat "003 FLATFILES\YOUR_FLATFILE.xlsm" --promote --ad-rate 5.0
```

Or via menu: **Option [2]**

| Flag | Description |
|------|-------------|
| `--promote` | Auto-promote with General strategy (Cost Per Sale) |
| `--ad-rate 5.0` | Set ad rate percentage (default 5%) |
| `--dry-run` | Preview without publishing |

**Result**: Listings published directly to eBay with variations

---

#### Etsy Pipeline

```batch
run_etsy_pipeline.bat "003 FLATFILES\YOUR_FLATFILE.xlsm"
```

Or via menu: **Option [3]**

**Output**: `*_shop_uploader.xlsx` in `003 FLATFILES/`

**Next step**: Upload to [Shop Uploader](https://www.shopuploader.com/)

---

### Utility Scripts

| Script | Description |
|--------|-------------|
| `run_generate_images.bat` | Generate product images only |
| `run_generate_content.bat` | Generate content + upload images |
| `run_lifestyle_images.bat` | Generate lifestyle images only |
| `run_qa_server_v2.bat` | Start QA review server |

## Input File: products.csv

| Column | Description | Example |
|--------|-------------|---------|
| m_number | Product M number | M1075 |
| description | Short description | No Dogs |
| size | Product size | saville, dick, barzan, a5, a4, a3 |
| color | Color variant | silver, white, gold |
| layout_mode | Layout template | B |
| icon_files | Icon filename(s) | dog_prohibited.png |
| text_line_1 | Main text | NO DOGS |
| text_line_2 | Secondary text | (optional) |
| text_line_3 | Tertiary text | (optional) |
| orientation | landscape/portrait | landscape |
| font | Font choice | arial_bold, arial_heavy |
| material | Material type | 1mm_aluminium |
| lifestyle_image | Generate lifestyle? | yes / (blank) |

## Output

- **exports/** - Product folders with images and design files
- **amazon_flatfile.xlsx** - Ready for Amazon Seller Central upload

## Folder Structure

```
019 - AMAZON PUBLISHER REV 2.0/
├── assets/              # SVG templates
├── 001 ICONS/           # Product icons
├── examples/            # Example files and templates
├── exports/             # Generated output
├── products.csv         # Input product data
├── config.bat           # API keys (DO NOT SHARE)
├── run_full_pipeline.bat
├── run_generate_images.bat
├── run_generate_content.bat
└── run_lifestyle_images.bat
```

## API Keys Required

- **ANTHROPIC_API_KEY** - Claude API for content generation
- **OPENAI_API_KEY** - DALL-E 3 for lifestyle images
- **R2_*** - Cloudflare R2 for image hosting

## Costs (Approximate)

- Claude content: ~$0.01 per product
- DALL-E lifestyle: ~$0.04 per image
- Cloudflare R2: Free (10GB storage, 10M requests/month)
- Shop Uploader (Etsy): $5-39/month depending on listing volume

## Flatfiles

Product flatfiles are stored in `003 FLATFILES/`. Each flatfile contains:
- Parent product with variation theme
- Child products with SKU, title, description, images, pricing
- Size and colour variations

Example flatfiles:
- `NODOGS SIGNAGE FLATFILE REV1.xlsm`
- `NOENTRY SIGNAGE FLATFILE REV1.xlsm`
- `PRIVATE SIGNAGE FLATFILE REV1.xlsm`
- `KEEP GATE CLOSED SIGNAGE FLATFILE REV1.xlsm`

## Troubleshooting

### eBay "Token expired"
Run `python ebay_auth.py --authorize` to re-authenticate.

### Etsy images have black background
The Etsy pipeline automatically converts PNGs to JPEGs with white backgrounds.

### Missing lifestyle images in flatfile
Ensure lifestyle images (005.png) exist in the product's `002 Images` folder before running content generation.
