from collections import OrderedDict
from datetime import datetime
import logging
from pathlib import Path
import re
from typing import Any, List
import uuid
from zipfile import ZipFile

import fiona
from fiona import open as fiona_open
from fiona.crs import CRS as fiona_crs
from pyproj import CRS as PyCRS, Transformer
from shapely.geometry import box, mapping, shape, Point, Polygon
from shapely.ops import unary_union, transform

from area import area

# Optional: Configure a simple logger (can be adjusted by caller)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_transformer_cache = {}  # stash transformers here to avoid recreation


# Internal functions
def _get_standard_schema(geom_type: str) -> dict:
    return {
        "geometry": geom_type,
        "properties": OrderedDict([
            ("uid", "str"),
            ("dataType", "str"),
            ("fname", "str"),
            ("path", "str"),
            ("native_crs", "int"),
            ("lastmod", "str")
        ])}


def _openkml(kml_path: str) -> str:
    """Reads KML text from file."""
    try:
        return Path(kml_path).read_text(encoding='utf-8')
    except Exception as e:
        logger.warning(f"Failed to read KML file {kml_path}: {e}")
        return ""


def _openkmz(kmz_path: str) -> str:
    """Unzips and reads the first KML file found in a KMZ archive."""
    try:
        with ZipFile(kmz_path, 'r') as archive:
            for name in archive.namelist():
                if name.lower().endswith('.kml'):
                    return archive.read(name).decode('utf-8')
    except Exception as e:
        logger.warning(f"Failed to extract KML from KMZ {kmz_path}: {e}")
    return ""


# Shared utility functions
def get_geometry(vector_path, minimum_bounding_geometry=False, layer=None):
    """
    Reads geometry from an object and computes either a bounding box (default)
    or a minimum bounding geometry (minimum_bounding_geometry=True).  Minimum
    bounding geometry attempts to return a convex hull with fallback to an
    envelope.

    Returns: (Shapely geometry, CRS as WKT string or dict)
    """
    try:
        with fiona.open(vector_path, layer=layer) if layer else fiona.open(vector_path) as src:
            crs = src.crs_wkt or src.crs
            geometries = [
                shape(feat["geometry"])
                for feat in src
                if feat.get("geometry") is not None
            ]

            if not geometries:
                return None, None

            combined = unary_union(geometries)

            if minimum_bounding_geometry:
                hull = combined.convex_hull
                if not isinstance(hull, Polygon):
                    geom = combined.envelope
                else:
                    geom = hull
            else:
                geom = combined.envelope
            epsg = PyCRS.from_user_input(crs).to_epsg() or 4326
            return geom, epsg
    except Exception as e:
        print(f"Error processing {vector_path}: {e}")
        return None, None
    

def write_features_by_scale(features: list[dict], output_gpkg_path: str) -> None:
    """
    Groups features by approximate spatial scale and writes them
    to corresponding layers in the output GeoPackage, level_00
    (global scale) to level_07 (hyper-local scale).
    """
    def classify_area_km2(area_km2: float) -> str:
        if area_km2 >= 175_000_000: return "level_00"
        elif area_km2 >= 35_000_000: return "level_01"
        elif area_km2 >= 5_000_000: return "level_02"
        elif area_km2 >= 1_000_000: return "level_03"
        elif area_km2 >= 500_000: return "level_04"
        elif area_km2 >= 100_000: return "level_05"
        elif area_km2 >= 50_000: return "level_06"
        return "level_07"

    layer_bins = {}

    for feat in features:
        try:
            geom = shape(feat["geometry"])
            geom_type = geom.geom_type
            native_crs = feat.get("native_crs", 4326)
            epsg_code = PyCRS.from_user_input(native_crs).to_epsg()

            geom = to_wgs84(native_epsg=epsg_code, geom_or_bounds=geom)

            # figure out target layer
            if geom_type in {"Polygon", "MultiPolygon"}:
                try:
                    area_km2 = area(geom.__geo_interface__) / 1_000_000
                    layer = classify_area_km2(area_km2)
                except Exception:
                    layer = "level_07"
            elif geom_type in {"Point", "MultiPoint"}:
                layer = "level_points"
            else:
                continue  # for invalid/unsupported geometry

            # bin the feature
            if layer not in layer_bins:
                layer_bins[layer] = {
                    "geometry": geom_type,
                    "features": []
                }

            layer_bins[layer]["features"].append({
                "geometry": geom.__geo_interface__,
                "properties": {
                    "uid": str(uuid.uuid4()),
                    "native_crs": epsg_code or 0
                }
            })
        except Exception as e:
            logger.debug(f"Failed to process feature for scaled layer: {e}")
            continue
    
    # Now write them all out
    for layer, data in layer_bins.items():
        try:
            geom_type = data["geometry"]
            schema = _get_standard_schema(geom_type=geom_type)

            with fiona_open(
                output_gpkg_path,
                "w" if not Path(output_gpkg_path).exists() else "a",
                driver="GPKG",
                schema=schema,
                crs=fiona_crs.from_epsg(4326),
                layer=layer
            ) as sink:
                sink.writerecords(data["features"])
        except Exception as e:
            logger.warning(f"Failed to write layer '{layer}' to {output_gpkg_path}: {e}")


def write_features_to_gpkg(
        features: List[dict],
        output_gpkg: str,
        layer_name: str = f"geoindexer_run{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    ):
    """
    Writes list of GeoJSON features to GeoPackage layer, automatically reprojecting
    features to EPSG:4326 while recording original CRS in a 'native_crs' property
    """
    if not features:
        raise ValueError("No features to write")
    
    # Bin things by geometric type
    lyr_types = {
        "Point": [],
        "Polygon": [],
        "MultiPolygon": []
    }
    transformer_cache = {}

    for feat in features:
        try:  # coerce to EPSG:4326 first
            geom = shape(feat["geometry"])
            geom_type = geom.geom_type
            native_crs = feat.get("native_crs", 4326)
            epsg_code = PyCRS.from_user_input(native_crs).to_epsg()

            geom = to_wgs84(native_epsg=epsg_code, geom_or_bounds=geom)
            
            props = feat["properties"]
            props["uid"] = str(uuid.uuid4())
            props["native_crs"] = epsg_code or 0  # Unknown projection
            feat["properties"] = props

            cleaned = {
                "geometry": geom.__geo_interface__,
                "properties": feat["properties"]
            }

            if geom_type in lyr_types:
                lyr_types[geom_type].append(cleaned)
        except Exception as e:
            logger.debug(f"Skipped feature due to error: {e}")
            continue  # Skip invalid geometry

    # Now write features out to their own appropriate GPKG layer
    for geom_type, feats in lyr_types.items():
        if not feats:
            continue

        lyr_suffix = geom_type.lower().replace("multi", "")
        lyr_name_out = f"{layer_name}_{lyr_suffix}"

        schema = _get_standard_schema(geom_type=geom_type)

        with fiona_open(
            output_gpkg,
            "w" if not Path(output_gpkg).exists() else "a",  # append after first write
            driver="GPKG",
            schema=schema,
            crs=fiona_crs.from_epsg(4326),
            layer=lyr_name_out
        ) as sink:
            sink.writerecords(feats)


def moddate(filepath: str) -> str:
    """Return the ISO 8601-formatted modification timestamp of a file."""
    try:
        lm = Path(filepath).stat().st_mtime
        return datetime.fromtimestamp(lm).strftime('%Y-%m-%dT%H:%M:%S')
    except Exception as e:
        logger.warning(f"Failed to get mod time for {filepath}: {e}")
        return ""


def to_wgs84(native_epsg, geom_or_bounds) -> Any:
    """
    Reprojects a Shapely geometry or bounding box to WGS84 (EPSG:4326).
    Returns Shapely geometry if input was geometry, or a tuple if
    input was extent/bounds.
    """
    try:
        if native_epsg == 4326:
            return geom_or_bounds
        
        if native_epsg not in _transformer_cache:
            _transformer_cache[native_epsg] = Transformer.from_crs(
                native_epsg, 4326, always_xy=True
            )
        transformer = _transformer_cache[native_epsg]

        if isinstance(geom_or_bounds, (tuple, list)):
            minx, miny = transformer.transform(geom_or_bounds[0], geom_or_bounds[1])
            maxx, maxy = transformer.transform(geom_or_bounds[2], geom_or_bounds[3])
            return minx, miny, maxx, maxy
        else:
            return transform(transformer.transform, geom_or_bounds)
        
    except Exception as e:
        logger.warning(f"Reprojection failed for EPSG:{native_epsg}: {e}")
        return geom_or_bounds  # Fallback to original bounds


def dms_to_dd(coords: str) -> tuple[float, float]:
    """Converts NITF-style DMS string to decimal degrees."""
    try:
        lat_d, lat_m, lat_s = int(coords[0:2]), int(coords[2:4]), int(coords[4:6])
        lat_dir = coords[6]
        lon_d, lon_m, lon_s = int(coords[7:10]), int(coords[10:12]), int(coords[12:14])
        lon_dir = coords[14]

        lat = lat_d + lat_m / 60 + lat_s / 3600
        lon = lon_d + lon_m / 60 + lon_s / 3600
        if lat_dir == 'S':
            lat = -lat
        if lon_dir == 'W':
            lon = -lon

        return lat, lon
    except Exception as e:
        logger.warning(f"Failed to convert DMS to decimal degrees: {e}")
        return 0.0, 0.0


def kmlextents(kmlfile: str) -> tuple | None:
    """Parses KML or KMZ file and extracts bounding box from coordinates."""
    data = ""
    if kmlfile.lower().endswith(".kmz"):
        data = _openkmz(kmlfile)
    elif kmlfile.lower().endswith(".kml"):
        data = _openkml(kmlfile)

    if not data:
        return None

    # Flatten XML text for regex parsing
    data = data.replace('\n', '').replace('\r', '').replace('\t', '')

    xf, yf = [], []

    try:
        xs = re.findall(r"<longitude>(.+?)</longitude>", data)
        ys = re.findall(r"<latitude>(.+?)</latitude>", data)

        if xs and ys:
            xf = list(map(float, xs))
            yf = list(map(float, ys))
        else:
            coords = re.findall(r"<coordinates>(.+?)</coordinates>", data)
            for coord in coords:
                for pair in coord.strip().split():
                    try:
                        lon, lat, *_ = map(float, pair.strip().split(","))
                        xf.append(lon)
                        yf.append(lat)
                    except ValueError:
                        continue
    except Exception as e:
        logger.warning(f"Failed to extract KML extents: {e}")

    if xf and yf:
        return min(xf), min(yf), max(xf), max(yf)
    return None

    
def get_geojson_record(
    geom,
    datatype: str,
    fname: str,
    path: str,
    nativecrs: int,
    lastmod: str,
    img_popup: str = None
) -> dict:
    """Builds a standard GeoJSON feature record with optional image preview link."""
    props = OrderedDict([
        ("dataType", datatype),
        ("fname", fname),
        ("path", f"file:///{path}"),
        ("native_crs", nativecrs),
        ("lastmod", lastmod)
    ])
    if img_popup:
        props["img_popup"] = f"file:///{img_popup}"

    return {
        "type": "Feature",
        "geometry": mapping(geom),
        "properties": props
    }
