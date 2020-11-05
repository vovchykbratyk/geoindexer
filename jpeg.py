from collections import OrderedDict
import os
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from shapely.geometry import mapping, Point


class ImageMetaData(object):
    exif_data = None
    image = None
    
    def __init__(self, img_path):
        self.img_path, self.img_name = os.path.split(img_path)
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

    @staticmethod
    def get_if_exists(data, key):
        if key in data:
            return data[key]
        return None

    @staticmethod
    def convert_to_degrees(value):
        return value[0] + (value[1] / 60.0) + (value[2] / 3600.0)
        
    def get_props(self, oid):
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

        point = Point(lon, lat)

        return {'type': 'Feature',
                'geometry': mapping(point),
                'properties': OrderedDict([
                    ('id', oid),
                    ('dataType', 'JPEG'),
                    ('fname', self.img_name),
                    ('path', self.img_path),
                    ('native_crs', 4326)
                ])}


class GroundImages:

    def __init__(self, coords, radius, outpath):
        self.coords = coords
        self.radius = radius
        self.outpath = outpath
        
        # Do PKI authentication to ground photography service(s) here
        
        
# TESTING

jpgdir = "/home/eric/OneDrive/Pictures/Camera Roll/2020/05"
types = ['jpg', 'jpeg', 'png']

imagelist = [str(p.resolve()) for p in Path(jpgdir).glob('**/*') if p.suffix[1:] in types]
fid = 0

for i in imagelist:
    try:
        md = ImageMetaData(i)
        lat_lon = md.get_props(fid)
        print(lat_lon)
        print('--------------------')
        fid += 1
    except Exception as e:
        print(f'Exception: {e}')
        pass