from setuptools import setup, find_packages

setup(
    name="geoindexer",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fiona",
        "rasterio",
        "shapely",
        "pyproj",
        "gdal",
        "tqdm",
        "exifread",
        "pillow",
        "numpy"
    ],
    extras_require={
        "full": ["pdal"]
    },
    entry_points={
        'console_scripts': [
            'geoindexer=geoindexer.geoindexer:main',
        ],
    },
    author="Eric Eagle",
    description="A tool to locate and index geospatial data files.",
    license="AGPL-3.0"
)