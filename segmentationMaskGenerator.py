import os
import math
import logging
from pathlib import Path
from typing import Optional, Dict

import numpy as np
from PIL import Image, ImageDraw
from fastkml import kml
from shapely.geometry import shape, LineString, Polygon
import xml.etree.ElementTree as ET
from shapely.geometry import Point

KML_PATH = "data/amazon_geoglyphs.kml"
DATA_ROOT = Path("data")
OUTPUT_MASKS_DIR = Path("data/masks")
ZOOM_LEVEL = 20
LINE_PADDING_PX = 3

logging.basicConfig(filename="missing_images.log", level=logging.INFO)
OUTPUT_MASKS_DIR.mkdir(parents=True, exist_ok=True)

TILE_SIZE = 256

def latlon_to_pixel_offset(lat, lon, lat_center, lon_center, zoom, image_size):
    """Convert lat/lon difference into pixel offset from image center."""
    def latlon_to_world(lat, lon):
        siny = math.sin(lat * math.pi / 180)
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

    width, height = image_size
    px = width / 2 + dx
    py = height / 2 + dy
    return px, py

def load_kml_geometries(kml_path: str):
    """Parse KML and return (name, Point) for all placemarks, tolerant of mixed formats."""
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    tree = ET.parse(kml_path)
    root = tree.getroot()
    geoms = []

    for placemark in root.findall(".//kml:Placemark", ns):
        name_elem = placemark.find("kml:name", ns)
        coords_elem = placemark.find(".//kml:coordinates", ns)
        if coords_elem is None or not coords_elem.text:
            continue

        name = name_elem.text.strip() if name_elem is not None else "unnamed"
        coords_text = coords_elem.text.strip()

        tokens = coords_text.replace(",", " ").split()
        if len(tokens) < 2:
            continue

        try:
            lon = float(tokens[0])
            lat = float(tokens[1])
        except ValueError:
            continue

        geoms.append((name, Point(lon, lat)))

    print(f"Extracted {len(geoms)} geometries from {kml_path}")
    return geoms


def build_image_index(data_root: Path) -> Dict[str, Path]:
    """Recursively scan for images, return {id_str: path} mapping."""
    index = {}
    for path in data_root.rglob("*"):
        if path.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]:
            parts = path.stem.split("#")
            if len(parts) > 1:
                gid = parts[-1]  # text after '#'
                index[gid] = path
    print(f"Indexed {len(index)} geoglyph images under {data_root}")
    return index


def find_image_by_id(image_index: Dict[str, Path], gid: str) -> Optional[Path]:
    """Return image path for given ID."""
    return image_index.get(gid)

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

    elif geom.geom_type == "Point":
        lon, lat = geom.x, geom.y
        px, py = latlon_to_pixel_offset(lat, lon, center_lat, center_lon, zoom, (width, height))
        r = pad_px * 3
        draw.ellipse((px - r, py - r, px + r, py + r), fill=255, outline=255)

    else:
        raise ValueError(f"Unsupported geometry type: {type(geom)}")

    return mask_img

def main():
    geoms = load_kml_geometries(KML_PATH)
    print(f"Loaded {len(geoms)} geoglyphs from {KML_PATH}")

    image_index = build_image_index(DATA_ROOT)

    for name, geom in geoms:
        gid = name.split("#")[-1] if "#" in name else name
        img_path = find_image_by_id(image_index, gid)

        if img_path is None:
            logging.info(f"No image found for {name} (id={gid})")
            continue

        print(f"Processing {name} → {img_path}")
        img = Image.open(img_path)
        width, height = img.size

        if geom.geom_type == "Point":
            lon_center, lat_center = geom.x, geom.y
        else:
            lon_center, lat_center = list(geom.centroid.coords)[0]

        mask_img = Image.new("L", (width, height), 0)
        mask_img = draw_geometry_on_mask(
            geom, lat_center, lon_center, mask_img, ZOOM_LEVEL, LINE_PADDING_PX
        )

        mask_out = OUTPUT_MASKS_DIR / f"{gid}_mask.png"
        mask_img.save(mask_out)
        print(f"Saved mask → {mask_out}")

if __name__ == "__main__":
    main()