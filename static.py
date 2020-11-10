from collections import OrderedDict
import json
import pyproj
from pyproj import CRS
from shapely.geometry import mapping


def get_schema(geom_type):
    return {"geometry": geom_type,
            "properties": OrderedDict([
                ("id", "int"),
                ("dataType", "str"),
                ("fname", "str"),
                ("path", "str"),
                ("native_crs", "int")
            ])}
            
            
def to_wgs84(native_epsg, bounds):
    proj = pyproj.Transformer.from_crs(CRS.from_user_input(int(native_epsg)), CRS.from_user_input(4326), always_xy=True)
    minx, miny = proj.transform(bounds[0], bounds[1])
    maxx, maxy = proj.transform(bounds[2], bounds[3])
    return minx, miny, maxx, maxy
    
    
def get_geojson_record(geom, oid, datatype, fname, path, nativecrs):
    return json.dumps({"type": "Feature",
                       "geometry": mapping(geom),
                       "properties": OrderedDict([
                           ("id", oid),
                           ("dataType", datatype),
                           ("fname", fname),
                           ("path", path),
                           ("native_crs", nativecrs)
                       ])})
                       
