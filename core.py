import container
import gdal
import geopandas as gpd
import jpeg
import json
import lidar
import os
from pathlib import Path
from pyproj import CRS
import raster
import shapefile

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
                return [str(p.resolve()) for p in Path(self.path).glob("**/*") if p.suffix[1:] in self.types]
            except PermissionError:
                pass
        else:
            try:
                return [str(p.resolve()) for p in Path(self.path).glob("*") if p.suffix[1:] in self.types]
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

        report = {'container_layers': 0,
                  'web_images': 0,
                  'lidar_pointclouds': 0,
                  'rasters': 0,
                  'shapefiles': 0}

        points = []
        polygons = []
        
        extents = {'type': 'FeatureCollection',
                   'features': []}
        
        try:
            for cf in self.categorized['containers']:
                container_feats = ContainerQ(cf).get_props()
                for feat in container_feats:
                    if feat:
                        polygons.append(json.loads(feat))
                        report['container_layers'] += 1
        except KeyError as ke:
            print(f'No files in list: {ke}')
            pass
        
        try:    
            for jf in self.categorized['jpg_files']:
                points.append(ExifQ(jf).get_props())
                report['web_images'] += 1
                
        except KeyError as ke:
            print(f'No files in list: {ke}')
            pass
        
        try:
            for lf in self.categorized['lidar_files']:
                feat = LidarQ(lf).get_props()
                if feat:
                    polygons.append(json.loads(feat))
                    report['lidar_pointclouds'] += 1
                    
        except KeyError as ke:
            print(f'No files in list: {ke}')
            pass
        
        try:    
            for rf in self.categorized['rasters']:
                feat = RasterQ(rf).get_props()
                if feat:
                    polygons.append(json.loads(feat))
                    report['rasters'] += 1
                    
        except KeyError as ke:
            print(f'No files in list: {ke}')
            pass
        
        try:        
            for sf in self.categorized['shapefiles']:
                feat = shpfile.ShapeQ(sf).get_props()
                if feat:
                    polygons.append(json.loads(feat))
                    report['shapefiles'] += 1
                    
        except KeyError as ke:
            print(f'No files in list: {ke}')
            pass
        
        if len(polygons) > 0:
            extents['features'] = polygons
        if len(points) > 0:
            extents['features'] = points
            
        return json.dumps(extents)


# testing
searchpath = "C:/Data"
ftypes = ['gpkg', 'json', 'geojson',
          'jpg', 'jpeg', 'las', 'laz', 'tif', 'tiff', 'ntf',
          'nitf', 'dt0', 'dt1', 'dt2', 'shp']
search = GeoCrawler(searchpath, ftypes).get_file_list()

srtd = GeoIndexer(search)

print(srtd.get_extents())
