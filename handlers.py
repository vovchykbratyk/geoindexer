from collections import OrderedDict
from datetime import datetime
import gdal
import geopandas as gpd
import fiona
import json
import os
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import pyproj
from pyproj import CRS
import rasterio
import re
from shapely.geometry import mapping, Point, Polygon
import subprocess as sp
from zipfile import ZipFile


class Log:

    def __init__(self, lines: list):
        self.lines = lines

    def to_file(self, path):
        logname = 'geoindexer_' + datetime.now().strftime('%Y%m%dT%H%M%S') + '.log'
        log = os.path.join(path, logname)
        with open(log, 'w') as outlog:
            for line in self.lines:
                outlog.write(f'{line}\n')
        return logname


class Container:

    def __init__(self, container):
        """
        Container constructor
        """
        self.container = container
        self.layer_errors = []
        self.failed_layers = []

    def get_props(self):
        """
        Cracks a Container instance and returns a list of layer extents in geojson

        :return: list
        """
        dt = None
        ext = os.path.splitext(os.path.split(self.container)[1])[1][1:]
        ext = ext.lower()

        feats = []

        if ext in ['gdb', 'gpkg', 'db']:  # it's a database
            if ext == 'gdb':
                dt = 'Esri FGDB Feature Class'
            elif ext == 'gpkg':
                dt = 'GeoPackage Layer'
            elif ext == 'db':
                dt = 'SQLite Database Layer'

            # process the db container
            for ln in fiona.listlayers(self.container):
                try:
                    with fiona.open(self.container, layer=ln) as lyr:
                        try:
                            lyr_crs = lyr.crs['init'].split(':')[1]
                            if lyr_crs != str(4326):
                                minx, miny, maxx, maxy = to_wgs84(lyr_crs, lyr.bounds)

                            else:
                                bounds = lyr.bounds
                                minx, miny, maxx, maxy = bounds[0], bounds[1], bounds[2], bounds[3]

                            boundary = Polygon([
                                [minx, miny],
                                [maxx, miny],
                                [maxx, maxy],
                                [minx, maxy]
                            ])

                            feats.append(get_geojson_record(
                                geom=boundary,
                                datatype=dt,
                                fname=ln,
                                path=self.container,
                                nativecrs=lyr_crs,
                                lastmod=moddate(self.container)
                            ))

                        except (AttributeError, KeyError, fiona.errors.DriverError) as e:
                            self.layer_errors.append(f"{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} - {e} - Could not process: {ln} | {self.container}")
                            self.failed_layers.append(f'{self.container} | {ln}')
                            pass

                except FileNotFoundError as e:
                    self.layer_errors.append(f"{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')} - FileNotFound - {e}")
                    return None

        elif ext in ['kml', 'kmz']:  # it's a kml file
            dt = 'KML'
            try:
                minx, miny, maxx, maxy = kmlextents(self.container)
                boundary = Polygon([
                    [minx, miny],
                    [maxx, miny],
                    [maxx, maxy],
                    [minx, maxy]
                ])

                feats.append(get_geojson_record(
                    geom=boundary,
                    datatype=dt,
                    fname=os.path.split(self.container)[1],
                    path=os.path.split(self.container)[0],
                    nativecrs=4326,  # KML is always in 4326
                    lastmod=moddate(self.container)
                ))

            except Exception as e:
                return None

        return {'feats': feats,
                'errors': self.layer_errors,
                'failed_layers': self.failed_layers}


class Exif(object):
    exif_data = None
    image = None

    def __init__(self, img_path):
        self.img_path = img_path
        self.image = Image.open(img_path)
        self.get_exif_data()
        super(Exif, self).__init__()

        self.dt = 'JPEG Image'

    def get_exif_data(self):
        """
        Opens an Exif instance (jpg format), determines if GPS coordinates are available,
        and returns location as a geojson point object.

        :return: json
        """
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

                return get_geojson_record(geom=point,
                                          datatype=self.dt,
                                          fname=os.path.split(self.img_path)[1],
                                          path=os.path.split(self.img_path)[0],
                                          nativecrs=4326,
                                          lastmod=moddate(self.img_path))

        except Exception:
            return None


class Lidar:

    def __init__(self, lidar_file):
        """
        Constructor.  Requires input lidar file (*.las, *.laz).

        :param lidar_file: Input Lidar dataset
        :type lidar_file: str
        """
        self.lidar_file = lidar_file

    def _run_pdal(self):
        """
        Invokes PDAL and pipes output back to python as json.

        :return: dict
        """
        r = (sp.run(['pdal', 'info', self.lidar_file, '--metadata'],
                    stderr=sp.PIPE,
                    stdout=sp.PIPE))

        return json.loads(r.stdout.decode())

    def get_props(self):
        """
        Parses the PDAL-obtained metadata and returns a schema and geojson object to be
        passed for writing.

        :return: dict
        """

        # local parameters
        path, fname = os.path.split(self.lidar_file)
        stats = Lidar._run_pdal(self)

        try:
            # Read metadata
            md = stats['metadata']

            # Get native CRS and project to WGS84
            cmpd_crs = json.loads(
                CRS.to_json(
                    CRS.from_wkt(md['comp_spatialreference'])
                )
            )
            native_crs = cmpd_crs['components'][0]['id']['code']
            bounds = md['minx'], md['miny'], md['maxx'], md['maxy']

            if native_crs != 4326:
                minx, miny, maxx, maxy = to_wgs84(native_crs, bounds)
            else:
                minx, miny, maxx, maxy = bounds[0], bounds[1], bounds[2], bounds[3]

            # Create the geometry
            boundary = Polygon([
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy]
            ])

            return get_geojson_record(
                geom=boundary,
                datatype="Lidar",
                fname=fname,
                path=path,
                nativecrs=cmpd_crs['components'][0]['id']['code'],
                lastmod=moddate(self.lidar_file)
            )

        except Exception as e:
            return None


class Raster:

    def __init__(self, raster_file):
        self.raster_file = raster_file

    def _get_file_extension(self):
        return os.path.splitext(os.path.split(self.raster_file)[1])[1][1:]

    def _get_raster_extents(self):
        pass

    def get_props(self):
        ext = Raster._get_file_extension(self)
        if ext.startswith('dt'):
            dt = 'DTED'
        elif ext in ['nitf', 'ntf']:
            dt = 'NITF'
        else:
            dt = 'Raster'

        try:
            with rasterio.open(self.raster_file) as r:
                try:
                    epsg = r.crs.to_epsg()
                    bounds = r.bounds
                    if epsg:
                        if epsg != 4326:
                            bounds = bounds.left, bounds.bottom, bounds.right, bounds.top
                            minx, miny, maxx, maxy = to_wgs84(epsg, bounds)
                        else:
                            minx, miny, maxx, maxy = bounds.left, bounds.bottom, bounds.right, bounds.top

                        boundary = Polygon([
                            [minx, miny],
                            [maxx, miny],
                            [maxx, maxy],
                            [minx, maxy]
                        ])

                        return get_geojson_record(geom=boundary,
                                                  datatype=dt,
                                                  fname=r.name,
                                                  path=os.path.split(self.raster_file)[0],
                                                  nativecrs=r.crs.to_epsg(),
                                                  lastmod=moddate(self.raster_file))
                except Exception:
                    try:
                        ds = gdal.Open(self.raster_file)
                        md = ds.GetMetadata()
                        filename = md.get('NITF_FTITLE', os.path.split(self.raster_file)[1])
                        for k, v in md.items():
                            if k == 'NITF_IGEOLO':
                                bounds_str = v
                                orig_coords = dms_to_dd(bounds_str[30:45])
                                b_coords = dms_to_dd(bounds_str[45:])
                                c_coords = dms_to_dd(bounds_str[:15])
                                d_coords = dms_to_dd(bounds_str[15:30])

                                boundary = Polygon([
                                    [orig_coords[1], orig_coords[0]],
                                    [b_coords[1], b_coords[0]],
                                    [c_coords[1], c_coords[0]],
                                    [d_coords[1], d_coords[0]]
                                ])

                                return get_geojson_record(geom=boundary,
                                                          datatype=dt,
                                                          fname=filename,
                                                          path=os.path.split(self.raster_file)[0],
                                                          nativecrs=4326,
                                                          lastmod=moddate(self.raster_file))

                    except Exception as e:
                        return None
        except Exception as e:
            return None


class Shapefile:

    def __init__(self, shpfile):
        self.shp = shpfile

    def get_props(self):
        try:
            gdf = gpd.read_file(self.shp)
            org_crs = int(str(gdf.crs).split(':')[1])
            if org_crs != 4326:
                minx, miny, maxx, maxy = to_wgs84(org_crs, gdf.geometry.total_bounds)
            else:
                minx, miny, maxx, maxy = gdf.geometry.total_bounds

            boundary = Polygon([
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy]
            ])

            return get_geojson_record(geom=boundary,
                                      datatype='Shapefile',
                                      fname=os.path.split(self.shp)[1],
                                      path=os.path.split(self.shp)[0],
                                      nativecrs=org_crs,
                                      lastmod=moddate(self.shp))

        except Exception as e:
            return e


# static methods
def dms_to_dd(coords):
    lat_d = coords[:2]
    lat_m = coords[2:4]
    lat_s = coords[4:6]
    lat_dir = coords[6:7]

    lon_d = coords[7:10]
    lon_m = coords[10:12]
    lon_s = coords[12:14]
    lon_dir = coords[14:15]

    dd_lat = float(lat_d) + float(lat_m) / 60 + float(lat_s) / 3600
    if lat_dir == 'S':
        dd_lat = 0 - dd_lat

    dd_lon = float(lon_d) + float(lon_m) / 60 + float(lon_s) / 3600
    if lon_dir == 'W':
        dd_lon = 0 - dd_lon

    return dd_lat, dd_lon


def get_centroid(geom):
    return geom.centroid


def get_geojson_record(geom, datatype, fname, path, nativecrs, lastmod, img_popup=None):
    if img_popup:
        return json.dumps({"type": "Feature",
                           "geometry": mapping(geom),
                           "properties": OrderedDict([
                               ("dataType", datatype),
                               ("fname", fname),
                               ("path", f'file:///{path}'),
                               ("img_popup", f'file:///{img_popup}'),
                               ("native_crs", nativecrs),
                               ("lastmod", lastmod)
                           ])})
    else:
        return json.dumps({"type": "Feature",
                           "geometry": mapping(geom),
                           "properties": OrderedDict([
                               ("dataType", datatype),
                               ("fname", fname),
                               ("path", f'file:///{path}'),
                               ("native_crs", nativecrs),
                               ("lastmod", lastmod)
                           ])})


def kmlextents(kmlfile):
    yf = []
    xf = []
    data = None

    if type(kmlfile) is str:
        if kmlfile.lower().endswith('kmz'):  # It's a KMZ and has to be unzipped
            data = openkmz(kmlfile)
        elif kmlfile.lower().endswith('kml'):  # It's a KML and does not have to be unzipped
            data = openkml(kmlfile)

        data = data.replace('\n', '').replace('\r', '').replace('\t', '')

        try:
            ys = re.findall(r'<latitude>(.+?)</latitude>', data)
            xs = re.findall(r'<longitude>(.+?)</longitude>', data)

            if len(xs) > 0 and len(ys) > 0:
                for x in xs:
                    xf.append(float(x))
                for y in ys:
                    yf.append(float(y))

            else:
                try:
                    coords = re.findall(r'<coordinates>(.+?)</coordinates>', data)

                    for coord in coords:
                        try:
                            coord = coord.lstrip().split(' ')
                            for c in coord:
                                try:
                                    c = c.lstrip().split(' ')
                                    for i in c:
                                        x, y, z = i.split(',')
                                        xf.append(float(x))
                                        yf.append(float(y))
                                except Exception:
                                    try:
                                        print(c.split(','))
                                        x, y, z = c.split(',')
                                        xf.append(float(x))
                                        yf.append(float(y))

                                    except Exception:
                                        pass

                        except Exception:
                            pass

                except Exception:
                    pass

        except Exception:
            pass

    if len(xf) > 0 and len(yf) > 0:
        minx = min(xf)
        miny = min(yf)
        maxx = max(xf)
        maxy = max(yf)

        return minx, miny, maxx, maxy

    else:
        return None


def moddate(filename):
    lm = os.stat(filename).st_mtime
    return datetime.fromtimestamp(lm).strftime('%Y-%m-%dT%H:%M:%S')


def openkml(kml):
    with open(kml, 'r') as okml:
        data = okml.read()
    return data


def openkmz(kmz):
    data = None
    for n in ZipFile(kmz).namelist():
        if n.lower().endswith('kml'):  # get the doc.kml or other enclosed kml
            with ZipFile(kmz, 'r') as kml:
                data = kml.read(n).decode(encoding='utf8')
    return data


def to_wgs84(native_epsg, bounds):
    proj = pyproj.Transformer.from_crs(native_epsg, 4326, always_xy=True)
    minx, miny = proj.transform(bounds[0], bounds[1])
    maxx, maxy = proj.transform(bounds[2], bounds[3])
    return minx, miny, maxx, maxy
