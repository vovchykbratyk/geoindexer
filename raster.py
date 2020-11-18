import os
import pyproj
import rasterio
from shapely.geometry import mapping, Polygon
import static

class RasterQ:

    def __init__(self, raster_file):
        self.raster_file = raster_file

    def _get_file_extension(self):
        return os.path.splitext(os.path.split(self.raster_file)[1])[1][1:]

    def _get_raster_extents(self):
        pass

    @staticmethod
    def _to_wgs84(native_epsg, bounds):
        proj = pyproj.Transformer.from_crs(native_epsg, 4326, always_xy=True)
        min_x, min_y = proj.transform(bounds.left, bounds.bottom)
        max_x, max_y = proj.transform(bounds.right, bounds.top)
        return min_x, min_y, max_x, max_y

    def get_props(self):
        ext = RasterQ._get_file_extension(self)
        if ext.startswith('dt'):
            dt = 'DTED'
        elif ext in ['nitf', 'ntf']:
            dt = 'NITF'
        else:
            dt = 'Raster'

        with rasterio.open(self.raster_file) as r:
            try:
                epsg = r.crs.to_epsg()
                if epsg:
                    if epsg != 4326:
                        bounds = r.bounds.left, r.bounds.bottom, r.bounds.right, r.bounds.top
                        minx, miny, maxx, maxy = static.to_wgs84(epsg, bounds)
                    else:
                        bounds = r.bounds
                        minx, miny, maxx, maxy = bounds.left, bounds.bottom, bounds.right, bounds.top

                    boundary = Polygon([
                        [minx, miny],
                        [maxx, miny],
                        [maxx, maxy],
                        [minx, maxy]
                    ])

                    return static.get_geojson_record(
                        geom=boundary,
                        datatype=dt,
                        fname=r.name,
                        path=os.path.split(self.raster_file)[0],
                        nativecrs=r.crs.to_epsg())

            except AttributeError:
                pass
