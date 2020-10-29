import fiona
import gdal
from lidar import LidarQ
import os
from pathlib import Path
from pyproj import CRS
import shapely


class GeoCrawler:

    def __init__(self, path, types):
        """
                Default GeoCrawler instance.

                :param path: The path to be crawled
                :type path: str
                :param types: List of file extensions
                :type types: list
                """
        self.path = path
        self.types = types

    def get_file_list(self, recursive=True):
        """
        Searches path (default recursive) for filetypes and returns list of matches.

        :param recursive: Traverse directories recursively (default: True)
        :type recursive: bool
        :return: list
        """
        if recursive:
            try:
                return [str(p.resolve()) for p in Path(self.path).glob("**/*") if p.suffix in self.types]
            except PermissionError:
                pass
        else:
            try:
                return [str(p.resolve()) for p in Path(self.path).glob("*") if p.suffix in self.types]
            except PermissionError:
                pass


class GeoIndexer:

    def __init__(self, file_list):
        """
        Constructor. Ingests uncategorized list of file objects and sorts them into broad categories for
        discrete processing.
        """

        self.file_list = file_list
        self.categorized = {
            'containers': [],
            'jpg_files': [],
            'lidar_files': [],
            'rasters': [],
            'shapefiles': []
        }
        self.default_sr = CRS.from_user_input(4326)

        try:
            for f in self.file_list:
                f = f.strip()
                ext = os.path.splitext(os.path.split(f)[1])[1][1:]
                if ext in ['gdb', 'gpkg', 'kml', 'kmz', 'json', 'geojson']:
                    self.categorized['containers'].append(f)
                elif ext in ['jpg', 'jpeg']:
                    self.categorized['jpg_files'].append(f)
                elif ext in ['las', 'laz']:
                    self.categorized['lidar_files'].append(f)
                elif ext in ['tif', 'ntf', 'nitf', 'dt0', 'dt1', 'dt2', 'tiff']:
                    self.categorized['rasters'].append(f)
                elif ext == "shp":
                    self.categorized['shapefiles'].append(f)

            self.categorized = {key: value for (key, value) in self.categorized.items() if value is not None}

        except Exception as e:
            print(e)
            raise e

    @staticmethod
    def _get_schema(geom_type):
        return {'geometry': geom_type,
                'properties': OrderedDict([
                    ('id', 'int'),
                    ('dataType', 'str'),
                    ('fname', 'str'),
                    ('path', 'str'),
                    ('parent', 'str'),
                    ('native_crs', 'int')
                ])}

    def get_extents(self):
        points = []
        polygons = []
        
        extents = {}
        
        poly_increment = 0
        point_increment = 0
        
        if self.categorized['containers']:
            pass
        if self.categorized['jpg_files']:
            pass
        if self.categorized['lidar_files']:
            for lf in self.categorized['lidar_files']:
                polygons.append(LidarQ(lf).get_props(poly_increment))
                poly_increment += 1
        if self.categorized['rasters']:
            for rf in self.categorized['rasters']:
                polygons.append(RasterQ(rf).get_props(poly_increment))
        if self.categorized['shapefiles']:
            pass
        
        if len(polygons) > 0:
            extents['polygons'] = polygons
        if len(points) > 0:
            extents['points'] = points
            
        return extents


# testing
searchpath = "C:/Data"
ftypes = ['.gdb', '.gpkg', '.kml', '.kmz', '.json', '.geojson',
          '.jpg', '.jpeg', '.las', '.laz', '.tif', '.tiff', '.ntf',
          '.nitf', '.dt0', '.dt1', '.dt2', '.shp']
search = GeoCrawler(searchpath, ftypes).get_file_list()

srtd = GeoIndexer(search)
print(srtd.categorized)
