from datetime import datetime
import fiona
from handlers import Container, Exif, Lidar, Log, Raster, Shapefile
import json
import os
from pathlib import Path
import sys
from tqdm import tqdm


def now():
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


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
                                polygons.append(json.loads(feat))
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
                            polygons.append(json.loads(lf))
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
                            polygons.append(json.loads(feat))
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
                            polygons.append(json.loads(feat))
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
                    extents['features'].append(points)

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
