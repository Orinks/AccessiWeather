#!/usr/bin/env python3
"""
Generate weather-themed app icons for AccessiWeather.

Creates icons in multiple sizes for Windows (.ico) and macOS (.icns).
Uses Pillow to draw a simple weather icon (sun with cloud).

Usage:
    python installer/create_icons.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow is required: pip install Pillow")
    sys.exit(1)

# Icon sizes needed
WINDOWS_SIZES = [16, 24, 32, 48, 64, 128, 256]
MACOS_SIZES = [16, 32, 64, 128, 256, 512, 1024]

# Colors
SKY_BLUE = (70, 130, 180)  # Steel blue background
SUN_YELLOW = (255, 200, 50)  # Warm yellow sun
SUN_ORANGE = (255, 165, 0)  # Orange sun rays
CLOUD_WHITE = (245, 245, 250)  # Slightly blue-white cloud
CLOUD_SHADOW = (200, 200, 210)  # Cloud shadow


def create_weather_icon(size: int) -> Image.Image:
    """
    Create a weather icon (sun with partial cloud) at the specified size.

    Args:
        size: Icon size in pixels (square)

    Returns:
        PIL Image object with the icon

    """
    # Create image with transparency
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Calculate proportions based on size
    center_x = size * 0.4
    center_y = size * 0.4
    sun_radius = size * 0.25

    # Draw circular background
    bg_margin = size * 0.02
    draw.ellipse(
        [bg_margin, bg_margin, size - bg_margin, size - bg_margin],
        fill=SKY_BLUE,
    )

    # Draw sun rays (before sun circle for layering)
    num_rays = 8
    ray_length = sun_radius * 0.6
    ray_width = max(2, size * 0.04)

    for i in range(num_rays):
        angle = (2 * math.pi * i) / num_rays - math.pi / 8
        inner_x = center_x + (sun_radius + size * 0.02) * math.cos(angle)
        inner_y = center_y + (sun_radius + size * 0.02) * math.sin(angle)
        outer_x = center_x + (sun_radius + ray_length) * math.cos(angle)
        outer_y = center_y + (sun_radius + ray_length) * math.sin(angle)

        draw.line(
            [(inner_x, inner_y), (outer_x, outer_y)],
            fill=SUN_ORANGE,
            width=int(ray_width),
        )

    # Draw sun circle
    sun_bbox = [
        center_x - sun_radius,
        center_y - sun_radius,
        center_x + sun_radius,
        center_y + sun_radius,
    ]
    draw.ellipse(sun_bbox, fill=SUN_YELLOW)

    # Draw cloud (partially covering sun)
    cloud_x = size * 0.55
    cloud_y = size * 0.6
    cloud_width = size * 0.45
    cloud_height = size * 0.25

    # Cloud shadow
    shadow_offset = size * 0.02
    _draw_cloud(
        draw,
        cloud_x + shadow_offset,
        cloud_y + shadow_offset,
        cloud_width,
        cloud_height,
        CLOUD_SHADOW,
    )

    # Main cloud
    _draw_cloud(draw, cloud_x, cloud_y, cloud_width, cloud_height, CLOUD_WHITE)

    return img


def _draw_cloud(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    width: float,
    height: float,
    color: tuple[int, int, int],
) -> None:
    """
    Draw a fluffy cloud shape.

    Args:
        draw: ImageDraw object
        x: Center X position
        y: Center Y position
        width: Cloud width
        height: Cloud height
        color: Fill color

    """
    # Cloud is made of overlapping circles
    circles = [
        (x - width * 0.25, y, height * 0.45),  # Left bump
        (x, y - height * 0.15, height * 0.55),  # Top middle bump
        (x + width * 0.2, y, height * 0.45),  # Right bump
        (x - width * 0.1, y + height * 0.1, height * 0.4),  # Bottom left
        (x + width * 0.1, y + height * 0.1, height * 0.4),  # Bottom right
    ]

    for cx, cy, radius in circles:
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=color,
        )


def save_ico(images: list[Image.Image], output_path: Path) -> None:
    """
    Save images as a Windows ICO file.

    Args:
        images: List of PIL Image objects at different sizes
        output_path: Path to save the ICO file

    """
    # Sort by size, largest first
    images = sorted(images, key=lambda img: img.size[0], reverse=True)
    images[0].save(
        output_path,
        format="ICO",
        sizes=[(img.size[0], img.size[1]) for img in images],
        append_images=images[1:],
    )
    print(f"Created: {output_path}")


def save_icns(images: list[Image.Image], output_path: Path) -> None:
    """
    Save images as a macOS ICNS file.

    Args:
        images: List of PIL Image objects at different sizes
        output_path: Path to save the ICNS file

    Note:
        ICNS generation only works reliably on macOS. On other platforms,
        this will attempt to save but may produce invalid files.

    """
    import platform
    if platform.system() != "Darwin":
        print(f"Warning: ICNS generation is only reliable on macOS. Skipping {output_path}")
        # Save as PNG instead for cross-platform compatibility
        png_path = output_path.with_suffix(".png")
        images[0].save(png_path, format="PNG")
        print(f"Created PNG fallback: {png_path}")
        return

    # Sort by size, largest first
    images = sorted(images, key=lambda img: img.size[0], reverse=True)
    images[0].save(
        output_path,
        format="ICNS",
        append_images=images[1:],
    )
    print(f"Created: {output_path}")


def save_png(image: Image.Image, output_path: Path) -> None:
    """
    Save an image as PNG.

    Args:
        image: PIL Image object
        output_path: Path to save the PNG file

    """
    image.save(output_path, format="PNG")
    print(f"Created: {output_path}")


def main() -> int:
    """Generate all icon files."""
    # Determine output directory
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    resources_dir = project_root / "src" / "accessiweather" / "resources"
    installer_dir = script_dir

    # Create resources directory if needed
    resources_dir.mkdir(parents=True, exist_ok=True)

    print("Generating AccessiWeather icons...")

    # Generate Windows icons
    print("\nGenerating Windows icons...")
    win_images = [create_weather_icon(size) for size in WINDOWS_SIZES]
    save_ico(win_images, resources_dir / "app.ico")
    save_ico(win_images, installer_dir / "app.ico")  # Also in installer dir

    # Generate macOS icons
    print("\nGenerating macOS icons...")
    mac_images = [create_weather_icon(size) for size in MACOS_SIZES]
    save_icns(mac_images, resources_dir / "app.icns")

    # Generate a master PNG at high resolution
    print("\nGenerating master PNG...")
    master_image = create_weather_icon(1024)
    save_png(master_image, resources_dir / "app_icon_master.png")

    # Generate additional sizes for various uses
    print("\nGenerating additional PNG sizes...")
    for size in [16, 32, 64, 128, 256]:
        icon = create_weather_icon(size)
        save_png(icon, resources_dir / f"app_{size}.png")

    print("\n✓ All icons generated successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
