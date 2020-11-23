import gdal
import os
import pyproj
import rasterio
from shapely.geometry import Polygon
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
            
        try:
            with rasterio.open(self.raster_file) as r:
                try:
                    epsg = r.crs.to_epsg()
                    bounds = r.bounds
                    if epsg:
                        if epsg != 4326:
                            bounds = bounds.left, bounds.bottom, bounds.right, bounds.top
                            minx, miny, maxx, maxy = static.to_wgs84(epsg, bounds)
                        else:
                            minx, miny, maxx, maxy = bounds.left, bounds.bottom, bounds.right, bounds.top

                        boundary = Polygon([
                            [minx, miny],
                            [maxx, miny],
                            [maxx, maxy],
                            [minx, maxy]
                        ])

                        return static.get_geojson_record(geom=boundary,
                                                         datatype=dt,
                                                         fname=r.name,
                                                         path=os.path.split(self.raster_file)[0],
                                                         nativecrs=r.crs.to_epsg(),
                                                         lastmod=static.moddate(self.raster_file))
                except Exception as e:
                    try:
                        filename = None
                        
                        ds = gdal.Open(self.raster_file)
                        md = ds.GetMetadata()
                        filename = md.get('NITF_FTITLE', os.path.split(self.raster_file)[1])
                        for k, v in md.items():
                            if k == 'NITF_IGEOLO':
                                bounds_str = v
                                orig_coords = static.dms_to_dd(bounds_str[30:45])
                                b_coords = static.dms_to_dd(bounds_str[45:])
                                c_coords = static.dms_to_dd(bounds_str[:15])
                                d_coords = static.dms_to_dd(bounds_str[15:30])
                                
                                boundary = Polygon([
                                    [orig_coords[1], orig_coords[0]],
                                    [b_coords[1], b_coords[0]],
                                    [c_coords[1], c_coords[0]],
                                    [d_coords[1], d_coords[0]]
                                ])
                                
                                return static.get_geojson_record(geom=boundary,
                                                                 datatype=dt,
                                                                 fname=filename,
                                                                 path=os.path.split(self.raster_file)[0],
                                                                 nativecrs=4326,
                                                                 lastmod=static.moddate(self.raster_file))
                                                                 
                    except Exception as e:
                        print(f'{e}: Unable to open {self.raster_file} even with GDAL, giving up...')
                        return None
        except Exception:
            return None
