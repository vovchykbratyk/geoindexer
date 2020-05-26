import os
import sys


import arcpy


class MapExtent:
    """Basic found-file object"""

    def __init__(self, file):
        self.file = file
        desc = arcpy.Describe(self.file)
        if hasattr(desc, "dataType"):
            dt = desc.dataType
            if dt == ""


class RasterIn(MapExtent):
    """raster subclass"""
    def __init__(self, file, extension):
        super().__init__(file)
        self.extension = extension
        pass

    def tiff_extent(self):
        r = arcpy.sa.Raster(self.file)



class VectorIn(MapExtent):
    """vector subclass"""
    def __init__(self, file, extension):
        super().__init__(file)
        self.extension = extension
        pass
