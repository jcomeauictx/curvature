#!/usr/bin/python
'''
calculate and display panorama of horizon from given point and bearing

various views can be generated based on flat-earth, concave-earth, and
convex-earth (normal) theories.
'''
import sys, os, math, hgtread
from ast import literal_eval as eval  # safe alternative to eval
from hgtread import logging, look, get_height, SAMPLE_SECONDS
from earthcurvature import earthcurvature, R, KM, GLOBE_EARTH_RADIUS
from PIL import Image
logging.basicConfig(level=logging.DEBUG if __debug__ else logging.INFO)
if R not in [float('-inf'), 0.0, float('inf')]:
    RADIUS = abs(R) * KM * 1000  # mean radius of earth in meters
else:  # equirectangular assumes distances same as that of the equator
    RADIUS = GLOBE_EARTH_RADIUS * KM * 1000
DEGREE_IN_METERS = (RADIUS * 2 * math.pi) / 360.0
SAMPLE_IN_METERS = DEGREE_IN_METERS / (60 * (60 / SAMPLE_SECONDS))
SPAN = float(os.getenv('SPAN', '60.0'))
WHITE = OPAQUE = COMPLETELY = 255
GRAYEST = 10
BLACK = NONE = 0
BLACKPIXEL = (BLACK, BLACK, BLACK, OPAQUE)
BLUEPIXEL = (NONE, NONE, COMPLETELY, OPAQUE)
logging.debug('RADIUS: %s, DEGREE_IN_METERS: %s', RADIUS, DEGREE_IN_METERS)

def distance(lat1, lon1, lat2, lon2):
    '''
    as-the-bullet-flies distance in meters between two points

    using Pythagorean theorem on equirectangular projection as
    shown on http://www.movable-type.co.uk/scripts/latlong.html

    not using Haversine because we're judging how things would *look*
    from a fixed point. we're not actually going overland to it.

    >>> distance(37, 116, 37, 117)
    88809.47272660509
    '''
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    x = (lon2 - lon1) * math.cos((lat1 + lat2) / 2)
    y = (lat2 - lat1)
    d = math.sqrt((x * x) + (y * y)) * RADIUS
    return d

def move(latitude, longitude, bearing, distance):
    '''
    resulting latitude and longitude from as-the-bullet-flies move

    from http://gis.stackexchange.com/a/30037/1291
    '''
    bearing = math.radians(bearing)
    distance_x = math.sin(bearing) * distance
    distance_y = math.cos(radians) * distance
    degrees_y = distance_y / DEGREE_IN_METERS
    average_latitude = latitude + (degrees_y / 2)
    degrees_x = (distance_x * math.cos(average_latitude)) / DEGREE_IN_METERS

def panorama(bearing, latitude, longitude, distance=500, height=1.8, span=SPAN):
    '''
    display view of horizon from a point at given bearing

    height is meters from ground to eye level.
    maximum distance in km can be shorter to speed processing.
    bearing is counterclockwise angle starting at due east.
    span is the number of degrees to view.

    pixel height is determined by angle of elevation as seen from viewer's
    position, which varies inversely with distance. pixels represent a uniform
    distance at `distance`, so the determined angle should be divided by
    delta(bearing) (`d_bearing`) to get pixels in height.
    '''
    step = SAMPLE_IN_METERS  # meters to "move" while tracing out horizon
    logging.info('radius: %s, step: %s', RADIUS, SAMPLE_IN_METERS)
    # FIXME: this should be passed to `look` function for delta distance
    viewrange = distance * 1000  # km to meters
    height += get_height(latitude, longitude)
    logging.info('initial height: %s', height)
    bearing = math.radians(bearing)
    halfspan = math.radians(span) / 2
    d_bearing = math.asin(float(step) / viewrange)
    logging.info('delta angle: %s (%s)', d_bearing, math.degrees(d_bearing))
    angle = bearing + halfspan
    logging.info('initial angle: %s', math.degrees(angle))
    logging.info('final angle: %s', math.degrees(bearing - halfspan))
    elevations, points = [], []
    while angle > bearing - halfspan:
        elevations.append(look(
            math.degrees(angle), latitude, longitude, distance))
        angle -= d_bearing
        logging.info('heights=%s, angle=%s', elevations, math.degrees(angle))
        points.append([])
        for index in range(1, len(elevations[-1])):
            # apparent elevation is reduced by eye height above sea level
            elevation = elevations[-1][index] - height
            # now factor in curvature
            elevation -= earthcurvature(step * index, 'm', 'm')[1][2]
            theta = math.atan(elevation / (step * index))
            # now convert radians to projected pixels
            projected = int(round(theta / abs(d_bearing)))
            points[-1].append(projected)
    logging.debug('points: %s', map(max, points))
    width, height = len(points), 360
    logging.info('width of image: %d', width)
    horizon = int(height / 2)
    # initialize to sky blue
    panorama = Image.new('RGBA', (width, height), (128, 128, 255, 255))
    # make lower half sea blue
    for x in range(width):
        for y in range(horizon, height):
            panorama.putpixel((x, y), BLUEPIXEL)
    #panorama.show()
    for index in range(width):
        x = index
        # adding a previous level of `height` will ensure a ridge line
        # gets drawn on the most distant plot
        heights, pointlist = elevations[index], points[index] + [height]
        logging.debug('heights: %s, pointlist: %s', heights, pointlist)
        for depth in range(len(pointlist) - 2, -1, -1):
            # farthest away will be shown lightest
            gray = int(max(GRAYEST, min(WHITE, WHITE - (depth / 50))))
            point, previous = pointlist[depth], pointlist[depth + 1]
            # remember that (0, 0) is top left of PIL.Image
            level = horizon - 1 - point
            if level > horizon - 1:  # meaning *below* horizon in plot
                logging.debug('skipping below-horizon point %f (%d, %d)',
                             point, x, level)
                continue
            y = max(0, level)
            # mark the top of every ridge
            if (point > previous):
                logging.info('marking top of ridge at (%s, %s)', x, y)
                panorama.putpixel((x, y), BLACKPIXEL)
            elif point < previous or panorama.getpixel((x, y)) != BLACKPIXEL:
                panorama.putpixel((x, y), (gray, gray, gray, OPAQUE))
            logging.debug('panorama.putpixel((%s, %s), %s)', x, y, gray)
            for plot in range(y + 1, horizon):
                panorama.putpixel((x, plot), (gray, gray, gray, OPAQUE))
    panorama.show()

if __name__ == '__main__':
    args = sys.argv[1:]
    if args:
        panorama(*args)
    else:
        import doctest
        doctest.testmod()
