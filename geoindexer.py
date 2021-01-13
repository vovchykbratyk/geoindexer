"""Documentation to follow"""

from area import area
from collections import OrderedDict
from datetime import datetime
import fiona
from fiona.crs import from_epsg
from handlers import Container, Exif, Lidar, Log, Raster, Shapefile
import json
import os
from pathlib import Path
import sys
from tqdm import tqdm


def now(iso8601=True):
    if iso8601:
        return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    return datetime.now().strftime('%Y%m%dT%H%M%S')


class GeoCrawler:

    def __init__(self, path, types):
        """
        GeoCrawler constructor

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
        GeoIndexer constructor
        """
        self.file_list = file_list
        self.errors = []
        self.failures = {'files': [],
                         'layers': []}

    def get_extents(self, logging=None):

        # Get total number of datasets to process, including geodatabase layers
        if len(self.file_list) > 0:

            to_process = 0
            for f in self.file_list:
                to_process += GeoIndexer.get_layer_num(self, f)

            # Set up the output
            points = []
            polygons = []
            extents = {'type': 'FeatureCollection',
                       'features': []}

            # Set up the report
            stats = {'container_layers': 0,
                     'web_images': 0,
                     'lidar_point_clouds': 0,
                     'rasters': 0,
                     'shapefiles': 0}

            # Main iterator
            for f in tqdm(self.file_list, desc='GeoIndexer progress', total=len(self.file_list), dynamic_ncols=True):
                fext = GeoIndexer.get_extension(f)

                if fext in ['gdb', 'gpkg', 'db', 'sqlite']:
                    try:
                        cf = Container(f).get_props()
                        for feat in cf['feats']:
                            if feat:
                                polygons.append(feat)
                                stats['container_layers'] += 1
                            else:
                                self.errors.append(f'{now()} - Problem processing layer {feat} in {f}')
                                self.failures['layers'].append(f'{feat} ({f})')
                        if len(cf['errors']) > 0:
                            self.errors.append([e for e in cf['errors']])
                            self.failures['layers'].append([f for f in cf['failed_layers']])
                    except Exception as e:
                        self.errors.append(f'{now()} - {e} - [{f}]')
                        self.failures['files'].append(f)
                        pass

                elif fext in ['jpg', 'jpeg']:
                    try:
                        points.append(Exif(f).get_props())
                        stats['web_images'] += 1
                    except Exception as e:
                        self.errors.append(f'{now()} - {e} - [{f}]')
                        self.failures['files'].append(f)
                        pass

                elif fext in ['laz', 'las']:
                    try:
                        lf = Lidar(f).get_props()
                        if lf:
                            polygons.append(lf)
                            stats['lidar_point_clouds'] += 1
                        else:
                            self.errors.append(f'{now()} - Problem processing Lidar file {f}')
                            self.failures['files'].append(f)
                    except Exception as e:
                        self.errors.append(f'{now()} - {e} - [{f}]')
                        pass

                elif fext in ['tiff', 'tif', 'ntf', 'nitf', 'dt0', 'dt1', 'dt2']:
                    try:
                        feat = Raster(f).get_props()
                        if feat:
                            polygons.append(feat)
                            stats['rasters'] += 1
                        else:
                            self.errors.append(f'{now()} - Problem accessing Raster {f}')
                            self.failures['files'].append(f)
                    except Exception as e:
                        self.errors.append(f'{now()} - {e} - [{f}]')
                        self.failures['files'].append(f)
                        pass

                elif fext == 'shp':
                    try:
                        feat = Shapefile(f).get_props()
                        if feat:
                            polygons.append(feat)
                            stats['shapefiles'] += 1
                        else:
                            self.errors.append(f'{now()} - Problem accessing Shapefile {f}')
                            self.failures['files'].append(f)
                    except Exception as e:
                        self.errors.append(f'{now()} - {e} - [{f}]')
                        self.failures['files'].append(f)
                        pass

            # Assemble the GeoJSON object
            if len(polygons) > 0:
                for poly in polygons:
                    extents['features'].append(poly)
            if len(points) > 0:
                for point in points:
                    extents['features'].append(point)

            # Summary statistics
            stats['total_processed'] = sum([val for key, val in stats.items()])
            stats['total_datasets'] = to_process
            stats['success_rate'] = round(
                ((float(stats.get('total_processed', 0)) / float(stats.get('total_datasets', 0))) * 100), 2)

            # Output log if true
            if logging:
                log = Log(self.errors)
                logname = log.to_file(logging)
                stats['logfile'] = f'file:///{str(os.path.join(logging, logname))}'.replace("\\", "/")

            return extents, stats, self.failures

        else:
            sys.exit('No files found to process.')

    def get_layer_num(self, filepath: str):
        """
        Get the number of layers within a container, if the file is a container and can be read by fiona.
        Otherwise, return 0 (if the container cannot be read) or 1 (if the file is not a container).

        :return: int
        """
        extension = GeoIndexer.get_extension(filepath)
        if extension in ['gdb', 'gpkg', 'db', 'sqlite']:
            try:
                numlayers = len(fiona.listlayers(filepath))
                return numlayers
            except Exception as e:
                self.errors.append(f'{now()} - {e} - [{filepath}]')
                return 0
        else:
            return 1

    @staticmethod
    def get_extension(filepath: str):
        if filepath:
            return os.path.splitext(os.path.split(filepath)[1])[1][1:].lower()
        return None

    @staticmethod
    def geojson_container():
        return {'type': 'FeatureCollection',
                'features': []}

    @staticmethod
    def get_schema(img_popup=False):
        if img_popup:
            return {'geometry': 'Point',
                    'properties': OrderedDict([
                        ('dataType', 'str'),
                        ('fname', 'str'),
                        ('path', 'str'),
                        ('img_popup', 'str'),
                        ('native_crs', 'int'),
                        ('lastmod', 'str')])}
        return {'geometry': 'Polygon',
                'properties': OrderedDict([
                    ('path', 'str'),
                    ('lastmod', 'str'),
                    ('fname', 'str'),
                    ('dataType', 'str'),
                    ('native_crs', 'int')])}

    @staticmethod
    def to_geopackage(features: dict, path: str, scoped=True):
        """
        Outputs to a geopackage container, with different layers of polygons based on size:
        -- lv0: >= 175,000,000
        -- lv1: >= 35,000,000 < 175,000,000
        -- lv2: >= 5,000,000 < 35,000,000
        -- lv3: >= 1,000,000, < 5,000,000
        -- lv4: >= 500,000, < 1,000,000
        -- lv5: >= 100,000, < 500,000
        -- lv6: >= 50,000, < 100,000
        -- lv7: > 0, < 50,000
        """
        driver = "GPKG"

        if scoped:

            layers = {'level_00': GeoIndexer.geojson_container(),
                      'level_01': GeoIndexer.geojson_container(),
                      'level_02': GeoIndexer.geojson_container(),
                      'level_03': GeoIndexer.geojson_container(),
                      'level_04': GeoIndexer.geojson_container(),
                      'level_05': GeoIndexer.geojson_container(),
                      'level_06': GeoIndexer.geojson_container()}

            for f in features['features']:
                try:
                    feat_area = float(area(f['geometry']) / 1000000)
                    if feat_area >= 175000000:  # lv0, world
                        layers['level_00']['features'].append(f)
                    elif 35000000 <= feat_area < 175000000:
                        layers['level_01']['features'].append(f)
                    elif 5000000 <= feat_area < 35000000:
                        layers['level_02']['features'].append(f)
                    elif 1000000 <= feat_area < 5000000:
                        layers['level_03']['features'].append(f)
                    elif 500000 <= feat_area < 1000000:
                        layers['level_04']['features'].append(f)
                    elif 100000 <= float(feat_area) < 500000:
                        layers['level_05']['features'].append(f)
                    elif 0 < float(feat_area) < 100000:
                        layers['level_06']['features'].append(f)
                except (TypeError, KeyError, AttributeError):
                    pass

            for k, v in layers.items():
                if len(v['features']) >= 1:
                    with fiona.open(path, 'w',
                                    schema=GeoIndexer.get_schema(),
                                    driver=driver,
                                    crs=from_epsg(4326),
                                    layer=k) as outlyr:
                        outlyr.writerecords(v['features'])
                        # print(f'wrote layer {k}:')
                        # print(f'{json.dumps(v)}')

                    # Uncomment below to use geopandas instead of fiona
                    # import geopandas as gpd
                    # gdf = gpd.GeoDataFrame.from_features(v)
                    # gdf.crs = 'EPSG:4326'
                    # gdf.to_file(path, driver=driver, layer=k)

            return True

        else:
            layername = f"coverages_{now(iso8601=False)}"
            with fiona.open(path, 'w',
                            schema=GeoIndexer.get_schema(),
                            driver=driver,
                            crs=from_epsg(4326),
                            layer=layername) as outlyr:
                outlyr.writerecords(features['features'])

            # Uncomment below to use geopandas instead of fiona
            # import geopandas as gpd
            # gdf = gpd.GeoDataFrame.from_features(features)
            # gdf.crs = 'EPSG:4326'
            # gdf.to_file(path, driver=driver, layer=layername)
