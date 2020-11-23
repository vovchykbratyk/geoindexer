import os
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from shapely.geometry import Point
import static


class ExifQ(object):
    exif_data = None
    image = None

    def __init__(self, img_path):
        self.img_path = img_path
        self.image = Image.open(img_path)
        self.get_exif_data()
        super(ExifQ, self).__init__()

        self.dt = 'JPEG Image'

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

    def get_props(self):
        lat = None
        lon = None

        try:
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

            if lat and lon:
                point = Point(lat, lon)

                return static.get_geojson_record(geom=point,
                                                 datatype=self.dt,
                                                 fname=os.path.split(self.img_path)[1],
                                                 path=os.path.split(self.img_path)[0],
                                                 nativecrs=4326,
                                                 lastmod=static.moddate(self.img_path))

        except Exception as e:
            print(f"Problem getting GPS info from {self.img_path}: {e}")
            return None
