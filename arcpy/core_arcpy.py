"""Crawls a directory structure looking for geospatial data types, reporting it in various ways"""

# Imports
import arcpy
from arcpy.sa import *
import os
from pathlib import Path
from tkinter.filedialog import askdirectory


class GeoCrawler:

    def __init__(self, path, types):
        """
        Default GeoCrawler instance.

        :param path: The path to be crawled
        :type path: str
        :param types: List of file extensions
        :type types: list
        """
        self.path = path
        self.types = types

    def find_gis_files(self, recursive=True):
        """
        Searches path (default recursive) for filetypes and returns list of matches.

        :param recursive: Traverse directories recursively (default: True)
        :type recursive: bool
        :return: list
        """
        if recursive:
            try:
                return [str(p.resolve()) for p in Path(self.path).glob("**/*") if p.suffix in self.types]
            except PermissionError:
                pass
        else:
            try:
                return [str(p.resolve()) for p in Path(self.path).glob("*") if p.suffix in self.types]
            except PermissionError:
                pass


class GeoIndexer:

    def __init__(self, file_list):
        """
        Initializes the GeoIndexer class with a list of files to be sifted and parsed into extent polygons.

        :param file_list: List of absolute paths to matching files
        :type file_list: list
        """
        self.file_list = file_list
        self.default_sr = arcpy.SpatialReference(4326)

    def get_file_info(self):
        """Orchestration method that checks each filetype and farms it out to the appropriate handler"""
        for f in self.file_list:
            desc = arcpy.Describe(f)
        if hasattr(desc, 'dataType'):
            filetype = (self.file, desc.dataType)
            if filetype[1] == "RasterDataset":
                raster_info = GeoIndexer.get_raster_geometry(self, self.file)
                for k, v in raster_info.items():
                    print(f"Property: {k} | Value: {v}")
                    print(raster_info['raster_sr'][0])
            elif filetype[1] == "ShapeFile":
                shp_ext = desc.extent
                return f"Found Shapefile: {str(self.file)}, {filetype[1]}, {shp_ext}"
            elif filetype[1] == "File":
                if desc.extension in ["laz", "las", "zlas"]:
                    return GeoIndexer.get_lidar_extent(self)
                elif desc.extension in ("json", "geojson"):
                    return GeoIndexer.get_geojson_extent(self)
            else:
                return f"File: {str(self.file)}, {filetype[1]}"

    def to_fgdb(self, gdb, fc_name, fields, geotype, rows):
        """
        Dumps results to a file geodatabase.

        :param gdb: UNC path to target file geodatabase
        :type gdb: str
        :param fc_name: Name of output feature class
        :type fc_name: str
        :param fields: List containing feature class fields
        :type fields: list
        :param geotype: Esri-standard geometry identifier
        :type geotype: str
        :param rows: Completed list of lists (features and attributes)
        :type rows: list
        """

        arcpy.env.overwriteOutput = True

        if not arcpy.Exists(gdb):
            gdb_path, gdb_filename = os.path.split(gdb)
            gdb_filename, gdb_extension = os.path.splitext(gdb_filename)
            gdb = arcpy.CreateFileGDB_management(gdb_path, gdb_filename)
            arcpy.env.Workspace = gdb
        else:
            arcpy.env.Workspace = gdb

        if not arcpy.Exists(os.path.join(gdb, fc_name)):
            fc = arcpy.CreateFeatureclass_management(gdb, fc_name, geotype, self.default_sr).getOutput(0)
            arcpy.AddFields_management(fc, fields)
        else:
            fc = fc_name

        fm = GeoIndexer.get_fieldmap(fields)
        fm.insert(0, GeoIndexer.get_geotoken(geotype))
        fieldmap = tuple(fm)

        with arcpy.da.InsertCursor(fc, fieldmap) as cursor:
            for row in rows:
                cursor.insertRow(row)

        fc_stats = {
            "name": fc_name,
            "rows": len(rows)
        }
        return fc_stats

    @staticmethod
    def get_geotoken(geom_type):
        if geom_type == "POINT":
            return "SHAPE@XY"
        elif geom_type in ("POLYLINE", "POLYGON"):
            return "SHAPE@"

    @staticmethod
    def get_fieldmap(flds):
        return [f[0] for f in flds]

    def get_raster_geometry(self, raster_in):
        """
        Returns a dictionary containing raster extent and path location.
        """
        poly = None
        ras = Raster(str(raster_in))
        ras_extent = [
            [
                [ras.extent.YMin, ras.extent.XMin],
                [ras.extent.YMax, ras.extent.XMin],
                [ras.extent.YMax, ras.extent.XMax],
                [ras.extent.YMin, ras.extent.XMax]
            ]
        ]
        for coord_ring in ras_extent:
            poly = arcpy.Polygon(
                arcpy.Array(
                    [arcpy.Point(*coords) for coords in coord_ring]
                ),
                ras.spatialReference
            ).projectAs(self.default_sr)

        return {
            "name": ras.name,
            "path": ras.path,
            "extent": poly,
        }

    def get_lidar_extent(self):
        """
        Loads lidar point cloud header and looks for spatial reference and min/max extents.  Attempts to use
        Esri library if file is a .las or .zlas.
        """
        pass

    def get_geojson_extent(self):
        """
        Reads .json or .geojson files for content that follows GeoJSON spec and constructs a feature class
        from the extent.
        """
        pass

    def get_shapefile_extent(self, description):
        """
        Returns a shapefile extent as a polygon.
        :param self (class instance)
        :param description (arcpy.Describe() object)
        """
        pass

    def get_fgdb_extents(self):
        """
        Opens a file geodatabase or a geopackage, iterating over the contained feature classes, returning an
        extent and path for each.
        :param self (class instance)
        :param in_file (file object)
        """
        gdb_rows = []
        gdb_fmap = ()
        with arcpy.da.Walk(self.file) as walk:
            for path, names, fc_list in walk:
                for fname in fc_list:
                    fc_extent = fname.extent
                    print(f"Extent of feature class: {fc_extent.XMin}, {fc_extent.YMin}, {fc_extent.XMax}, {fc_extent.YMax}")




# Testing #
# filetypes = [".shp", ".kmz", ".kml", ".tif", ".geotiff",
#              ".nitf", ".ntf", ".las", ".laz", ".bpf",
#              ".txt", ".csv", ".json", ".geojson",
#              ".gdb", ".gpkg"]
#
# mypath = r"C:/Data"
#
# raster_holdings = {}
# vector_holdings = {}
#
# my_files = GeoCrawler(mypath, filetypes)
# ff = my_files.find_gis_files()
# print(ff)
