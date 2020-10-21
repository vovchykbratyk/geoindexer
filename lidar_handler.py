from fiona.crs import from_epsg
import json
import os
from shapely.geometry import mapping, Polygon
import subprocess
import sys


class LidarQ:

    def __init__(self, lidar_files):
        self.lidar_files = lidar_files

    def run_pdal(self):
        print(self.lidar_files)
        results = {}
        print("Running PDAL")
        for f in self.lidar_files:
            r = (subprocess.run(['pdal', 'info', f],
                                stderr=subprocess.PIPE,
                                stdout=subprocess.PIPE))
            print(r)
            results[f] = json.loads(r.stdout.decode())
        return results
        # return json.loads(results.stdout.decode())

    def get_props(self):
        i = 0
        feats = []

        boundary = None
        crs = None
        fname = None
        path = None
        props = None
        schema = {'geometry': 'Polygon',
                  'properties': {
                      'id': 'int',
                      'fname': 'str',
                      'path': 'str'
                  }}

        stats = LidarQ.run_pdal(self)  # generate list of json objects
        for file, stat in stats.items():
            epsg_stats = stat['stats']['bbox']
            if stat['filename']:
                path, fname = os.path.split(stat['filename'])
            for k, v in epsg_stats.items():
                if k.startswith('EPSG'):
                    crs = from_epsg(k.split(':')[1])
                    try:
                        bcube = epsg_stats[k]['bbox']
                        boundary = Polygon([
                            [bcube['minx'], bcube['miny']],
                            [bcube['maxx'], bcube['miny']],
                            [bcube['maxx'], bcube['maxy']],
                            [bcube['minx'], bcube['maxy']]
                        ])
                    except ValueError as ve:
                        sys.exit(f"Failed to get key: {ve}")
                props = {'geometry': mapping(boundary),
                         'properties': {'id': i,
                                        'fname': fname,
                                        'path': path}}
                i += 1
            feat = {'schema': schema,
                    'props': props,
                    'crs': crs}
            feats.append(feat)
            return feats


fl = [
    '/home/eric/Data/lidar/UFO_ALIRT_PC_20200727_1348_11.las',
    '/home/eric/Data/lidar/UFO_ALIRT_PC_20200727_1348_12.las',
    '/home/eric/Data/lidar/UFO_BuckEye_PC_20200727_1033_2.laz',
    '/home/eric/Data/lidar/USGS_LPC_IL_4County_Cook_2017_LAS_15008550_LAS_2019.las'
]

lidar = LidarQ(fl)

lidar_stats = lidar.get_props()
print(lidar_stats)
