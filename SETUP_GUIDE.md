# Amazon Publisher - Setup Guide for Gabby's PC

## Overview

The Amazon Publisher is a web-based tool for generating product images, lifestyle images, and Amazon flatfiles for signage products. It automates the entire workflow from product CSV to ready-to-upload Amazon listings.

---

## Prerequisites

### 1. Python 3.11+

**Check if Python is installed:**
```
python --version
```

If not installed or version is below 3.11:
1. Download Python 3.11+ from https://www.python.org/downloads/
2. **IMPORTANT:** During installation, check ✅ "Add Python to PATH"
3. Restart your PC after installation

### 2. Inkscape (Required for Image Generation)

Inkscape is used to render SVG templates into PNG images.

1. Download from https://inkscape.org/release/
2. Install to the default location: `C:\Program Files\Inkscape\`
3. The pipeline expects Inkscape at `C:\Program Files\Inkscape\bin\inkscape.exe`

### 3. Python Packages

Open Command Prompt (cmd) and run:
```
pip install flask lxml anthropic openai boto3 openpyxl requests Pillow
```

Or navigate to this folder and run:
```
pip install -r requirements.txt
pip install flask
```

---

## Required Files

Make sure these files exist in this folder:

| File | Purpose |
|------|---------|
| `config.bat` | API keys (Anthropic, OpenAI, Cloudflare R2, eBay, Etsy) |
| `products.csv` | Product definitions |
| `publisher_web.py` | Main web application |
| `generate_images_v2.py` | Image generation script |
| `generate_lifestyle_images.py` | AI lifestyle image generation |
| `generate_amazon_content.py` | Amazon content & flatfile generation |
| `assets/` | SVG templates for each size/color |
| `001 ICONS/` | Icon PNG files |

---

## Configuration

### config.bat

This file contains all API keys. It should already be configured, but verify it exists and contains:

```batch
@echo off
set ANTHROPIC_API_KEY=sk-ant-...
set OPENAI_API_KEY=sk-proj-...
set R2_ACCOUNT_ID=...
set R2_ACCESS_KEY_ID=...
set R2_SECRET_ACCESS_KEY=...
set R2_BUCKET_NAME=productimages
set R2_PUBLIC_URL=https://pub-...r2.dev
```

**If config.bat is missing or empty**, copy it from the main folder:
`G:\My Drive\003 APPS\019 - AMAZON PUBLISHER REV 2.0\config.bat`

---

## Starting the Publisher

### Option 1: Double-click PUBLISHER_WEB.bat

If this file exists, just double-click it.

### Option 2: Manual Start

1. Open Command Prompt
2. Navigate to this folder:
   ```
   cd "G:\My Drive\003 APPS\AMAZON PUBLISHER - Gabby"
   ```
3. Run:
   ```
   call config.bat
   python publisher_web.py
   ```
4. Open browser to http://localhost:5000

---

## Workflow

### Step 1: Prepare Products CSV

Edit `products.csv` with your products. Each row needs:
- `m_number` - Unique ID (e.g., M1260)
- `description` - Product description
- `size` - dracula, saville, dick, barzan, or baby_jesus
- `color` - silver, gold, or white
- `layout_mode` - A, B, C, etc.
- `icon_files` - Icon filename from 001 ICONS folder
- `text_line_1`, `text_line_2`, `text_line_3` - Text on sign (if any)
- `orientation` - landscape or portrait

### Step 2: Generate Images (Pipeline Tab)

1. Click **"Run Amazon Pipeline"**
2. Wait for images to generate (uses Inkscape)
3. M folders will appear in `exports/`

### Step 3: QA Review (QA Review Tab)

1. Click **"↻ Refresh"** to load products
2. Review each product image
3. Adjust **Icon Scale** and **Text Scale** if needed
4. Click **Approved** or **Rejected** for each
5. Click **Save** to save your changes
6. Optionally click **"🖼️ Lifestyle"** to generate lifestyle images

### Step 4: Generate Content (QA Review Tab)

1. Click **"📦 Finalize All Approved & Generate Content"**
2. Click **"🤖 Auto-generate with AI"** to get description/use cases
3. Click **"Start Pipeline"**
4. Wait for:
   - All images to regenerate
   - Lifestyle images to generate
   - Amazon content to generate (AI)
   - Images to upload to cloud
   - Flatfile to be created

### Step 5: Download Flatfile

The flatfile will be saved as `amazon_flatfile_YYYYMMDD_HHMM.xlsx` in this folder.

---

## Troubleshooting

### "Python is not recognized"
- Python is not installed or not in PATH
- Reinstall Python and check "Add to PATH"

### "No module named 'flask'" (or other module)
```
pip install flask lxml anthropic openai boto3 openpyxl requests Pillow
```

### "Inkscape not found"
- Install Inkscape from https://inkscape.org/
- Make sure it's at `C:\Program Files\Inkscape\bin\inkscape.exe`

### "ANTHROPIC_API_KEY not set"
- Make sure `config.bat` exists and has the API key
- Run `call config.bat` before starting the server

### Images not generating
- Check Inkscape is installed
- Check the `assets/` folder has SVG templates
- Check the `001 ICONS/` folder has icon files

### Pipeline crashes immediately
Run this to check all dependencies:
```
python -c "import flask, lxml, anthropic, openai, boto3, openpyxl, requests, PIL; print('All packages OK')"
```

If any fail, install the missing package with `pip install <package_name>`

---

## File Locations

| What | Where |
|------|-------|
| Product images | `exports/M#### .../002 Images/` |
| Master SVG files | `exports/M#### .../001 Design/001 MASTER FILE/` |
| Flatfiles | This folder (`amazon_flatfile_*.xlsx`) |
| Shared M folders | `G:\My Drive\001 NBNE\001 M` |

---

## Quick Start Checklist

- [ ] Python 3.11+ installed (with PATH)
- [ ] Inkscape installed
- [ ] `pip install flask lxml anthropic openai boto3 openpyxl requests Pillow`
- [ ] `config.bat` exists with API keys
- [ ] `assets/` folder has SVG templates
- [ ] `001 ICONS/` folder has icon files
- [ ] Run `PUBLISHER_WEB.bat` or `python publisher_web.py`
- [ ] Open http://localhost:5000

---

## Support

If you encounter issues, check:
1. The command prompt window for error messages
2. The browser console (F12 → Console tab) for JavaScript errors
3. Contact the main developer with the error message
