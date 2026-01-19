# Amazon Publisher - Staff Guide

## Getting Started

### First Time Setup

1. **Open your workspace folder** - You should have a folder named `AMAZON PUBLISHER - [Your Name]`
2. **Install Python dependencies** (first time only):
   - Double-click `install_dependencies.bat`
   - Wait for it to complete

3. **Start the web interface**:
   - Double-click `PUBLISHER_WEB.bat`
   - Your browser will open to `http://localhost:5000`

---

## Workflow Overview

The publishing workflow has 3 main stages:

```
1. CREATE PRODUCTS    →    2. QA REVIEW    →    3. PUBLISH
   (products.csv)          (approve images)      (Amazon/eBay/Etsy)
```

---

## Step 1: Create Products (products.csv)

### Opening the Products File

1. Open `products.csv` in Excel or Google Sheets
2. Each row = one product variant

### Required Columns

| Column | Description | Example |
|--------|-------------|---------|
| `m_number` | Unique ID (M + number) | M1200 |
| `description` | Product name | No Entry Sign |
| `icon` | Icon filename from 001 ICONS | noentry.svg |
| `color` | Material color | Gold, Silver, White |
| `size` | Size code | Dracula, Saville, Dick, Barzan, Baby_jesus |
| `material` | Material type | 1mm_aluminium |
| `mounting` | Mounting type | self_adhesive, screw_mount |
| `layout_mode` | Layout template | icon_top, text_only, icon_left |
| `text_line_1` | Main text | NO ENTRY |
| `text_line_2` | Secondary text (optional) | Authorised Personnel Only |
| `lifestyle_image` | Generate lifestyle? | yes, no |
| `qa_status` | Leave empty initially | (blank) |

### Size Reference

| Code | Dimensions | Price Tier |
|------|------------|------------|
| Dracula | 95mm x 95mm | £10.99 |
| Saville | 115mm x 95mm | £12.99 |
| Dick | 140mm x 90mm | £14.99 |
| Barzan | 194mm x 143mm | £18.99 |
| Baby_jesus | 290mm x 190mm | £21.99 |

### Tips for products.csv

- **M Numbers**: Use sequential numbers (M1200, M1201, M1202...)
- **Check your M numbers don't clash** with other staff members
- **Icons**: Check `001 ICONS` folder for available icons
- **Start small**: Test with 2-3 products first

---

## Step 2: Generate Images

1. In the web interface, go to the **Pipeline** tab
2. Click **Run Amazon Pipeline**
3. Wait for images to generate (watch the progress)

The pipeline will:
- Generate product images (main, dimensions, mounting, rear views)
- Generate lifestyle images (if enabled)
- Upload images to cloud storage

---

## Step 3: QA Review

1. Go to the **QA Review** tab
2. Review each product image
3. For each product:
   - Click **✓ Approve** if the image looks good
   - Click **✗ Reject** if there are issues
   - Add comments if needed

### Adjusting Images

If an image needs tweaking:
- **Icon Scale**: Make the icon bigger/smaller (0.5 - 2.0)
- **Text Scale**: Make text bigger/smaller (0.5 - 2.0)
- Click **🔄 Regenerate** after adjusting

### Finalizing

Once all products are approved:
1. Click **📦 Finalize All Approved & Generate Content**
2. Enter the **Signage Theme** (e.g., "No Entry warning sign for restricted areas")
3. Enter **Target Use Cases** (e.g., "offices, warehouses, construction sites")
4. Click **Start Pipeline**

This generates:
- Amazon listing content (titles, descriptions, bullet points)
- Amazon flatfile (XLSX)
- Lifestyle images with context

---

## Step 4: Publish to Channels

### Amazon

1. Open the generated flatfile in `003 FLATFILES`
2. Add EAN codes (from `004 CODES` if available)
3. Upload to Amazon Seller Central

### eBay

1. In the web interface, select your flatfile
2. Choose options:
   - **Promote**: Enable promoted listings (5% ad rate)
   - **Dry run**: Preview without publishing
3. Click **Run eBay Pipeline**

### Etsy

1. Select your flatfile
2. Click **Run Etsy Pipeline**
3. This generates a Shop Uploader file
4. Upload to [Shop Uploader](https://www.shopuploader.com/)

---

## Troubleshooting

### "config.bat not found"
- Copy `config_template.bat` to `config.bat`
- Ask your manager for the API keys

### Images not generating
- Check the output log for errors
- Ensure `products.csv` is saved and closed
- Try with a single product first

### Web interface won't start
- Check if another instance is running (close it first)
- Try a different port: edit `PUBLISHER_WEB.bat`

### eBay authentication error
- Run `run_ebay_auth.bat` to refresh tokens
- Ask your manager if tokens have expired

---

## File Locations

| What | Where |
|------|-------|
| Product definitions | `products.csv` |
| Generated images | `exports/M####/002 Images/` |
| Output flatfiles | `003 FLATFILES/` |
| Icons | `001 ICONS/` |
| Layout templates | `002 LAYOUTS/` |

---

## Getting Help

- Check the error messages in the output log
- Ask your manager for assistance
- Don't modify Python files unless instructed

---

## Quick Reference

### Starting Work
```
1. Double-click PUBLISHER_WEB.bat
2. Edit products.csv
3. Run pipeline
4. QA review
5. Finalize & publish
```

### Keyboard Shortcuts (QA Review)
- `A` - Approve current product
- `R` - Reject current product
- `→` - Next product
- `←` - Previous product
