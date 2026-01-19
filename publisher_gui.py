#!/usr/bin/env python3
"""
Signage Publisher GUI

A graphical interface for staff to run the publishing pipeline
across Amazon, eBay, and Etsy channels.
"""

import csv
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path

# Key columns to display in products.csv editor
PRODUCTS_COLUMNS = [
    "m_number",
    "description", 
    "size",
    "color",
    "layout_mode",
    "icon_files",
    "text_line_1",
    "orientation",
    "lifestyle_image",
    "qa_status",
]

# All columns in products.csv (for saving)
ALL_COLUMNS = [
    "m_number", "description", "size", "color", "layout_mode", "icon_files",
    "text_line_1", "text_line_2", "text_line_3", "orientation", "font",
    "material", "mounting_type", "lifestyle_image", "qa_status", "qa_comment",
    "icon_scale", "text_scale", "ebay_listing_id"
]


class PublisherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Signage Publisher")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)
        
        # Set working directory to script location
        self.app_dir = Path(__file__).parent
        os.chdir(self.app_dir)
        
        # Load config
        self.load_config()
        
        # Store products data
        self.products_data = []
        
        # Create UI
        self.create_widgets()
        
        # Refresh flatfile list and load products
        self.refresh_flatfiles()
        self.load_products_csv()
    
    def load_config(self):
        """Load environment variables from config.bat."""
        config_path = self.app_dir / "config.bat"
        if config_path.exists():
            with open(config_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("set ") and "=" in line:
                        # Parse: set VAR=value
                        parts = line[4:].split("=", 1)
                        if len(parts) == 2:
                            os.environ[parts[0]] = parts[1]
    
    def create_widgets(self):
        """Create the main UI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="Signage Publisher", 
            font=("Segoe UI", 18, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Pipeline
        pipeline_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(pipeline_tab, text="Pipeline")
        
        # Tab 2: Products CSV
        products_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(products_tab, text="Products CSV")
        
        # === PIPELINE TAB ===
        self.create_pipeline_tab(pipeline_tab)
        
        # === PRODUCTS TAB ===
        self.create_products_tab(products_tab)
    
    def create_pipeline_tab(self, parent):
        """Create the pipeline tab content."""
        # Workflow info
        workflow_label = ttk.Label(
            parent,
            text="Workflow: products.csv → Amazon → Create XLSM flatfile → eBay/Etsy",
            font=("Segoe UI", 9)
        )
        workflow_label.pack(pady=(0, 15))
        
        # === Step 1: Amazon Pipeline ===
        amazon_frame = ttk.LabelFrame(parent, text="Step 1: Amazon Pipeline", padding="10")
        amazon_frame.pack(fill=tk.X, pady=(0, 10))
        
        amazon_desc = ttk.Label(
            amazon_frame,
            text="Generate images, content, and flatfile from products.csv"
        )
        amazon_desc.pack(anchor=tk.W)
        
        self.amazon_btn = ttk.Button(
            amazon_frame,
            text="Run Amazon Pipeline",
            command=self.run_amazon_pipeline
        )
        self.amazon_btn.pack(pady=(10, 0))
        
        # === Step 2: Select Flatfile ===
        flatfile_frame = ttk.LabelFrame(parent, text="Step 2: Select Flatfile for eBay/Etsy", padding="10")
        flatfile_frame.pack(fill=tk.X, pady=(0, 10))
        
        flatfile_row = ttk.Frame(flatfile_frame)
        flatfile_row.pack(fill=tk.X)
        
        flatfile_label = ttk.Label(flatfile_row, text="Flatfile:")
        flatfile_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.flatfile_var = tk.StringVar()
        self.flatfile_combo = ttk.Combobox(
            flatfile_row,
            textvariable=self.flatfile_var,
            state="readonly",
            width=50
        )
        self.flatfile_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        refresh_btn = ttk.Button(
            flatfile_row,
            text="↻",
            width=3,
            command=self.refresh_flatfiles
        )
        refresh_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # === Step 3: eBay/Etsy Pipelines ===
        channels_frame = ttk.LabelFrame(parent, text="Step 3: Publish to Channels", padding="10")
        channels_frame.pack(fill=tk.X, pady=(0, 10))
        
        # eBay row
        ebay_row = ttk.Frame(channels_frame)
        ebay_row.pack(fill=tk.X, pady=(0, 10))
        
        self.ebay_btn = ttk.Button(
            ebay_row,
            text="Run eBay Pipeline",
            command=self.run_ebay_pipeline,
            width=20
        )
        self.ebay_btn.pack(side=tk.LEFT)
        
        self.ebay_promote_var = tk.BooleanVar(value=True)
        ebay_promote_cb = ttk.Checkbutton(
            ebay_row,
            text="Promote (5% ad rate)",
            variable=self.ebay_promote_var
        )
        ebay_promote_cb.pack(side=tk.LEFT, padx=(15, 0))
        
        self.ebay_dryrun_var = tk.BooleanVar(value=False)
        ebay_dryrun_cb = ttk.Checkbutton(
            ebay_row,
            text="Dry run",
            variable=self.ebay_dryrun_var
        )
        ebay_dryrun_cb.pack(side=tk.LEFT, padx=(15, 0))
        
        # Etsy row
        etsy_row = ttk.Frame(channels_frame)
        etsy_row.pack(fill=tk.X)
        
        self.etsy_btn = ttk.Button(
            etsy_row,
            text="Run Etsy Pipeline",
            command=self.run_etsy_pipeline,
            width=20
        )
        self.etsy_btn.pack(side=tk.LEFT)
        
        etsy_note = ttk.Label(
            etsy_row,
            text="(Generates Shop Uploader file for manual upload)",
            font=("Segoe UI", 8)
        )
        etsy_note.pack(side=tk.LEFT, padx=(15, 0))
        
        # === Output Log ===
        log_frame = ttk.LabelFrame(parent, text="Output", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            height=15
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            parent,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.pack(fill=tk.X)
    
    def create_products_tab(self, parent):
        """Create the products CSV editor tab."""
        # Toolbar
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        load_btn = ttk.Button(toolbar, text="Reload", command=self.load_products_csv)
        load_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        save_btn = ttk.Button(toolbar, text="Save", command=self.save_products_csv)
        save_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        add_btn = ttk.Button(toolbar, text="Add Row", command=self.add_product_row)
        add_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        delete_btn = ttk.Button(toolbar, text="Delete Selected", command=self.delete_product_row)
        delete_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Product count label
        self.product_count_var = tk.StringVar(value="0 products")
        count_label = ttk.Label(toolbar, textvariable=self.product_count_var)
        count_label.pack(side=tk.RIGHT)
        
        # Treeview for products
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Treeview
        self.products_tree = ttk.Treeview(
            tree_frame,
            columns=PRODUCTS_COLUMNS,
            show="headings",
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )
        self.products_tree.pack(fill=tk.BOTH, expand=True)
        
        y_scroll.config(command=self.products_tree.yview)
        x_scroll.config(command=self.products_tree.xview)
        
        # Configure columns
        col_widths = {
            "m_number": 70,
            "description": 250,
            "size": 80,
            "color": 60,
            "layout_mode": 50,
            "icon_files": 120,
            "text_line_1": 100,
            "orientation": 80,
            "lifestyle_image": 80,
            "qa_status": 70,
        }
        
        for col in PRODUCTS_COLUMNS:
            self.products_tree.heading(col, text=col, anchor=tk.W)
            self.products_tree.column(col, width=col_widths.get(col, 100), minwidth=50)
        
        # Double-click to edit
        self.products_tree.bind("<Double-1>", self.edit_product_cell)
    
    def load_products_csv(self):
        """Load products.csv into the treeview."""
        csv_path = self.app_dir / "products.csv"
        if not csv_path.exists():
            return
        
        # Clear existing items
        for item in self.products_tree.get_children():
            self.products_tree.delete(item)
        
        self.products_data = []
        
        try:
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.products_data.append(row)
                    values = [row.get(col, "") for col in PRODUCTS_COLUMNS]
                    self.products_tree.insert("", tk.END, values=values)
            
            self.product_count_var.set(f"{len(self.products_data)} products")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load products.csv: {e}")
    
    def save_products_csv(self):
        """Save products data back to CSV."""
        csv_path = self.app_dir / "products.csv"
        
        # Update products_data from treeview
        self.products_data = []
        for item in self.products_tree.get_children():
            values = self.products_tree.item(item, "values")
            row = {}
            for i, col in enumerate(PRODUCTS_COLUMNS):
                row[col] = values[i] if i < len(values) else ""
            # Preserve other columns with empty values
            for col in ALL_COLUMNS:
                if col not in row:
                    row[col] = ""
            self.products_data.append(row)
        
        try:
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=ALL_COLUMNS)
                writer.writeheader()
                writer.writerows(self.products_data)
            
            messagebox.showinfo("Saved", f"Saved {len(self.products_data)} products to products.csv")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    def add_product_row(self):
        """Add a new empty product row."""
        # Find next M number
        max_m = 1000
        for row in self.products_data:
            m_num = row.get("m_number", "")
            if m_num.startswith("M") and m_num[1:].isdigit():
                max_m = max(max_m, int(m_num[1:]))
        
        new_m = f"M{max_m + 1}"
        
        # Default values
        defaults = {
            "m_number": new_m,
            "size": "saville",
            "color": "silver",
            "layout_mode": "A",
            "orientation": "landscape",
            "qa_status": "pending",
        }
        
        values = [defaults.get(col, "") for col in PRODUCTS_COLUMNS]
        self.products_tree.insert("", tk.END, values=values)
        self.products_data.append(defaults)
        self.product_count_var.set(f"{len(self.products_data)} products")
    
    def delete_product_row(self):
        """Delete selected product row."""
        selected = self.products_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a row to delete")
            return
        
        if messagebox.askyesno("Confirm", "Delete selected row(s)?"):
            for item in selected:
                self.products_tree.delete(item)
            self.product_count_var.set(f"{len(self.products_tree.get_children())} products")
    
    def edit_product_cell(self, event):
        """Edit a cell on double-click."""
        item = self.products_tree.selection()
        if not item:
            return
        item = item[0]
        
        # Get column
        col = self.products_tree.identify_column(event.x)
        col_idx = int(col[1:]) - 1  # "#1" -> 0
        
        if col_idx < 0 or col_idx >= len(PRODUCTS_COLUMNS):
            return
        
        col_name = PRODUCTS_COLUMNS[col_idx]
        current_value = self.products_tree.item(item, "values")[col_idx]
        
        # Create popup entry
        x, y, width, height = self.products_tree.bbox(item, col)
        
        entry = ttk.Entry(self.products_tree, width=width // 8)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, current_value)
        entry.select_range(0, tk.END)
        entry.focus()
        
        def save_edit(event=None):
            new_value = entry.get()
            values = list(self.products_tree.item(item, "values"))
            values[col_idx] = new_value
            self.products_tree.item(item, values=values)
            entry.destroy()
        
        def cancel_edit(event=None):
            entry.destroy()
        
        entry.bind("<Return>", save_edit)
        entry.bind("<Escape>", cancel_edit)
        entry.bind("<FocusOut>", save_edit)
    
    def refresh_flatfiles(self):
        """Refresh the list of available flatfiles."""
        flatfiles_dir = self.app_dir / "003 FLATFILES"
        if flatfiles_dir.exists():
            files = [
                f.name for f in sorted(flatfiles_dir.glob("*.xlsm"))
                if not f.name.startswith("~$") and "_jpeg" not in f.name
            ]
            self.flatfile_combo["values"] = files
            if files and not self.flatfile_var.get():
                self.flatfile_var.set(files[0])
        else:
            self.flatfile_combo["values"] = []
    
    def log(self, message):
        """Add message to log output."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_log(self):
        """Clear the log output."""
        self.log_text.delete(1.0, tk.END)
    
    def set_buttons_state(self, state):
        """Enable or disable all action buttons."""
        self.amazon_btn.config(state=state)
        self.ebay_btn.config(state=state)
        self.etsy_btn.config(state=state)
    
    def run_command(self, cmd, description):
        """Run a command in a background thread."""
        def worker():
            self.clear_log()
            self.set_buttons_state(tk.DISABLED)
            self.status_var.set(f"Running: {description}...")
            self.log(f"=== {description} ===\n")
            
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(self.app_dir),
                    shell=True
                )
                
                for line in process.stdout:
                    self.log(line.rstrip())
                
                process.wait()
                
                if process.returncode == 0:
                    self.log(f"\n=== {description} COMPLETE ===")
                    self.status_var.set(f"Completed: {description}")
                else:
                    self.log(f"\n=== {description} FAILED (exit code {process.returncode}) ===")
                    self.status_var.set(f"Failed: {description}")
                    
            except Exception as e:
                self.log(f"\nERROR: {e}")
                self.status_var.set(f"Error: {e}")
            
            finally:
                self.set_buttons_state(tk.NORMAL)
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    
    def run_amazon_pipeline(self):
        """Run the Amazon pipeline."""
        # Check products.csv exists
        if not (self.app_dir / "products.csv").exists():
            messagebox.showerror("Error", "products.csv not found!")
            return
        
        cmd = (
            "python generate_images_v2.py --csv products.csv && "
            "python generate_lifestyle_images.py --csv products.csv && "
            "python generate_amazon_content.py --csv products.csv --output amazon_flatfile.xlsx --upload-images"
        )
        self.run_command(cmd, "Amazon Pipeline")
    
    def run_ebay_pipeline(self):
        """Run the eBay pipeline."""
        flatfile = self.flatfile_var.get()
        if not flatfile:
            messagebox.showerror("Error", "Please select a flatfile first!")
            return
        
        flatfile_path = f"003 FLATFILES\\{flatfile}"
        
        # Build command with options
        cmd = f'python generate_ebay_from_flatfile.py "{flatfile_path}"'
        
        if self.ebay_dryrun_var.get():
            cmd += " --dry-run"
        elif self.ebay_promote_var.get():
            cmd += " --promote --ad-rate 5.0"
        
        self.run_command(cmd, f"eBay Pipeline ({flatfile})")
    
    def run_etsy_pipeline(self):
        """Run the Etsy pipeline."""
        flatfile = self.flatfile_var.get()
        if not flatfile:
            messagebox.showerror("Error", "Please select a flatfile first!")
            return
        
        flatfile_path = f"003 FLATFILES\\{flatfile}"
        
        # Derive output name
        product_name = flatfile.split()[0]
        output_path = f"003 FLATFILES\\{product_name}_shop_uploader.xlsx"
        
        cmd = f'python generate_etsy_shop_uploader.py --input "{flatfile_path}" --output "{output_path}"'
        self.run_command(cmd, f"Etsy Pipeline ({flatfile})")


def main():
    root = tk.Tk()
    
    # Set icon if available
    try:
        root.iconbitmap(default="")
    except:
        pass
    
    # Apply a modern theme
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "clam" in style.theme_names():
        style.theme_use("clam")
    
    app = PublisherGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
