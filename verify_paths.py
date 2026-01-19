"""Verify all paths are relative to Gabby's folder."""
from pathlib import Path
import csv

print("=" * 60)
print("PATH VERIFICATION FOR GABBY'S FOLDER")
print("=" * 60)

# Get current working directory
cwd = Path.cwd()
print(f"\nWorking Directory: {cwd}")
print()

# Check critical files and folders
checks = {
    "products.csv": Path("products.csv"),
    "config.bat": Path("config.bat"),
    "exports/": Path("exports"),
    "001 ICONS/": Path("001 ICONS"),
    "assets/": Path("assets"),
    "003 FLATFILES/": Path("003 FLATFILES"),
}

print("File/Folder Checks:")
print("-" * 60)
all_good = True
for name, path in checks.items():
    exists = path.exists()
    status = "[OK]     " if exists else "[MISSING]"
    print(f"{status:12} {name:20} -> {path.absolute()}")
    if not exists:
        all_good = False

# Check products.csv content
print("\n" + "=" * 60)
print("PRODUCTS.CSV CONTENT")
print("=" * 60)
csv_path = Path("products.csv")
if csv_path.exists():
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"Total products: {len(rows)}")
    if rows:
        print(f"First M number: {rows[0].get('m_number', 'N/A')}")
        print(f"Columns: {', '.join(rows[0].keys())}")
else:
    print("products.csv not found!")

# Check icons
print("\n" + "=" * 60)
print("001 ICONS FOLDER")
print("=" * 60)
icons_dir = Path("001 ICONS")
if icons_dir.exists():
    png_files = list(icons_dir.glob("*.png"))
    print(f"PNG files found: {len(png_files)}")
    if png_files:
        print(f"Example icons: {', '.join([f.name for f in png_files[:5]])}")
else:
    print("001 ICONS folder not found!")

# Check exports
print("\n" + "=" * 60)
print("EXPORTS FOLDER")
print("=" * 60)
exports_dir = Path("exports")
if exports_dir.exists():
    m_folders = [f for f in exports_dir.iterdir() if f.is_dir() and f.name.startswith("M")]
    print(f"M folders found: {len(m_folders)}")
    if m_folders:
        print(f"Example M folders: {', '.join([f.name for f in m_folders[:3]])}")
else:
    print("exports folder not found!")

# Check assets
print("\n" + "=" * 60)
print("ASSETS FOLDER (SVG Templates)")
print("=" * 60)
assets_dir = Path("assets")
if assets_dir.exists():
    svg_files = list(assets_dir.glob("*.svg"))
    print(f"SVG templates found: {len(svg_files)}")
    if svg_files:
        print(f"Example templates: {', '.join([f.name for f in svg_files[:5]])}")
else:
    print("assets folder not found!")

print("\n" + "=" * 60)
if all_good:
    print("[SUCCESS] ALL PATHS VERIFIED - SOFTWARE READY TO USE")
else:
    print("[WARNING] SOME PATHS MISSING - CHECK ABOVE")
print("=" * 60)
