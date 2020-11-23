import geopandas as gpd
import os
import static
from shapely.geometry import Polygon


class ShapeQ:

    def __init__(self, shpfile):
        self.shp = shpfile
        
    def get_props(self):
        try:
            gdf = gpd.read_file(self.shp)
            org_crs = int(str(gdf.crs).split(':')[1])
            if org_crs != 4326:
                minx, miny, maxx, maxy = static.to_wgs84(org_crs, gdf.geometry.total_bounds)
            else:
                minx, miny, maxx, maxy = gdf.geometry.total_bounds
                
            boundary = Polygon([
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy]
            ])
            
            return static.get_geojson_record(geom=boundary,
                                             datatype='Shapefile',
                                             fname=os.path.split(self.shp)[1],
                                             path=os.path.split(self.shp)[0],
                                             nativecrs=org_crs,
                                             lastmod=static.moddate(self.shp))
            
        except Exception as e:
            print(f'{e}: Problem reading shapefile to geodataframe.')
            return None
