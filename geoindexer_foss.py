import fiona
import gdal
import os
from pathlib import Path
from pyproj import CRS
import shapely


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
        self.file_list = file_list
        self.default_sr = CRS.from_user_input(4326)

    def determine_type(self, metadata):
        if 'DMD_E' in []:
            pass



    def get_file_info(self):

        for f in self.file_list:
            try:
                dataset = gdal.OpenEx(f)
                md = dataset.GetDriver().GetMetadata()


            except:
                print(f"GDAL error opening file {f}.")
            else:
                raster_capable = 'DCAP_RASTER' in md
                vector_capable = 'DCAP_VECTOR' in md
                print(f"raster: {raster_capable}, vector: {vector_capable}")
