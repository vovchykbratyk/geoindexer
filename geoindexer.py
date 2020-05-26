"""Crawls a directory structure looking for geospatial data types, reporting it in various ways"""

# Imports
import arcpy
from arcpy.sa import *
import os
from pathlib import Path
from tkinter.filedialog import askdirectory


class GISCrawler:

    def __init__(self, path, types):
        self.path = path
        self.types = types

    def find_gis_files(self):
        try:
            return {p.resolve() for p in Path(self.path).glob("**/*") if p.suffix in self.types}
        except PermissionError:
            pass


class GeoExtractor:

    def __init__(self, file):
        self.file = file

    def get_file_info(self):
        desc = arcpy.Describe(str(self.file))
        if hasattr(desc, 'dataType'):
            filetype = (self.file, desc.dataType)
            if filetype[1] == "RasterDataset":
                ras = Raster(str(self.file))
                extent = ras.extent
                return {
                    "name": desc.file,
                    "extension": desc.extension,
                    "path": desc.path,
                    "XMin": extent.XMin,
                    "YMin": extent.YMin,
                    "XMax": extent.XMax,
                    "YMax": extent.YMax
                }
            elif filetype[1] == "ShapeFile":
                shp_ext = desc.extent
                return f"Found Shapefile: {str(self.file)}, {filetype[1]}, {shp_ext}"
            elif filetype[1] == "File":
                if desc.extension == "laz":
                    return GeoExtractor.get_laz_extent(self)
                elif desc.extension in ("json", "geojson"):
                    return GeoExtractor.parse_geojson(self)
            else:
                return f"File: {str(self.file)}, {filetype[1]}"

    def parse_geojson(self):
        pass

    def get_laz_extent(self):
        pass


filetypes = [".shp", ".kmz", ".kml", ".tif", ".geotiff",
             ".nitf", ".ntf", ".dt0", ".dt1", ".dt2",
             ".las", ".laz", ".bpf", ".txt", ".csv", ".json", ".geojson"]

mypath = r"C:/Data"

raster_holdings = {}
vector_holdings = {}

my_files = GISCrawler(mypath, filetypes)
found_files = my_files.find_gis_files()
for f in found_files:
    ff = GeoExtractor(f).get_file_info()
    print(ff)