from collections import OrderedDict
import json
import pyproj
from pyproj import CRS
import re
from shapely.geometry import mapping
from zipfile import ZipFile


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
    proj = pyproj.Transformer.from_crs(native_epsg, 4326, always_xy=True)
    minx, miny = proj.transform(bounds[0], bounds[1])
    maxx, maxy = proj.transform(bounds[2], bounds[3])
    return minx, miny, maxx, maxy
    
    
def get_geojson_record(geom, datatype, fname, path, nativecrs):
    return json.dumps({"type": "Feature",
                       "geometry": mapping(geom),
                       "properties": OrderedDict([
                           ("dataType", datatype),
                           ("fname", fname),
                           ("path", path),
                           ("native_crs", nativecrs)
                       ])})


def _openkmz(kmz):
    data = None
    for n in ZipFile(kmz).namelist():
        if n.lower().endswith('kml'):  # get the doc.kml or other enclosed kml
            with ZipFile(kmz, 'r') as kml:
                data = kml.read(n).decode(encoding='utf8')
    return data


def _openkml(kml):
    with open(kml, 'r') as openkml:
        data = openkml.read()
    return data


def kmlextents(kmlfile):
    yf = []
    xf = []
    data = None

    if type(kmlfile) is str:
        if kmlfile.lower().endswith('kmz'):  # It's a KMZ and has to be unzipped
            data = _openkmz(kmlfile)
        elif kmlfile.lower().endswith('kml'):  # It's a KML and does not have to be unzipped
            data = _openkml(kmlfile)

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
                                except Exception as e:
                                    print(f'{e}... trying something else')
                                    try:
                                        print(c.split(','))
                                        x, y, z = c.split(',')
                                        xf.append(float(x))
                                        yf.append(float(y))

                                    except Exception as e:
                                        print(f'{e}... that didnt work either')
                                        pass

                        except Exception as e:
                            print(f'{e}...something in inner loop failed...')
                            pass
                except Exception as e:
                    print(f'{e}...something in inner loop failed...')
                    pass

        except Exception:
            print('exception')
            pass

    if len(xf) > 0 and len(yf) > 0:
        minx = min(xf)
        miny = min(yf)
        maxx = max(xf)
        maxy = max(yf)

        return minx, miny, maxx, maxy

    else:
        return None
