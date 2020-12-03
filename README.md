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


if __name__ == '__main__':
    
    # Setup parameters
    searchpath = "path/to/data"
    ftypes = ['gpkg', 'kml', 'kmz', 'jpg',
              'jpeg', 'las', 'laz', 'tif',
              'tiff', 'ntf', 'nitf', 'dt0',
              'dt1', 'dt2', 'shp', 'gdb']
    logpath = "path/to/log"

    # Discover results and get their coverage extents
    search = GeoCrawler(searchpath, ftypes).get_file_list()
    results = GeoIndexer(search).get_extents(logging=logpath)

    # Split out the results to do things with them.
    cvg_areas = results[0]  # this is the geojson object
    statistics = results[1]  # these are various reporting stats
    failures = results[2]  # this is a list of files/layers that failed just in case

    # Put it in a GeoDataframe
    gdf = gpd.GeoDataFrame.from_features(cvg_areas['features'])

    # Set up a geopackage object to write it out
    gpkg_out = "C:/Temp/coverage_new.gpkg"
    driver = "GPKG"

    points = gdf.copy()
    points['geometry'] = points['geometry'].centroid  # Create a set of center points, helpful with very dense data
    points.to_file(gpkg_out, layer="cvg_centroids", driver=driver)
    gdf.to_file(gpkg_out, layer="cvg_original", driver=driver)

    # Now report some optional statistics
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
