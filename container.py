from collections import OrderedDict
import fiona
import json
import os
import pyproj
from pyproj import CRS
from shapely.geometry import mapping, Polygon
import warnings


class ContainerQ:

    def __init__(self, container):
        self.container = container
        self.crs = 4326

    def _to_wgs84(self, native_epsg, bounds):
        proj = pyproj.Transformer.from_crs(native_epsg, self.crs, always_xy=True)
        min_x, min_y = proj.transform(bounds[0], bounds[1])
        max_x, max_y = proj.transform(bounds[2], bounds[3])
        return min_x, min_y, max_x, max_y

    def get_props(self, oid):
        dt = None
        ext = os.path.splitext(os.path.split(self.container)[1])[1][1:]

        feats = []

        if ext == 'gdb':
            dt = 'Esri FGDB Feature Class'
        elif ext == 'gpkg':
            dt = 'GeoPackage Layer'
        elif ext == 'db':
            dt = 'SQLite Database Layer'

        for ln in fiona.listlayers(self.container):
            try:
                with fiona.open(self.container, layer=ln) as lyr:
                    try:
                        lyr_crs = lyr.crs['init'].split(':')[1]
                        if lyr_crs != str(4326):
                            minx, miny, maxx, maxy = ContainerQ._to_wgs84(self, lyr_crs, lyr.bounds)

                        else:
                            bounds = lyr.bounds
                            minx, miny, maxx, maxy = bounds[0], bounds[1], bounds[2], bounds[3]

                        boundary = Polygon([
                            [minx, miny],
                            [maxx, miny],
                            [maxx, maxy],
                            [minx, maxy]
                        ])

                        gj = {"type": "Feature",
                              "geometry": mapping(boundary),
                              "properties": OrderedDict([
                                  ("id", oid),
                                  ("dataType", dt),
                                  ("fname", ln),
                                  ("path", self.container),
                                  ("native_crs", lyr_crs)
                              ])}

                        feats.append(json.dumps(gj))

                    except (AttributeError, KeyError) as ke:
                        warnings.warn(f'Error: {ke} - Layer {lyr} has no Coordinate Reference System.')
                        pass
            except FileNotFoundError:
                warnings.warn(f'File {self.container} not found or inaccessible.  Skipping...')

        return feats
