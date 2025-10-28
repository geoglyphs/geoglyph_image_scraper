import os
import math
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw
from fastkml import kml
from shapely.geometry import shape, LineString, Polygon

KML_PATH = "data/amazon_geoglyphs.kml"
IMAGES_DIR = Path("data/images")
OUTPUT_MASKS_DIR = Path("data/masks")
ZOOM_LEVEL = 20
IMAGE_SIZE_PIXELS = (2048, 2048)
LINE_PADDING_PX = 3

logging.basicConfig(filename="missing_images.log", level=logging.INFO)
OUTPUT_MASKS_DIR.mkdir(parents=True, exist_ok=True)

TILE_SIZE = 256

def latlon_to_pixel_offset(lat, lon, lat_center, lon_center, zoom, image_size):
    """
    Converts lat/lon difference into pixel offset from center of image
    using Web Mercator projection.
    """
    # Compute world coordinates for lat/lon at this zoom
    def latlon_to_world(lat, lon):
        siny = math.sin(lat * math.pi / 180)
        # clamp siny for numerical stability
        siny = min(max(siny, -0.9999), 0.9999)
        x = TILE_SIZE * (0.5 + lon / 360)
        y = TILE_SIZE * (
            0.5 - math.log((1 + siny) / (1 - siny)) / (4 * math.pi)
        )
        return x, y

    scale = 2 ** zoom

    x, y = latlon_to_world(lat, lon)
    cx, cy = latlon_to_world(lat_center, lon_center)

    dx = (x - cx) * scale * 256
    dy = (y - cy) * scale * 256

    # Convert offset to pixel coordinates within the image
    width, height = image_size
    px = width / 2 + dx
    py = height / 2 + dy
    return px, py

def load_kml_geometries(kml_path: str):
    """Parse KML and return a list of (name, geometry) tuples."""
    with open(kml_path, "rb") as f:
        doc = f.read()
    k = kml.KML()
    k.from_string(doc)
    geoms = []
    for feature in k.features():
        for placemark in feature.features():
            name = placemark.name.strip() if placemark.name else "unnamed"
            geom = shape(placemark.geometry)
            geoms.append((name, geom))
    return geoms


def find_image_for_name(name: str, image_dir: Path) -> Optional[Path]:
    """Find an image corresponding to a geoglyph name."""
    for file in image_dir.iterdir():
        if file.stem.lower().startswith(name.lower()):
            return file
    return None


def draw_geometry_on_mask(geom, center_lat, center_lon, mask_img, zoom, pad_px):
    """Rasterize KML geometry into mask image."""
    draw = ImageDraw.Draw(mask_img)
    width, height = mask_img.size

    if isinstance(geom, LineString):
        pts = [
            latlon_to_pixel_offset(lat, lon, center_lat, center_lon, zoom, (width, height))
            for lon, lat in geom.coords
        ]
        draw.line(pts, fill=255, width=pad_px * 2)

    elif isinstance(geom, Polygon):
        pts = [
            latlon_to_pixel_offset(lat, lon, center_lat, center_lon, zoom, (width, height))
            for lon, lat in geom.exterior.coords
        ]
        draw.polygon(pts, outline=255, fill=255)

    else:
        raise ValueError(f"Unsupported geometry type: {type(geom)}")

    return mask_img

def main():
    geoms = load_kml_geometries(KML_PATH)
    print(f"Loaded {len(geoms)} geoglyphs")

    for name, geom in geoms:
        img_path = find_image_for_name(name, IMAGES_DIR)
        if not img_path:
            logging.info(f"Missing image for {name}")
            continue

        print(f"Processing {name} → {img_path}")
        img = Image.open(img_path)
        width, height = img.size

        lat_center = 0.0
        lon_center = 0.0

        mask_img = Image.new("L", (width, height), 0)
        mask_img = draw_geometry_on_mask(
            geom, lat_center, lon_center, mask_img, ZOOM_LEVEL, LINE_PADDING_PX
        )

        mask_out = OUTPUT_MASKS_DIR / f"{name}_mask.png"
        mask_img.save(mask_out)
        print(f"Saved mask → {mask_out}")


if __name__ == "__main__":
    main()
