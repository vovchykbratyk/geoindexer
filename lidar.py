import json
import os
import pyproj
from pyproj import CRS
from shapely.geometry import mapping, Polygon
import subprocess as sp


class LidarQ:

    def __init__(self, lidar_file):
        """
        Constructor.  Requires input lidar file (*.las, *.laz).

        :param lidar_file: Input Lidar dataset
        :type lidar_file: str
        """
        self.lidar_file = lidar_file

    def _run_pdal(self):
        """
        Invokes PDAL and pipes output back to python as json.

        :return: dict
        """
        r = (sp.run(['pdal', 'info', self.lidar_file, '--metadata'],
                    stderr=sp.PIPE,
                    stdout=sp.PIPE))

        return json.loads(r.stdout.decode())

    def get_props(self, oid):
        """
        Parses the PDAL-obtained metadata and returns a schema and geojson object to be
        passed for writing.

        :param oid: index number
        :type oid: int

        :return: dict
        """

        # local parameters
        path, fname = os.path.split(self.lidar_file)
        stats = LidarQ._run_pdal(self)

        try:
            # Read metadata
            md = stats['metadata']

            # Get native CRS and project to WGS84
            cmpd_crs = json.loads(
                CRS.to_json(
                    CRS.from_wkt(md['comp_spatialreference'])
                )
            )
            native_crs = cmpd_crs['components'][0]['id']['code']
            proj = pyproj.Transformer.from_crs(native_crs, 4326, always_xy=True)

            minx, miny = proj.transform(md['minx'], md['miny'])
            maxx, maxy = proj.transform(md['maxx'], md['maxy'])

            # Create the geometry
            boundary = Polygon([
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy]
            ])

            return {'type': 'Feature',
                    'geometry': mapping(boundary),
                    'properties': OrderedDict([
                        ('id', oid),
                        ('dataType', 'Lidar'),
                        ('fname', fname),
                        ('path', path),
                        ('native_crs', cmpd_crs['components'][0]['id']['code'])
                    ])}

        except ValueError:
            raise ValueError


## test
#laz_file_a = "C:/Data/USGS_LPC_IL_4County_Cook_2017_LAS_15008550_LAS_2019.laz"
#laz_file_b = "C:/Data/UFO_BuckEye_PC_20200727.1033_2.laz"

#lfile_info = LidarQ(laz_file_b).get_props(0)
#print(lfile_info)
