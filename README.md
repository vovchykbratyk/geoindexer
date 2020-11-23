# geoindexer
GeoIndexer is intended to help people with large amounts of uncatalogued spatial data to discover and catalogue it spatially.  This happens sometimes in large organizations where a NAS/SAN might get stuffed with content and nobody really has a good idea of what is where.  GeoIndexer can find and represent these holdings by either points (discrete locations) or polygons (coverage extents) that can be overlaid on a map and used to quickly locate and use the asset.

## data types supported
1. Raster (TIFF, DTED, NITF, GeoPackage raster layers)
2. Vector (SHP, containerized content such as Esri feature classes, GeoPackage layers, KML layers)
3. Lidar (.las, .laz)
4. Web images (JPEG, and PNG... theoretically)
5. Other containerized content (KML-wrapped content such as Collada models, valid GeoJSON files, OpenStreetMap Planet Binary Format (PBF) # under development

## installation
`git clone https://github.com/vovchykbratyk/geoindexer.git`

This project has been a learning experience for me, so eventually when I learn how to wrap all this up with a `setup.py`
file, I'll submit it for `pip` and `conda` installation.

### dependencies
```fiona, gdal, pdal, PIL, pyproj, rasterio, shapely```

in /arcpy/ there are some methods i'm testing using Esri's `arcpy` libraries.

## example usage
```
from geoindexer import core as gi

"""
This example will find and generate extents for raster, 
geopackage layers, file geodatabase layers and lidar point
clouds within a search path, returning it as a geojson
object that can be easily cast to any number of formats
"""

path = '/path/to/search'
filetypes = ['gpkg', 'gdb', 'tif', 'laz']
found = gi.GeoCrawler(path)

coverage = gi.GeoIndexer(found).get_extents()
```

## licensing
GeoIndexer relies on Free and Open Source (FOSS) libraries and any/all restrictions attached to those libraries are
inherited. Any leverage of the `arcpy` library, obviously, requires an ArcGIS license of some sort.