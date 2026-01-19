"""Resize images that exceed Amazon's 10,000 pixel limit."""
from PIL import Image
import os
from pathlib import Path

base = Path(__file__).parent / 'exports'
max_dim = 10000

folders = [d for d in os.listdir(str(base)) if d.startswith('M')]
resized_count = 0

for f in folders:
    img_dir = os.path.join(base, f, '002 Images')
    if not os.path.exists(img_dir):
        continue
    
    for i in os.listdir(img_dir):
        if not i.endswith('.png'):
            continue
        
        p = os.path.join(img_dir, i)
        with Image.open(p) as img:
            w, h = img.size
            if max(w, h) > max_dim:
                if w > h:
                    new_w = max_dim
                    new_h = int(h * max_dim / w)
                else:
                    new_h = max_dim
                    new_w = int(w * max_dim / h)
                print(f'Resizing {i}: {w}x{h} -> {new_w}x{new_h}')
                resized = img.resize((new_w, new_h), Image.LANCZOS)
                resized.save(p)
                resized_count += 1

print(f'Done! Resized {resized_count} images.')
