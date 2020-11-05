from collections import OrderedDict
import fiona
import json
import os
import pyproj
from pyproj import CRS
from shapely.geometry import mapping, Polygon


class ContainerQ:

    def __init__(self, containerfile):
        self.containerfile = containerfile
        self.crs = 4326
        self.container_ext = os.path.splitext(os.path.split(self.containerfile)[1])[1][1:]
        self.count = 0

    def get_layer_info(self):

        featurecollection = {'type': 'FeatureCollection',
                             'features': []}

        if self.container_ext in ['gdb', 'db', 'gpkg']:  # geodatabase
            feats = ContainerQ._get_db_layer_props(self)
            for f in feats:
                featurecollection['features'].append(f)
        elif self.container_ext in ['kml', 'kmz']:
            # do kml things
            pass
        elif self.container_ext in ['json', 'geojson']:
            # do geojson things
            pass

        return featurecollection

    def _to_wgs84(self, native_epsg, bounds):
        proj = pyproj.Transformer.from_crs(native_epsg, 4326, always_xy=True)
        min_x, min_y = proj.transform(bounds[0], bounds[1])
        max_x, max_y = proj.transform(bounds[2], bounds[3])
        return min_x, min_y, max_x, max_y

    def _get_db_layer_props(self):
        dt = None

        feats = []

        if self.container_ext == 'gdb':
            dt = 'Esri FGDB Feature Class'
        elif self.container_ext == 'gpkg':
            dt = 'GeoPackage Layer'
        elif self.container_ext == 'db':
            dt = 'SQLite Database Layer'

        for ln in fiona.listlayers(self.containerfile):
            with fiona.open(self.containerfile, layer=ln) as lyr:
                try:
                    lyr_crs = lyr.crs['init'].split(':')[1]
                    print(lyr_crs)
                    if lyr_crs != str(4326):
                        minx, miny, maxx, maxy = ContainerQ._to_wgs84(self, lyr_crs, lyr.bounds)

                    else:
                        bounds = lyr.bounds
                        print(bounds)
                        minx, miny, maxx, maxy = bounds[0], bounds[1], bounds[2], bounds[3]

                    boundary = Polygon([
                        [minx, miny],
                        [maxx, miny],
                        [maxx, maxy],
                        [minx, maxy]
                    ])

                    gj = {'type': 'Feature',
                          'geometry': mapping(boundary),
                          'properties': OrderedDict([
                              ('id', self.count),
                              ('dataType', dt),
                              ('fname', ln),
                              ('path', self.containerfile),
                              ('native_crs', lyr_crs)
                          ])}
                    feats.append(json.dumps(gj))
                    self.count += 1
                except (AttributeError, KeyError) as ke:
                    print(f'Error: {ke} - Layer {lyr} has no Coordinate Reference System.')

        return feats


# testing
fgdb_list = ['/home/eric/Data/MixedTypes.gdb',
             '/home/eric/Data/Network/Djibouti/DJI_Final/Network_Database/Djibouti_Network.gdb',
             '/home/eric/Data/Network/Iran/ABA_Final/Network_Database/Abadan_Delivery.gdb']

for f in fgdb_list:
    info = ContainerQ(f).get_layer_info()
    print(info)
