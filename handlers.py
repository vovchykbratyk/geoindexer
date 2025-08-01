from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import subprocess as sp
import json
import logging

import fiona
from fiona import open as fiona_open
from fiona.crs import CRS
import rasterio
from pyproj import CRS as PyCRS
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from shapely.geometry import Point, Polygon
from osgeo import gdal, ogr

from wrenches import (
    get_geometry,
    moddate,
    to_wgs84,
    dms_to_dd,
    kmlextents,
    get_geojson_record
)

# Optional: Configure a simple logger (can be adjusted by caller)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Container:
    def __init__(self, container_path: str, minimum_bounding_geometry: bool = False):
        self.container = container_path
        self.layer_errors = []
        self.failed_layers = []
        self.mbg = minimum_bounding_geometry

    def get_props(self) -> dict:
        ext = Path(self.container).suffix.lower()[1:]
        feats = []

        if ext in {'gdb', 'gpkg', 'db'}:
            datatype = {
                'gdb': 'Esri FGDB Feature Class',
                'gpkg': 'GeoPackage Layer',
                'db': 'SQLite Database Layer'
            }.get(ext, 'Unknown Container')

            for layer_name in fiona.listlayers(self.container):
                try:
                    geom, crs = get_geometry(
                        self.container,
                        minimum_bounding_geometry=self.mbg,
                        layer=layer_name
                    )
                    if not geom or not crs:
                        continue

                    epsg_code = PyCRS.from_user_input(crs).to_epsg() or 4326

                    if geom.is_valid and geom.area > 0:
                        feats.append(get_geojson_record(
                            geom=geom,
                            datatype=datatype,
                            fname=layer_name,
                            path=self.container,
                            nativecrs=epsg_code,
                            lastmod=moddate(self.container)
                        ))
                except Exception as e:
                    msg = f"{datetime.now().isoformat()} - {e} - {self.container} | {layer_name}"
                    self.layer_errors.append(msg)
                    self.failed_layers.append(f"{self.container} | {layer_name}")
        elif ext in {'kml', 'kmz'}:  # KML/KMZ can also be thought of as a container
            try:
                bounds = kmlextents(self.container)
                if bounds:
                    minx, miny, maxx, maxy = bounds
                    polygon = Polygon([
                        [minx, miny], [maxx, miny],
                        [maxx, maxy], [minx, maxy]
                    ])
                    feats.append(get_geojson_record(
                        geom=polygon,
                        datatype="KML",
                        fname=Path(self.container).name,
                        path=str(Path(self.container).parent),
                        nativecrs=4326,
                        lastmod=moddate(self.container)
                    ))
            except Exception as e:
                msg = f"{datetime.now().isoformat()} - {e} - {self.container}"
                self.layer_errors.append(msg)

        return {
            'feats': feats,
            'errors': self.layer_errors,
            'failed_layers': self.failed_layers
        }


class Exif:
    def __init__(self, img_path: str):
        self.img_path = img_path
        self.datatype = "JPEG Image"
        self.exif_data = None

    def _extract_exif(self) -> dict:
        """Extract and decode EXIF data, including GPS tags if available."""
        data = {}
        try:
            with Image.open(self.img_path) as img:
                raw = img._getexif()
                if not raw:
                    return {}
                for tag, value in raw.items():
                    name = TAGS.get(tag, tag)
                    if name == "GPSInfo":
                        gps = {GPSTAGS.get(t, t): value[t] for t in value}
                        data[name] = gps
                    else:
                        data[name] = value
        except Exception as e:
            logger.debug(f"EXIF read failed for {self.img_path}: {e}")
        return data
    

    @staticmethod
    def _convert_to_degrees(dms: tuple) -> float | None:
        try:
            return dms[0] + dms[1] / 60.0 + dms[2] / 3600.0
        except (TypeError, IndexError, ZeroDivisionError):
            return None
        
    @staticmethod
    def batch(image_paths: list[str], max_workers: int = 8) -> list[dict]:
        """
        Threaded EXIF extractor for a list of images. Returns GeoJSON records
        (point) for images with GPS data.
        """
        def worker(img_path: str) -> dict | None:
            try:
                props = Exif(img_path).get_props()
                if props and "geometry" in props:
                    return props
            except Exception as e:
                logger.debug(f"Threaded EXIF processing failed: {e}")
            return None
        
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(worker, p): p for p in image_paths}
            for f in as_completed(futures):
                result = f.result()
                if result:
                    results.append(result)
        return results

    def get_props(self) -> dict | None:
        """Returns a GeoJSON point from EXIF GPS coordinates, if present."""
        try:
            self.exif_data = self.exif_data or self._extract_exif()
            gps = self.exif_data.get("GPSInfo")
            if not gps:
                return None

            lat = self._convert_to_degrees(gps.get("GPSLatitude"))
            if gps.get("GPSLatitudeRef") == "S" and lat is not None:
                lat = -lat

            lon = self._convert_to_degrees(gps.get("GPSLongitude"))
            if gps.get("GPSLongitudeRef") == "W" and lon is not None:
                lon = -lon

            if lat is not None and lon is not None:
                point = Point(lon, lat)
                return get_geojson_record(
                    geom=point,
                    datatype=self.datatype,
                    fname=Path(self.img_path).name,
                    path=str(Path(self.img_path).parent),
                    nativecrs=4326,
                    lastmod=moddate(self.img_path)
                )
        except Exception as e:
            logger.debug(f"Failed to extract GPS from {self.img_path}: {e}")
            return None


class Lidar:
    def __init__(self, lidar_file: str):
        self.lidar_file = lidar_file
        self.datatype = "Lidar"

    def _run_pdal(self) -> dict | None:
        """Invoke PDAL to extract metadata in JSON format."""
        try:
            result = sp.run(
                ['pdal', 'info', self.lidar_file, '--metadata'],
                stdout=sp.PIPE, stderr=sp.PIPE, check=True
            )
            return json.loads(result.stdout)
        except Exception as e:
            logger.warning(f"PDAL failed on {self.lidar_file}: {e}")
            return None

    def get_props(self) -> dict | None:
        """Returns a GeoJSON polygon bounding box for the Lidar file."""
        stats = self._run_pdal()
        if not stats:
            return None

        try:
            md = stats['metadata']
            bounds = (md['minx'], md['miny'], md['maxx'], md['maxy'])

            # Extract and reproject CRS
            crs_wkt = md.get('comp_spatialreference')
            if not crs_wkt:
                logger.warning(f"No CRS found in PDAL metadata for {self.lidar_file}")
                return None

            crs_json = json.loads(CRS.from_wkt(crs_wkt).to_json())  # doublecheck from_wkt() call
            native_crs = crs_json['components'][0]['id']['code']
            if native_crs != 4326:
                minx, miny, maxx, maxy = to_wgs84(native_crs, bounds)
            else:
                minx, miny, maxx, maxy = bounds

            polygon = Polygon([
                [minx, miny], [maxx, miny],
                [maxx, maxy], [minx, maxy]
            ])

            return get_geojson_record(
                geom=polygon,
                datatype=self.datatype,
                fname=Path(self.lidar_file).name,
                path=str(Path(self.lidar_file).parent),
                nativecrs=native_crs,
                lastmod=moddate(self.lidar_file)
            )
        except Exception as e:
            logger.warning(f"Lidar parsing failed for {self.lidar_file}: {e}")
            return None


class Raster:
    def __init__(self, raster_file: str):
        self.raster_file = raster_file
        self.ext = Path(raster_file).suffix.lower()[1:]
        self.datatype = self._infer_datatype()

    def _infer_datatype(self) -> str:
        if self.ext.startswith("dt"):
            return "DTED"
        elif self.ext in {"ntf", "nitf"}:
            return "NITF"
        return "Raster"

    def get_props(self) -> dict | None:
        """Returns a GeoJSON polygon for raster bounds, using Rasterio or GDAL as fallback."""
        try:
            with rasterio.open(self.raster_file) as r:
                epsg = r.crs.to_epsg() if r.crs else 4326
                bounds = r.bounds
                if epsg != 4326:
                    minx, miny, maxx, maxy = to_wgs84(epsg, (bounds.left, bounds.bottom, bounds.right, bounds.top))
                else:
                    minx, miny, maxx, maxy = bounds.left, bounds.bottom, bounds.right, bounds.top

                polygon = Polygon([
                    [minx, miny], [maxx, miny],
                    [maxx, maxy], [minx, maxy]
                ])

                return get_geojson_record(
                    geom=polygon,
                    datatype=self.datatype,
                    fname=Path(self.raster_file).name,
                    path=str(Path(self.raster_file).parent),
                    nativecrs=epsg,
                    lastmod=moddate(self.raster_file)
                )

        except Exception as rasterio_error:
            logger.debug(f"Rasterio failed for {self.raster_file}: {rasterio_error}")

        # Fallback: Use GDAL if Rasterio fails (e.g., older NITF formats)
        try:
            ds = gdal.Open(self.raster_file)
            md = ds.GetMetadata()

            coords = md.get('NITF_IGEOLO')
            if coords:
                b1 = dms_to_dd(coords[30:45])
                b2 = dms_to_dd(coords[45:])
                b3 = dms_to_dd(coords[:15])
                b4 = dms_to_dd(coords[15:30])

                polygon = Polygon([
                    [b1[1], b1[0]], [b2[1], b2[0]],
                    [b3[1], b3[0]], [b4[1], b4[0]]
                ])

                return get_geojson_record(
                    geom=polygon,
                    datatype=self.datatype,
                    fname=Path(self.raster_file).name,
                    path=str(Path(self.raster_file).parent),
                    nativecrs=4326,
                    lastmod=moddate(self.raster_file)
                )
        except Exception as e:
            logger.warning(f"GDAL fallback failed for {self.raster_file}: {e}")

        return None


class Shapefile:
    def __init__(self, shpfile: str, minimum_bounding_geometry: bool = False):

        self.shp = shpfile
        self.datatype = "Shapefile"
        self.mbg = minimum_bounding_geometry

    def get_props(self) -> dict | None:
        """Returns a GeoJSON polygon bounding box or hull for shapefile data"""
        try:
            geom, epsg = get_geometry(
                self.shp,
                minimum_bounding_geometry=self.mbg
            )
            if not geom or not epsg:
                return None
            
            return get_geojson_record(
                geom=geom,
                datatype=self.datatype,
                fname=Path(self.shp).name,
                path=str(Path(self.shp).parent),
                nativecrs=epsg,
                lastmod=moddate(self.shp)
            )
        except Exception as e:
            logger.warning(f"Shapefile processing failed for {self.shp}: {e}")
            return None


class Log:
    def __init__(self, lines: list[str]):
        self.lines = lines

    def to_file(self, output_dir: str) -> str:
        """Writes log lines to a timestamped log file in the given directory."""
        logname = f"geoindexer_{datetime.now().strftime('%Y%m%dT%H%M%S')}.log"
        log_path = Path(output_dir) / logname

        try:
            with log_path.open("w", encoding="utf-8") as f:
                for line in self.lines:
                    f.write(f"{line}\n")
            return logname
        except Exception as e:
            logger.warning(f"Failed to write log to {log_path}: {e}")
            return ""
