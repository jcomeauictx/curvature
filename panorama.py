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
DARKEST = 10
BLACK = NONE = 0
BLACKPIXEL = (BLACK, BLACK, BLACK, OPAQUE)
WHITEPIXEL = (WHITE, WHITE, WHITE, OPAQUE)
BLUEPIXEL = (NONE, NONE, COMPLETELY, OPAQUE)
OCEANFRONT = bool(os.getenv('OCEANFRONT'))
CAMERA_HEIGHT = float(os.getenv('CAMERA_HEIGHT', '1.538'))
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

def panorama(bearing, latitude, longitude, distance=500,
             height=CAMERA_HEIGHT, span=SPAN):
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
    # elevations will be expressed in 3 ways:
    # 0. actual elevation above sea level;
    # 1. 'y' pixel coordinate after correcting for curvature and perspective
    # 2. 'y' as mapped to PIL.Image coordinates
    (closer, current, farther) = (raw, y_cartesian, y_image) = (0, 1, 2)
    elevations = []
    image_height = 360
    horizon = int(image_height / 2)
    # initializers for bad pixels:
    nearest = [0, -horizon, image_height - 1]
    farthest = [0, 0, horizon - 1]
    while angle > bearing - halfspan:
        elevations.append([[e] + nearest[y_cartesian:] for e in look(
            math.degrees(angle), latitude, longitude, distance)])
        correct_for_no_data(elevations[-1], raw, farthest)
        for index in range(1, len(elevations[-1])):
            elevation = elevations[-1][index][raw]
            # factor in curvature
            elevation -= earthcurvature(step * index, 'm', 'm')[1][2]
            # apparent elevation is reduced by eye height above sea level
            elevation -= height
            theta = math.atan(elevation / (step * index))
            # now convert radians to projected pixels
            projected = int(round(theta / abs(d_bearing)))
            elevations[-1][index][y_cartesian] = projected
            elevations[-1][index][y_image] = horizon - 1 - projected
        logging.debug('angle: %s, elevations: %s', angle, elevations[-1])
        angle -= d_bearing
    width = len(elevations)
    logging.info('width of image: %d', width)
    # initialize to sky blue
    panorama = Image.new('RGBA', (width, image_height), (128, 128, 255, 255))
    if OCEANFRONT:
        # make lower half sea blue
        for x in range(width):
            for y in range(horizon, image_height):
                panorama.putpixel((x, y), BLUEPIXEL)
    for index in range(width):
        x = index
        # adding a previous level of `image_height` will ensure a ridge line
        # gets drawn on the most distant plot
        # adding the spot on which the observer is standing will allow
        # checking the arc of view of each point
        pointlist = elevations[index]
        pointlist = [pointlist[0]] + pointlist + [[None, None, image_height]]
        logging.debug('pointlist: %s', pointlist)
        color = WHITEPIXEL
        for depth in range(len(pointlist) - 2, 0, -1):
            context = pointlist[depth - 1:depth + 2]
            logging.debug('context: %s', context)
            if context[current][y_image] == context[closer][y_image]:
                # carry forward the previous "farther" value
                logging.debug('carrying over previous value at depth %d', depth)
                pointlist[depth] = pointlist[depth + 1]
            elif context[current][y_cartesian] > context[closer][y_cartesian]:
                if OCEANFRONT and context[current][raw] == 0:
                    logging.debug('ocean at depth %d', depth)
                    ridgecolor = color = BLUEPIXEL
                else:
                    # farthest away will be shown lightest
                    # map depth values from DARKEST to WHITE
                    divider = len(pointlist) / float(WHITE - DARKEST)
                    gray = int(depth / divider) + DARKEST
                    color = (gray, gray, gray, OPAQUE)
                    ridgecolor = BLACKPIXEL
                    logging.debug('color at depth %d is %s', depth, color)
                # remember that (0, 0) is top left of PIL.Image
                y = max(0, context[current][y_image])
                # mark the top of every ridge
                if y < context[farther][y_image]:
                    logging.debug('marking top of ridge at (%s, %s)', x, y)
                    putpixel(panorama, (x, y), ridgecolor)
                # don't overwrite black pixel from previous ridgeline
                elif (y > context[farther][y_image] or
                        getpixel(panorama, (x, y)) != ridgecolor):
                    logging.debug('not top of ridge at (%s, %s)', x, y)
                    putpixel(panorama, (x, y), color)
                logging.debug('painting %s from %d to %d',
                              color, y + 1, context[closer][y_image])
                for plot in range(y + 1, context[closer][y_image]):
                    putpixel(panorama, (x, plot), color)
    panorama.show()

def putpixel(image, point, color):
    '''
    plot a pixel on the image, ignoring anything outside image range
    '''
    try:
        image.putpixel(point, color)
    except IndexError:
        pass

def getpixel(image, point):
    '''
    get a pixel from the image, ignoring anything outside image range
    '''
    try:
        return image.getpixel(point)
    except IndexError:
        return None

def correct_for_no_data(elevations, raw, farthest):
    '''
    for any "no data" (-32768) points in the list, average known elevations

    modifies list "in place"

    >>> test = [[13], [-32768], [-32768]]
    >>> correct_for_no_data(test, 0, [0])
    >>> test
    [[13], [9], [4]]
    >>> test = [[13], [-32768], [-32768], [-32768], [26]]
    >>> correct_for_no_data(test, 0, [0])
    >>> test
    [[13], [16], [20], [23], [26]]
    '''
    last_known = farthest[raw]
    state, count, increment = 'scanning', 0, 0
    for index in range(len(elevations) - 1, -1, -1):
        elevation = elevations[index][raw]
        logging.debug('state: %s, count: %d', state, count)
        if elevation == -32768:  # no data for this point
            logging.debug('found "no data" point at index %d', index)
            if state == 'scanning':
                state = 'counting'
                count = 1
            else:
                count += 1
        else:
            logging.debug('found valid data at index %d', index)
            if state == 'scanning':
                last_known = elevation
            else:
                increment = float(last_known - elevation) / (count + 1)
                logging.debug('correcting with increment %.2f', increment)
                for i in range(count + 1):
                    elevations[index + i][raw] = int(round(
                        elevation + (i * increment))
                    )
                    logging.debug('elevation[%d] is now %s', index + i,
                                  elevations[index + i])
                last_known = elevation
                state = 'scanning'

if __name__ == '__main__':
    args = sys.argv[1:]
    if args:
        panorama(*args)
    else:
        import doctest
        doctest.testmod()
