#!/usr/bin/env python3
"""
Generate PWA icons with communicator badge design.
Requires: pillow
pip install pillow
"""

from pathlib import Path
import math

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Please install required packages:")
    print("pip install pillow")
    exit(1)


SIZES = [72, 96, 128, 144, 152, 180, 192, 384, 512, 1024]
OUTPUT_DIR = Path(__file__).parent.parent / "app" / "static" / "icons"


def generate_icons():
    """Generate PNG icons with communicator badge design at various sizes."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    for size in SIZES:
        # Create a new RGBA image
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Calculate dimensions
        padding = size // 10
        circle_size = size - (padding * 2)
        center = size // 2
        
        # Draw the circular gradient background (simulated with concentric circles)
        # Going from blue-500 (#3b82f6) through blue-600 (#2563eb) to purple-600 (#9333ea)
        for i in range(circle_size // 2, 0, -1):
            # Interpolate color
            ratio = i / (circle_size // 2)
            if ratio > 0.5:
                # Blue-500 to Blue-600
                r = int(59 + (37 - 59) * ((1 - ratio) * 2))
                g = int(130 + (99 - 130) * ((1 - ratio) * 2))
                b = int(246 + (235 - 246) * ((1 - ratio) * 2))
            else:
                # Blue-600 to Purple-600
                r = int(37 + (147 - 37) * ((0.5 - ratio) * 2))
                g = int(99 + (51 - 99) * ((0.5 - ratio) * 2))
                b = int(235 + (234 - 235) * ((0.5 - ratio) * 2))
            
            draw.ellipse(
                [center - i, center - i, center + i, center + i],
                fill=(r, g, b, 255)
            )
        
        # Draw the communicator icon (three stacked chevrons/layers)
        icon_size = int(size * 0.4)
        icon_x = center
        icon_y = center
        
        line_width = max(2, size // 30)
        gap = icon_size // 5
        
        # Draw three layers (top, middle, bottom)
        for layer in range(3):
            offset_y = (layer - 1) * gap
            half_width = icon_size // 2.5
            
            # Each layer is like a chevron pointing up then down
            points = [
                (icon_x - half_width, icon_y + offset_y),  # Left point
                (icon_x, icon_y - gap // 2 + offset_y),     # Top center
                (icon_x + half_width, icon_y + offset_y),   # Right point
            ]
            
            # Draw line segments
            draw.line([points[0], points[1]], fill=(255, 255, 255, 255), width=line_width)
            draw.line([points[1], points[2]], fill=(255, 255, 255, 255), width=line_width)
        
        # Add a subtle glow/shadow effect around the circle
        # (Already looks good without it due to the gradient)
        
        output_path = OUTPUT_DIR / f"icon-{size}x{size}.png"
        img.save(output_path, "PNG", optimize=True)
        print(f"Generated: {output_path}")
    
    print(f"\nGenerated {len(SIZES)} icons in {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_icons()
