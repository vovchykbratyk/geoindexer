import os
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import re


class ImageMetaData(object):
    exif_data = None
    image = None
    
    def __init__(self, img_path):
        self.image = Image.open(img_path)
        self.get_exif_data()
        super(ImageMetaData, self).__init__()
        
    def get_exif_data(self):
        exif_data = {}
        info = self.image._getexif()
        if info:
            for tag, value in info.items():
                decoded = TAGS.get(tag, tag)
                if decoded == 'GPSInfo':
                    gps_data = {}
                    for t in value:
                        sub_decoded = GPSTAGS.get(t, t)
                        gps_data[sub_decoded] = value[t]
                    exif_data[decoded] = gps_data
                else:
                    exif_data[decoded] = value
        self.exif_data = exif_data
        return exif_data
        
    def get_if_exists(self, data, key):
        if key in data:
            return data[key]
        return None
        
    def convert_to_degrees(self, value):
        return value[0] + (value[1] / 60.0) + (value[2] / 3600.0)
        
    def get_lat_lon(self):
        lat = None
        lon = None
        
        exif_data = self.get_exif_data()
        if 'GPSInfo' in exif_data:
            gps_info = exif_data['GPSInfo']
            gps_lat = self.get_if_exists(gps_info, 'GPSLatitude')
            gps_lat_ref = self.get_if_exists(gps_info, 'GPSLatitudeRef')
            gps_lon = self.get_if_exists(gps_info, 'GPSLongitude')
            gps_lon_ref = self.get_if_exists(gps_info, 'GPSLongitudeRef')
            
            if gps_lat and gps_lat_ref and gps_lon and gps_lon_ref:
                lat = self.convert_to_degrees(gps_lat)
                if gps_lat_ref == 'S':
                    lat = 0 - lat
                lon = self.convert_to_degrees(gps_lon)
                if gps_lon_ref == 'W':
                    lon = 0 - lon
        return lat, lon
        
        
class GroundImages:

    def __init__(self, coords, radius, outpath):
        self.coords = coords
        self.radius = radius
        self.outpath = outpath
        
        # Do PKI authentication to ground photography service here
        
        
# TESTING

jpgdir = ""
types = ['jpg', 'jpeg', 'png']

imagelist = [str(p.resolve()) for p in Path(jpgdir).glob('**/*') if p.suffix[1:] in types]

for i in imglist:
    try:
        md = ImageMetaData(i)
        lat_lon = metadata.get_lat_lon()
        if lat_lon[0] and lat_lon[1]:
            print(lat_lon)
            print('--------------------------------')
    except Exception as e:
        print(f'Exception: {e}')
        pass
