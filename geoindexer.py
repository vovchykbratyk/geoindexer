"""
geoindexer.py

Original author: Eric Eagle
Initial creation: 2020

This script indexes geospatial and location-aware datasets across local or networked
storage, extracting spatial metadata for storage in GeoJSON or GeoPackage.
"""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import os
import logging

from tqdm import tqdm

# Import refactored handlers
from handlers import (
    Container,
    Exif, 
    Lidar, 
    Raster, 
    Shapefile
)

from wrenches import (
    write_features_by_scale,
    write_features_to_gpkg
)

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Helper function for current DTG
def now() -> str:
    return datetime.now().strftime('%Y%m%dT%H%M%S')


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
        self.files = self.get_file_list(self.path)

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
                        files.extend(crawl_dir(Path(entry.path)))  # still recursive here
            except (PermissionError, FileNotFoundError) as e:
                logger.debug(f"Skipped directory {path} due to error: {e}")
            return files

        try:
            # Collect matches in the top-level directory
            for entry in os.scandir(self.path):
                if entry.is_file():
                    ext = Path(entry.name).suffix[1:].lower()
                    if ext in self.types:
                        matches.append(str(Path(entry.path).resolve()))
        except Exception as e:
            logger.warning(f"Failed to scan root directory {self.path}: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all top-level subdirectories for crawling
            futures = [
                executor.submit(crawl_dir, Path(entry.path))
                for entry in os.scandir(self.path)
                if entry.is_dir(follow_symlinks=False)
            ]

            for f in concurrent.futures.as_completed(futures):
                try:
                    matches.extend(f.result())
                except Exception as e:
                    logger.warning(f"Directory crawl failed: {e}")

        return matches


class GeoIndexer:
    def __init__(
        self, input_dir: str,
        output_gpkg: str,
        convex_hull: bool = False,
        scaled_output: bool = False
    ):
        self.input_dir = Path(input_dir)
        self.matches = None
        self.output_gpkg = Path(output_gpkg)
        self.convex_hull = convex_hull
        self.scaled_output = scaled_output
        self.accumulated_features = []

    def index(self):
        """
        Kicks off GeoCrawler, iterates through matches, processing coverages as
        either simple extents (default) or convex hulls (optional) for each file
        (shapefile, raster) or layer (feature class, db table).

        Writes results to an output GeoPackage as a single layer (default) or
        broken into a number of scaled layers (00 - 07)
        """
        self.matches = GeoCrawler(self.input_dir, list(PROCESSOR_MAP.keys())).files
        for i in self.matches:
            ext = Path(i).suffix.lower()[1:]
            processor_cls = PROCESSOR_MAP.get(ext)

            if not processor_cls:
                continue

            try:
                if processor_cls is Shapefile:
                    handler = processor_cls(i)
                    props = handler.get_props()
                    if props and "geometry" in props:
                        self.accumulated_features.append(props)

                elif processor_cls is Container:
                    handler = processor_cls(i, convex_hull=self.convex_hull)
                    results = handler.get_props()
                    if results and "feats" in results:
                        for feature in results["feats"]:
                            if "geometry" in feature:
                                self.accumulated_features.append(feature)

                elif processor_cls is Raster:
                    handler = processor_cls(i)
                    props = handler.get_props()
                    if props and "geometry" in props:
                        if "native_crs" not in props:
                            props["native_crs"] = 4326
                        self.accumulated_features.append(props)

                else:
                    # All other types (Exif, Lidar, other potential types) return single GeoJSON-like records
                    handler = processor_cls(i)
                    props = handler.get_props()
                    if props and "geometry" in props:
                        self.accumulated_features.append(props)

            except Exception as e:
                logger.warning(f"Failed to process {i}: {e}")
                print("Error processing file:", i, "Error:", e)

        if self.accumulated_features:
            if self.scaled_output:
                write_features_by_scale(
                    features=self.accumulated_features,
                    output_gpkg_path=str(self.output_gpkg)
                )
            else:
                write_features_to_gpkg(
                    features=self.accumulated_features,
                    output_gpkg=str(self.output_gpkg)
                )


if __name__ == "__main__":

    def testrunner(input_path, output_path):
        outname = f"geoindexer_run_{now()}.gpkg"
        output_gpkg = Path(output_path) / outname
        gi = GeoIndexer(input_path, output_gpkg, convex_hull=True)
        print('*' * 120)
        print('START GEOINDEXING...')
        print('*' * 120)
        return gi.index()
        