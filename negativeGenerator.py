import pandas as pd
import random
import math
import os
import cv2
import numpy as np
from v2gmapDownloader import GoogleMapDownloader, GoogleMapsLayers

EXCEL_PATH = "amazon_geoglyphs.xlsx"
OUTPUT_CSV = "negative_samples.csv"
ZOOM_LEVEL = 20  # same zoom level used to generate positives
OFFSET_RANGE = 0.003  # degrees of lat/lon to shift
OFFSET_RANGE = float(OFFSET_RANGE)
NUM_OFFSETS_PER_SITE = 1  # how many negatives per geoglyph
DISTANCE_THRESHOLD = 0.001  # minimum distance (deg) to avoid overlap
DISTANCE_THRESHOLD = float(DISTANCE_THRESHOLD)
IMAGE_OUTPUT_FOLDER = "negatives/"
EDGE_DENSITY_THRESHOLD = 0.01  # threshold for texture filtering, feel free to adjust

# using haversine dist. formula to check distances between the offsets and geoglyphs, should prevent any overlap
def haversine_distance(lat1, lon1, lat2, lon2):
    earthR = 6371    # earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * earthR * math.asin(math.sqrt(a))


# edge detection to filter out low-texture images, hopefully helps avoid getting too many forest tiles
# ^^ i feel like if we get too forest tiles as negatives it might confuse the model, this still allows for some
# ^^ not sure if it is helping much, maybe adjusting the threshold would help
def has_low_texture(img):
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    edge_density = np.sum(edges > 0) / edges.size
    return edge_density < EDGE_DENSITY_THRESHOLD


def generate_negative_coordinates(df):
    negatives = []
    existing_points = list(zip(df["lat"], df["lon"]))

    for indx, row in df.iterrows():

        lat, lon, code = row["lat"], row["lon"], row["code"]

        for i in range(NUM_OFFSETS_PER_SITE):
            while True:
                lat_offset = lat + random.uniform(-OFFSET_RANGE, OFFSET_RANGE)
                lon_offset = lon + random.uniform(-OFFSET_RANGE, OFFSET_RANGE)

                # ensure offset isn't too close to any known site
                too_close = any(
                    haversine_distance(lat_offset, lon_offset,e_lat,e_lon) < DISTANCE_THRESHOLD * 111
                    for e_lat, e_lon in existing_points
                )

                if not too_close:

                    negatives.append({"orig_code": code, "lat": lat_offset, "lon": lon_offset})
                    break

    neg_df = pd.DataFrame(negatives)
    neg_df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(neg_df)} negative samples to {OUTPUT_CSV}")
    return neg_df

def download_negative_images(df, max_images=1500):
    os.makedirs(IMAGE_OUTPUT_FOLDER, exist_ok=True)
    count = 0

    for _, row in df.iterrows():
        if count >= max_images:
            print(f"Reached {max_images} images. Stopping.")
            break

        lat, lon = row["lat"], row["lon"]
        orig_code = row["orig_code"]

        print(f"Downloading negative, near geoglyph {orig_code} at ({lat}, {lon})")
        gmd = GoogleMapDownloader(lat, lon, ZOOM_LEVEL, GoogleMapsLayers.SATELLITE)

        try:
            img = gmd.generateImage()
        except Exception as e:
            print(f"Failed to download ({lat}, {lon}): {e}")
            continue

        try:
            if has_low_texture(img):
                print(f"Skipped ({lat:.3f}, {lon:.3f}) — low texture")
                continue

            out_name = (
                f"{IMAGE_OUTPUT_FOLDER}negative_{orig_code}_{lat:.3f}_{lon:.3f}.png"
            )
            img.save(out_name)
            print(f"Saved {out_name}")
        finally:
            del img  # remove reference to large image object
            gc.collect()

        count += 1
        
# MAIN

def main():
    df = pd.read_excel(EXCEL_PATH, engine="openpyxl")
    # convert lat/lon to numeric
    df["lat"] = pd.to_numeric(df["lat"], errors='coerce')
    df["lon"] = pd.to_numeric(df["lon"], errors='coerce')
    neg_df = generate_negative_coordinates(df)
    download_negative_images(neg_df)


if __name__ == "__main__":
    main()
