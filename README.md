# geoindexer
GeoIndexer is intended to help people with large amounts of uncatalogued spatial data to discover and catalogue it spatially.  It often happens in large organizations where a NAS/SAN might get stuffed with content and nobody really has a good idea of what data covers what locations on the earth.  GeoIndexer can find and represent these holdings by either points (discrete locations) or polygons (coverage extents) that can be overlaid on a map and used to quickly locate and use the asset.

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
Here is a simple example using GeoIndexer to discover and construct coverage geometry for GeoPackage layers, File Geodatabase layers, Lidar point clouds, JPEG images, TIFF rasters and NITF rasters, outputting the coverage to a set of GeoPackage layers for various coverage scales.
```
from geoindexer import GeoCrawler, GeoIndexer


if __name__ == '__main__':

    searchpath = "C:/path/to/data"
    ftypes = ['gpkg', 'kml', 'kmz', 'jpg',
              'jpeg', 'las', 'laz', 'tif',
              'tiff', 'ntf', 'nitf', 'dt0',
              'dt1', 'dt2', 'shp', 'gdb']
    logpath = "C:/Temp"

    search = GeoCrawler(searchpath, ftypes).get_file_list()
    results = GeoIndexer(search).get_extents(logging=logpath)

    # Split out the results to do stuff with them
    cvg_areas = results[0]
    statistics = results[1]
    failures = results[2]

    # Output it as a GeoPackage
    gpkg = 'C:/Temp/gpkg_test_fiona.gpkg'
    areas = GeoIndexer.to_geopackage(cvg_areas,
                                     path=gpkg)

    print('--------------------------')
    print('--------STATISTICS--------')
    print('--------------------------')
    for k, v in statistics.items():
        print(f"{k.title().replace('_', ' ')}: {v}")

    print('')

    for k, v in failures.items():
        print(f'Failed {k.title()}:')
        for x in v:
            if k == "layers":
                print(f'\t{" | ".join(x)}')
            else:
                print(f'\t{x}')


```

## licensing
GeoIndexer relies on Free and Open Source (FOSS) libraries and any/all restrictions attached to those libraries are
inherited. As I am new to this, I am also still sort of figuring out licensing and will update this as I go.
Any leverage of the `arcpy` library, obviously, requires an ArcGIS license of some sort.
