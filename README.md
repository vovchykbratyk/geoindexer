# geoindexer
GeoIndexer is intended to help people with large amounts of uncatalogued spatial data to discover and catalogue it spatially.  It often happens in large organizations where a NAS/SAN might get stuffed with content and nobody really has a good idea of what is where.  GeoIndexer can find and represent these holdings by either points (discrete locations) or polygons (coverage extents) that can be overlaid on a map and used to quickly locate and use the asset.

## data types supported
1. Raster (TIFF, DTED, NITF, GeoPackage raster layers)
2. Vector (SHP, containerized content such as Esri feature classes, GeoPackage layers, KML layers)
3. Lidar (.las, .laz)
4. Web images (JPEG, and PNG... theoretically)
5. *Under development* - Other containerized content (valid GeoJSON files, OpenStreetMap Planet Binary Format, virtual raster tables)
6. *Future plans* - Explicit/implicit location parsing in common document formats (.docx, .odt, .txt, .pdf)

## installation
`git clone https://github.com/vovchykbratyk/geoindexer.git`

This project has been a learning experience for me, eventually I will sit down and learn how to publish this for `pip` installation and will update this section.

### dependencies/requirements
```fiona, gdal, geopandas, pdal, PIL, pyproj, rasterio, shapely```

in /arcpy/ there are some methods i'm testing using Esri's `arcpy` libraries, but at this point I don't rely on them for anything.

## example usage
Here is a simple example using GeoIndexer with GeoPandas to discover and construct coverage geometry for GeoPackage layers, File Geodatabase layers, Lidar point clouds, JPEG images, TIFF rasters and NITF rasters, outputting the coverage to a GeoPackage layer.
```
from geoindexer import GeoCrawler, GeoIndexer
import geopandas as gpd


path = '/path/to/search'
filetypes = ['gpkg', 'gdb', 'jpg', 'tif', 'ntf', 'nitf', 'las', 'laz']

found = GeoCrawler(path, filetypes)
results = GeoIndexer(found).get_extents()
coverage = results[0]  # the geojson object
report = results[1]  # run statistics dict, do whatever with it

gdf = gpd.GeoDataFrame.from_features(coverage['features'])

outfile = "/home/username/output.gpkg"
layername = "coverage"
driver="GPKG"

gdf.to_file(outfile, layer=layername, driver=driver)
```

## licensing
GeoIndexer relies on Free and Open Source (FOSS) libraries and any/all restrictions attached to those libraries are
inherited. As I am new to this, I am also still sort of figuring out licensing and will update this as I go.
Any leverage of the `arcpy` library, obviously, requires an ArcGIS license of some sort.
