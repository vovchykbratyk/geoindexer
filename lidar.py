import json
import os
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

    def run_pdal(self):
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
        schema = {'geometry': 'Polygon',
                  'properties': {
                      'id': 'int',
                      'fname': 'str',
                      'path': 'str'
                  }}

        path, fname = os.path.split(self.lidar_file)

        stats = LidarQ.run_pdal(self)

        try:
            # Read metadata
            md = stats['metadata']
            minx, miny = md['minx'], md['miny']
            maxx, maxy = md['maxx'], md['maxy']
            cmpd_crs = json.loads(
                CRS.to_json(
                    CRS.from_wkt(md['comp_spatialreference'])
                )
            )

            # Sift out only the horizontal CRS for drawing projected extent footprint
            xy_crs = CRS.from_epsg(cmpd_crs['components'][0]['id']['code']).to_string()

            # Create the geometry
            boundary = Polygon([
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy]
            ])

            feat = {'geometry': mapping(boundary),
                    'properties': {
                        'id': oid,
                        'fname': fname,
                        'path': path
                    }}

            return {'schema': schema,
                    'crs': xy_crs,
                    'feature': feat}

        except ValueError:
            raise ValueError
