#
from PIL import Image
import math, shutil, requests, os
import pandas as pd 
import time
import numpy as np 
import cv2

class GoogleMapsLayers:
  ROADMAP = "v"
  TERRAIN = "p"
  ALTERED_ROADMAP = "r"
  SATELLITE = "s"
  TERRAIN_ONLY = "t"
  HYBRID = "y"


class GoogleMapDownloader:
    """
        A class which generates high resolution google maps images given
        a longitude, latitude and zoom level
    """

    def __init__(self, lat, lng, zoom=12, layer=GoogleMapsLayers.ROADMAP):
        """
            GoogleMapDownloader Constructor
            Args:
                lat:    The latitude of the location required
                lng:    The longitude of the location required
                zoom:   The zoom level of the location required, ranges from 0 - 23
                        defaults to 12
        """
        self._lat = lat
        self._lng = lng
        self._zoom = zoom
        self._layer = layer

    def getXY(self):
        """
            Generates an X,Y tile coordinate based on the latitude, longitude
            and zoom level
            Returns:    An X,Y tile coordinate
        """

        tile_size = 256

        # Use a left shift to get the power of 2
        # i.e. a zoom level of 2 will have 2^2 = 4 tiles
        numTiles = 1 << self._zoom

        # Find the x_point given the longitude
        point_x = (tile_size / 2 + self._lng * tile_size / 360.0) * numTiles // tile_size

        # Convert the latitude to radians and take the sine
        sin_y = math.sin(self._lat * (math.pi / 180.0))

        # Calulate the y coorindate
        point_y = ((tile_size / 2) + 0.5 * math.log((1 + sin_y) / (1 - sin_y)) * -(
        tile_size / (2 * math.pi))) * numTiles // tile_size

        return int(point_x), int(point_y)

    def generateImage(self, **kwargs):
        """
            Generates an image by stitching a number of google map tiles together.
            Args:
                start_x:        The top-left x-tile coordinate
                start_y:        The top-left y-tile coordinate
                tile_width:     The number of tiles wide the image should be -
                                defaults to 5
                tile_height:    The number of tiles high the image should be -
                                defaults to 5
            Returns:
                A high-resolution Goole Map image.
        """

        start_x = kwargs.get('start_x', None)
        start_y = kwargs.get('start_y', None)
        tile_width = kwargs.get('tile_width', 8)
        tile_height = kwargs.get('tile_height', 8)

        # Check that we have x and y tile coordinates
        if start_x == None or start_y == None:
            start_x, start_y = self.getXY()
        # Determine the size of the image
        width, height = 256 * tile_width, 256 * tile_height
        # Create a new image of the size require
        map_img = Image.new('RGB', (width, height))
        for x in range(-tile_width//2, tile_width//2):
            for y in range(-tile_height//2, tile_height//2):
                url = f'https://mt0.google.com/vt?lyrs={self._layer}&x=' + str(start_x + x) + \
                       '&y=' + str(start_y + y) + '&z=' + str(self._zoom)
                current_tile = str(x) + '-' + str(y)
                response = requests.get(url, stream=True)
                with open(current_tile, 'wb') as out_file: shutil.copyfileobj(response.raw, out_file)
                im = Image.open(current_tile)
                map_img.paste(im, ((x+tile_width//2) * 256, (y+tile_height//2) * 256))
                os.remove(current_tile)
        print('Image size (pix): ', map_img.size)
        return map_img


# ==================================================================================

def generate_original_images(rows, geo_form):
    """
    Extracted from the commented-out block in main.
    Generates and saves original images for the given rows.
    """
    for index, row in rows.iterrows():
        lat = row['lat']
        lon = row['lon']
        code = row['code']
        print(f"Downloading geoglyph {code} at coordinates ({lat}, {lon})")
        gmd = GoogleMapDownloader(lat, lon, 20, GoogleMapsLayers.SATELLITE)
        try:
            img = gmd.generateImage()
        except IOError:
            # if it fails, orig. comments said try adjusting zoom level and checking coordinates
            print(f"Could not generate the image for geoglyph {code}")
        else:
            # Save with geo_form in the filename so grayscale step can find it
            out_name = f"geoglyph_{geo_form}_#{code}.png"
            img.save(out_name)
            print(f"Image for geoglyph {code} has been created: {out_name}")
            # may need sleep function for rate limits 
            # time.sleep(.25)


def convert_images_to_grayscale(rows, geo_form):
    """
    Extracted from the OpenCV grayscale loop in main.
    Converts saved originals into grayscale images.
    """
    for index, row in rows.iterrows():
        code = row['code']
        img_path = f"geoglyph_{geo_form}_#{code}.png"  # matches the save name above
        img = cv2.imread(img_path)
        if img is None:
            print(f"Failed to load image for geoglyph {code} at {img_path}")
            continue
        # Convert to gray scale using OpenCV
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cv2.imwrite(f"geoglyph_{geo_form}_#{code}_gray.png", gray)


def main():
    geoglyph_data_path = "amazon_geoglyphs.xlsx"
    geo_form = input("Input the form of geoglyph (circle, square, parallelogram, zanja, geoglyph, octagon, etc.): ").strip()

    dat = pd.read_excel(geoglyph_data_path, engine="openpyxl")
    circle_rows = dat[dat['form'] == geo_form]

    # 1 Generate original images
    generate_original_images(circle_rows, geo_form)

    # 2 Ask whether to make grayscale versions
    make_gray = input("Do you want to generate grayscale images as well? (y/n): ").strip().lower()
    if make_gray in ("y", "yes"):
        convert_images_to_grayscale(circle_rows, geo_form)


if __name__ == '__main__':
    main()
