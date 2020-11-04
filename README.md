# geoindexer
GeoIndexer is intended to help people with large amounts of uncatalogued spatial data to discover and catalogue it spatially.  This happens sometimes in large organizations where a NAS/SAN might get stuffed with content and nobody really has a good idea of what is where.  GeoIndexer can find and represent these holdings by either points (discrete locations) or polygons (coverage extents) that can be overlaid on a map and used to quickly locate and use the asset.

## data types supported
1. Raster (TIFF, DTED, NITF, database arrays in containers such as Esri File Geodatabase and GeoPackage)
2. Vector (SHP, containerized content such as Esri feature classes, GeoPackage layers, KML layers) # under development
3. Lidar (.las, .laz)
4. Web images (JPEG, and PNG theoretically)
5. Other containerized content (KML-wrapped content such as Collada models, valid GeoJSON files, OpenStreetMap Planet Binary Format (PBF) # under development

## installation
tbd

### dependencies
```fiona, gdal, pdal, PIL, pyproj, rasterio, shapely```

in /arcpy/ there are some methods i'm testing using Esri's arcpy libraries.

## usage
tbd

## licensing
GeoIndexer relies on Free and Open Source (FOSS) libraries and is itself FOSS.  Do whatever you want with it.  The version that supports `arcpy`, obviously, requires an ArcGIS license of some sort.
