"""
This script was pulled from the "area" python port of Mapbox's geojson-area
module and credited to GitHub users Alireza & Chip Warden
(https://github.com/scisco/area).

Minor updates 2025-07-14 to avoid vulnerabilities in the original code.
"""

from __future__ import division
import json
from math import pi, sin

WGS84_RADIUS = 6378137


def rad(value):
    return value * pi / 180


def _ring_area(coordinates):
    """
    Calculate the approximate _area of the polygon where it
        is projected onto the earth. Note that this _area will be
        positive if the ring is oriented clockwise; otherwise it
        will be negative.

    Reference:
        Robert G. Chamberlain and William H. Duquette, "Some Algorithms
        for Polygons on a Sphere", JPL Publication 07-03, Jet Propulsion
        Laboratory, Pasadena, CA; June 2007
        http://trs-new.jpl.nasa.gov/dspace/handle/2014/40409

    @Returns

    {float} The approximate signed geodesic _area of the polygon in square metres.
    """
    if not isinstance(coordinates, (list, tuple)):
        raise TypeError("Coordinates must be a list or tuple")
    
    _area = 0
    n = len(coordinates)

    if n > 2:
        for i in range(n):
            p1 = coordinates[i - 1]
            p2 = coordinates[i]
            p3 = coordinates[(i + 1) % n]

            lon1 = rad(p1[0])
            lon3 = rad(p3[0])
            lat2 = rad(p2[1])

            _area += (lon3 - lon1) * sin(lat2)
        _area = _area * (WGS84_RADIUS ** 2) / 2

    return _area


def polygon_area(coordinates):

    assert isinstance(coordinates, (list, tuple))

    _area = 0
    if len(coordinates) > 0:
        _area += abs(_ring_area(coordinates[0]))

        for i in range(1, len(coordinates)):
            _area -= abs(_ring_area(coordinates[i]))

    return _area


def area(geometry):
    if isinstance(geometry, str):
        geometry = json.loads(geometry)

    assert isinstance(geometry, dict)

    _area = 0

    if geometry['type'] == 'Polygon':
        return polygon_area(geometry['coordinates'])
    elif geometry['type'] == 'MultiPolygon':
        for i in range(0, len(geometry['coordinates'])):
            _area += polygon_area(geometry['coordinates'][i])

    elif geometry['type'] == 'GeometryCollection':
        for i in range(0, len(geometry['geometries'])):
            _area += area(geometry['geometries'][i])

    return _area


def polygon_area(rings):
    """
    Calculate the area of a polygon defined by its rings.

    :param rings: A list of rings, where each ring is a list of coordinates.
    :return: The area of the polygon in square meters.
    """
    if not isinstance(rings, (list, tuple)):
        raise TypeError("Polygon must be a list or tuple of rings.")

    _area = abs(_ring_area(rings[0]))
    for hole in rings[1:]:
        _area -= abs(_ring_area(hole))
    return _area


def area(geometry):
    """
    Computes total area of a GeoJSON Polygon, MultiPolygon or GeometryCollection.

    Args:
        geometry (dict or str):  A GeoJSON geometry object or JSON string.

    Returns:
        float: Area in square metres.
    """
    if isinstance(geometry, str):
        geometry = json.loads(geometry)

    if not isinstance(geometry, dict) or 'type' not in geometry:
        raise ValueError("Invalid GeoJSON geometry.")
    
    _area = 0
    gtype = geometry['type']

    if gtype == 'Polygon':
        return polygon_area(geometry['coordinates'])
    elif gtype == 'MultiPolygon':
        for polygon in geometry['coordinates']:
            _area += polygon_area(polygon)
    elif gtype == 'GeometryCollection':
        for geom in geometry.get('geometries', []):
            _area += area(geom)

    return _area