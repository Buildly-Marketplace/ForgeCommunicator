#!/usr/bin/env python3
"""
Generate PWA icons.
Requires: pillow
pip install pillow
"""

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Please install required packages:")
    print("pip install pillow")
    exit(1)


SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
OUTPUT_DIR = Path(__file__).parent.parent / "app" / "static" / "icons"


def generate_icons():
    """Generate PNG icons at various sizes."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    for size in SIZES:
        # Create a new image with a blue background
        img = Image.new('RGBA', (size, size), (79, 70, 229, 255))  # Indigo color
        draw = ImageDraw.Draw(img)
        
        # Draw rounded rectangle background
        corner_radius = size // 5
        draw.rounded_rectangle(
            [(0, 0), (size-1, size-1)],
            radius=corner_radius,
            fill=(79, 70, 229, 255)
        )
        
        # Draw "FC" text
        text = "FC"
        font_size = size // 2
        
        try:
            # Try system fonts
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()
        
        # Get text bounding box for centering
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (size - text_width) // 2
        y = (size - text_height) // 2 - bbox[1]  # Adjust for baseline
        
        draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
        
        output_path = OUTPUT_DIR / f"icon-{size}x{size}.png"
        img.save(output_path, "PNG", optimize=True)
        print(f"Generated: {output_path}")
    
    print(f"\nGenerated {len(SIZES)} icons in {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_icons()
