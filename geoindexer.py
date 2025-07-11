"""
geoindexer.py

Original author: Eric Eagle
Initial creation: 2020

This script indexes geospatial and location-aware datasets across local or networked
storage, extracting spatial metadata for storage in GeoJSON or GeoPackage.

The current version includes significant performance, maintainability, and robustness
improvements implemented with the assistance of OpenAI GPT-4o LLM, used interactively
to review, modernize, and optimize the codebase.

Key improvements include:
- Modular and testable handler classes for each supported file type
- Centralized utility functions for CRS conversion, file handling, and parsing
- Consistent error handling and logging
- Reduced computational overhead for large-scale network storage crawling

This script is designed for large-volume indexing tasks in GIS workflows,
with an emphasis on speed and resilience across large and diverse geospatial
data.
"""

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import os
import sys
import json
import logging

from tqdm import tqdm
import fiona
from fiona.crs import CRS

# Import refactored handlers
from handlers import Container, Exif, Lidar, Raster, Shapefile, Log

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Utility function for current DTG
def now(iso8601: bool = True) -> str:
    fmt = "%Y-%m-%dT%H:%M:%S" if iso8601 else "%Y%m%dT%H%M%S"
    return datetime.now().strftime(fmt)


# filetype handler registry
PROCESSOR_MAP: Dict[str, Any] = {
    "gdb": Container,
    "gpkg": Container,
    "db": Container,
    "sqlite": Container,
    "jpg": Exif,
    "jpeg": Exif,
    "laz": Lidar,
    "las": Lidar,
    "tif": Raster,
    "tiff": Raster,
    "ntf": Raster,
    "nitf": Raster,
    "dt0": Raster,
    "dt1": Raster,
    "dt2": Raster,
    "shp": Shapefile,
}

import concurrent.futures

class GeoCrawler:
    def __init__(self, path: str, types: List[str]):
        self.path = Path(path)
        self.types = set(t.lower() for t in types)  # faster lookup

    def get_file_list(self, recursive: bool = True) -> List[str]:
        """Returns list of files matching extensions (case-insensitive)."""
        if not recursive:
            return [
                str(p.resolve())
                for p in self.path.iterdir()
                if p.is_file() and p.suffix[1:].lower() in self.types
            ]
        return self._crawl_parallel()

    def _crawl_parallel(self, max_workers: int = os.cpu_count() or 4) -> List[str]:
        matches = []

        def crawl_dir(path: Path) -> List[str]:
            files = []
            try:
                for entry in os.scandir(path):
                    if entry.is_file():
                        ext = Path(entry.name).suffix[1:].lower()
                        if ext in self.types:
                            files.append(str(Path(entry.path).resolve()))
                    elif entry.is_dir(follow_symlinks=False):
                        subdir = Path(entry.path)
                        files.extend(crawl_dir(subdir))  # serial for now
            except (PermissionError, FileNotFoundError):
                pass
            return files

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(crawl_dir, self.path)]
            for f in concurrent.futures.as_completed(futures):
                try:
                    matches.extend(f.result())
                except Exception as e:
                    logger.warning(f"Directory crawl failed: {e}")

        return matches


class GeoIndexer:
    def __init__(self, file_list: List[str]):
        self.file_list = file_list
        self.errors: List[str] = []
        self.failures = {
            "files": [],
            "layers": []
        }

    @staticmethod
    def get_extension(filepath: str) -> Optional[str]:
        return Path(filepath).suffix.lower()[1:] if filepath else None

    def get_layer_num(self, filepath: str) -> int:
        """Returns number of layers in a container, or 1 for non-container files."""
        ext = self.get_extension(filepath)
        if ext in {"gdb", "gpkg", "db", "sqlite"}:
            try:
                return len(fiona.listlayers(filepath))
            except Exception as e:
                self.errors.append(f"{now()} - {e} - [{filepath}]")
                return 0
        return 1

    @staticmethod
    def geojson_container() -> dict:
        return {
            "type": "FeatureCollection",
            "features": []
        }

    @staticmethod
    def get_schema(img_popup: bool = False) -> dict:
        if img_popup:
            return {
                "geometry": "Point",
                "properties": OrderedDict([
                    ("dataType", "str"),
                    ("fname", "str"),
                    ("path", "str"),
                    ("img_popup", "str"),
                    ("native_crs", "int"),
                    ("lastmod", "str")
                ])
            }
        return {
            "geometry": "Polygon",
            "properties": OrderedDict([
                ("path", "str"),
                ("lastmod", "str"),
                ("fname", "str"),
                ("dataType", "str"),
                ("native_crs", "int")
            ])
        }
    
    def _process_file(
        self,
        filepath: str,
        polygons: List[dict],
        points: List[dict],
        stats: dict
    ) -> None:
        ext = self.get_extension(filepath)
        processor_cls = PROCESSOR_MAP.get(ext)

        if not processor_cls:
            return

        try:
            result = processor_cls(filepath).get_props()

            if not result:
                raise ValueError("Processor returned None")

            if isinstance(result, dict) and result.get("geometry", {}).get("type") == "Point":
                points.append(result)
            else:
                if ext in {"gdb", "gpkg", "db", "sqlite"} and "feats" in result:
                    polygons.extend(result["feats"])
                    stats["container_layers"] += len(result["feats"])
                    if result.get("errors"):
                        self.errors.extend(result["errors"])
                        self.failures["layers"].extend(result.get("failed_layers", []))
                else:
                    polygons.append(result)
                    stats[self._stat_key(ext)] += 1

        except Exception as e:
            self.errors.append(f"{now()} - {e} - [{filepath}]")
            self.failures["files"].append(filepath)

    @staticmethod
    def _stat_key(ext: str) -> str:
        return {
            "jpg": "web_images",
            "jpeg": "web_images",
            "laz": "lidar_point_clouds",
            "las": "lidar_point_clouds",
            "tif": "rasters",
            "tiff": "rasters",
            "ntf": "rasters",
            "nitf": "rasters",
            "dt0": "rasters",
            "dt1": "rasters",
            "dt2": "rasters",
            "shp": "shapefiles"
        }.get(ext, "unknown")
    
    def get_extents(self, logging: Optional[str] = None):
        if not self.file_list:
            logger.warning("No files to process.")
            return None

        # Estimate total datasets (includes container sublayers)
        total_datasets = sum(self.get_layer_num(f) for f in self.file_list)

        # Setup
        polygons, points = [], []
        extents = self.geojson_container()
        stats = {
            "container_layers": 0,
            "web_images": 0,
            "lidar_point_clouds": 0,
            "rasters": 0,
            "shapefiles": 0
        }

        for f in tqdm(self.file_list, desc="GeoIndexer progress", dynamic_ncols=True):
            self._process_file(f, polygons, points, stats)

        extents["features"].extend(polygons + points)

        stats["total_processed"] = sum(stats.values())
        stats["total_datasets"] = total_datasets
        stats["success_rate"] = round(
            (stats["total_processed"] / total_datasets * 100.0), 2
        ) if total_datasets else 0.0

        if logging:
            log = Log(self.errors)
            logname = log.to_file(logging)
            stats["logfile"] = f"file:///{Path(logging, logname).as_posix()}"

        return extents, stats, self.failures
    
    @staticmethod
    def to_geopackage(features: dict, output_path: str, scoped: bool = True) -> bool:
        """
        Writes features to a GeoPackage file, split into size-based layers if scoped is True.
        """
        def layer_name_for_area(km2: float) -> str:
            if km2 >= 175_000_000: return "level_00"
            elif km2 >= 35_000_000: return "level_01"
            elif km2 >= 5_000_000: return "level_02"
            elif km2 >= 1_000_000: return "level_03"
            elif km2 >= 500_000: return "level_04"
            elif km2 >= 100_000: return "level_05"
            elif km2 >= 50_000: return "level_06"
            return "level_07"

        driver = "GPKG"

        if scoped:
            layers = {f"level_0{i}": GeoIndexer.geojson_container() for i in range(7)}
            for feat in features["features"]:
                try:
                    from area import area
                    area_km2 = area(feat["geometry"]) / 1_000_000
                    layer = layer_name_for_area(area_km2)
                    layers[layer]["features"].append(feat)
                except Exception:
                    continue

            for layer, collection in layers.items():
                if collection["features"]:
                    with fiona.open(
                        output_path, 'w',
                        schema=GeoIndexer.get_schema(),
                        driver=driver,
                        crs=CRS.from_epsg(4326),
                        layer=layer
                    ) as out:
                        out.writerecords(collection["features"])
            return True

        else:
            layer_name = f"coverages_{now(False)}"
            with fiona.open(
                output_path, 'w',
                schema=GeoIndexer.get_schema(),
                driver=driver,
                crs=CRS.from_epsg(4326),
                layer=layer_name
            ) as out:
                out.writerecords(features["features"])
            return True
        
    @staticmethod
    def to_geojson(features: dict, output_path: str) -> bool:
        """
        Writes the entire FeatureCollection to a single GeoJSON file.
        """
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(features, f, indent=2)
            return True
        except Exception as e:
            logger.warning(f"Failed to write GeoJSON to {output_path}: {e}")
            return False
