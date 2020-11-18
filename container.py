from collections import OrderedDict
import fiona
import json
import os
import pyproj
from shapely.geometry import mapping, Polygon
import static


class ContainerQ:

    def __init__(self, container):
        self.container = container
        self.crs = 4326

    def _to_wgs84(self, native_epsg, bounds):
        proj = pyproj.Transformer.from_crs(native_epsg, self.crs, always_xy=True)
        min_x, min_y = proj.transform(bounds[0], bounds[1])
        max_x, max_y = proj.transform(bounds[2], bounds[3])
        return min_x, min_y, max_x, max_y
    
    @staticmethod
    def _get_geojson_record(geom, oid, datatype, fname, path, nativecrs):
        return json.dumps({"type": "Feature",
                           "geometry": mapping(geom),
                           "properties": OrderedDict([
                               ("id", oid),
                               ("dataType", datatype),
                               ("fname", fname),
                               ("path", path),
                               ("native_crs", nativecrs)
                           ])})

    def get_props(self):
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
                                minx, miny, maxx, maxy = static.to_wgs84(lyr_crs, lyr.bounds)

                            else:
                                bounds = lyr.bounds
                                minx, miny, maxx, maxy = bounds[0], bounds[1], bounds[2], bounds[3]

                            boundary = Polygon([
                                [minx, miny],
                                [maxx, miny],
                                [maxx, maxy],
                                [minx, maxy]
                            ])

                            feats.append(static.get_geojson_record(
                                geom=boundary,
                                datatype=dt,
                                fname=ln,
                                path=self.container,
                                nativecrs=lyr_crs
                            ))

                        except (AttributeError, KeyError) as ke:
                            print(f'Error: {ke} - Layer {lyr} has no Coordinate Reference System.')
                            pass

                except FileNotFoundError:
                    print(f'File {self.container} not found or inaccessible.  Skipping...')
                    pass

        elif ext in ['kml', 'kmz']:  # it's a kml file
            dt = 'KML'
            try:
                minx, miny, maxx, maxy = static.kmlextents(self.container)
                boundary = Polygon([
                    [minx, miny],
                    [maxx, miny],
                    [maxx, maxy],
                    [minx, maxy]
                ])

                feats.append(static.get_geojson_record(
                    geom=boundary,
                    datatype=dt,
                    fname=os.path.split(self.container)[1],
                    path=os.path.split(self.container)[0],
                    nativecrs=4326  # KML is always in 4326
                ))

            except Exception as e:
                print(f"Error: {e} - KML {self.container} has no boundary properties.")
                pass
                    
        return feats
