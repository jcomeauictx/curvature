#!/usr/bin/python
'''
calculate and display panorama of horizon from given point and bearing

various views can be generated based on flat-earth, concave-earth, and
convex-earth views.
'''
import sys, os, math, hgtread
from ast import literal_eval as eval  # safe alternative to eval
from hgtread import logging, get_height
from hgtread import RADIUS, SAMPLE_SECONDS
from earthcurvature import R, earthcurvature
from PIL import Image
logging.basicConfig(level=logging.DEBUG if __debug__ else logging.INFO)
SPAN = float(os.getenv('SPAN', '60.0'))
logging.info('SPAN: %.02f', SPAN)
WHITE = OPAQUE = COMPLETELY = 255
DARKEST = 10
BLACK = NONE = 0
BLACKPIXEL = (BLACK, BLACK, BLACK, OPAQUE)
WHITEPIXEL = (WHITE, WHITE, WHITE, OPAQUE)
BLUEPIXEL = (NONE, NONE, COMPLETELY, OPAQUE)
OCEANFRONT = bool(os.getenv('OCEANFRONT'))
CAMERA_HEIGHT = float(os.getenv('CAMERA_HEIGHT', '1.538'))
FLAT_EARTH_RADIUS = math.pi * RADIUS  # north pole to "ice rim"
DEGREE_IN_METERS = (RADIUS * 2 * math.pi) / 360.0
SAMPLE_IN_METERS = DEGREE_IN_METERS / (60 * (60 / SAMPLE_SECONDS))
logging.debug('RADIUS: %s, DEGREE_IN_METERS: %s', RADIUS, DEGREE_IN_METERS)

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
    logging.info('bearing (compass): %.2f', bearing)
    bearing = math.radians(cartesian(bearing))
    logging.info('bearing (cartesian): %.2f', math.degrees(bearing))
    viewrange = distance * 1000  # km to meters
    logging.info('radius: %s, step: %s', RADIUS, step)
    height += get_height(latitude, longitude)
    logging.info('initial height: %s', height)
    halfspan = math.radians(span) / 2
    d_bearing = math.asin(float(step) / viewrange)
    logging.info('delta angle: %s (%s)', d_bearing, math.degrees(d_bearing))
    angle = bearing + halfspan
    logging.info('initial angle: %s', math.degrees(angle))
    logging.info('final angle: %s', math.degrees(bearing - halfspan))
    # elevations will be expressed in 3 ways:
    # 0. actual elevation above sea level;
    # 1. 'y' pixel coordinate after correcting for perspective
    #    (also for curvature if enabled in model)
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
            math.degrees(angle), latitude, longitude, distance, step)])
        correct_for_no_data(elevations[-1], raw, farthest)
        for index in range(1, len(elevations[-1])):
            elevation = elevations[-1][index][raw]
            # factor in curvature if enabled
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
    for index in range(width):
        x = index
        # adding a previous level of `image_height` will ensure a ridge line
        # gets drawn on the most distant plot
        # adding the spot on which the observer is standing will allow
        # checking the arc of view of each point
        pointlist = elevations[index]
        pointlist = [pointlist[0]] + pointlist + [[None, None, image_height]]
        logging.debug('index: %d, pointlist: %s', index, pointlist)
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
                              color, y + 1, context[closer][y_image] + 1)
                for plot in range(y + 1, context[closer][y_image] + 1):
                    putpixel(panorama, (x, plot), color)
    panorama.show()

def look(angle, north, east, distance, d_travel):
    '''
    return list of elevation in the given direction
    '''
    logging.info('look(%s, %s, %s, %s)', angle, north, east, distance)
    elevations = []
    traversed = 0
    radians = math.radians(angle)
    distance *= 1000  # convert km to meters
    while traversed < distance:
        elevation = get_height(north, east)
        elevations.append(elevation)
        radians = math.radians(angle)
        north, east = move(north, east, angle, d_travel, False)
        traversed += d_travel
    return elevations

def spherical_distance(lat1, lon1, lat2, lon2):
    '''
    as-the-bullet-flies distance in meters between two points

    using Pythagorean theorem on equirectangular projection as
    shown on http://www.movable-type.co.uk/scripts/latlong.html

    not using Haversine because we're judging how things would *look*
    from a fixed point. we're not actually going overland to it.

    >>> spherical_distance(37, 116, 37, 117)
    88809.47272660509
    '''
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    x = (lon2 - lon1) * math.cos((lat1 + lat2) / 2)
    y = (lat2 - lat1)
    d = math.sqrt((x * x) + (y * y)) * RADIUS
    return d

def cartesian(bearing):
    '''
    convert compass bearing in degrees to math module bearing in degrees
    
    0 (north) becomes 90 (0x, 1y)
    90 (east) becomes 0  (1x, 0y)
    180 (south) becomes -90 (0x, -1y)
    270 (west) becomes 180 (-1x, 0y)

    >>> cartesian(0)
    90
    >>> cartesian(-90)
    180
    >>> cartesian(180)
    -90
    >>> cartesian(270)
    180
    '''
    converted = (90 - bearing) % 360
    if converted > 180:
        converted -= 360
    elif converted < -180:
        converted += 360
    return converted

compass = cartesian  # reverse holds true

def latitude_extremes(latitude, longitude, bearing, distance, span):
    '''
    find the minimum and maximum latitude in the area covered

    we will need this to find the longitudinal distances covered by a sample

    FIXME: for now I will simplify and just assume distance +- latitude,
    regardless whether bearing and span justify it or not.
    '''
    northwards = spherical_move(latitude, longitude, 0, distance)[0]
    southwards = spherical_move(latitude, longitude, 180, distance)[0]
    most_polar = max(northwards, southwards, key=abs)
    most_equatorial = min(northwards, southwards, key=abs)
    if math.copysign(1, most_polar) != math.copysign(1, most_equatorial):
        # span crosses equator
        return (0, most_polar)
    else:
        return(most_equatorial, most_polar)

def spherical_move(latitude, longitude, bearing, distance,
        compass_bearing=True):
    '''
    resulting latitude and longitude from as-the-bullet-flies move

    from http://gis.stackexchange.com/a/30037/1291, but corrected for
    the Cartesian sense of zero degrees that the Python math module uses.

    a purely latitudinal move should be same on all 3 models

    >>> spherical_move(60.0, -110.0, 0, DEGREE_IN_METERS)
    (61.0, -110.0)

    a longitudinal move will cover more than 1 degree north or
    south of the equator, twice as much at the 60th parallel
    
    at equator, latitude is returned as a very small positive quantity so we
    round it

    >>> tuple(map(round, spherical_move(0.0, -110.0, -90, DEGREE_IN_METERS)))
    (0, -111)
    >>> spherical_move(60.0, -110.0, -90, DEGREE_IN_METERS)
    (60.0, -112.0)
    '''
    if compass_bearing:  # expressed as clockwise degrees from due north
        radians = math.radians(cartesian(bearing))
    else:
        radians = math.radians(bearing)
    distance_x = math.cos(radians) * distance
    distance_y = math.sin(radians) * distance
    logging.debug('distances to move: (%.3fx, %.3fy)', distance_x, distance_y)
    degrees_y = distance_y / DEGREE_IN_METERS
    average_latitude = math.radians(latitude + (degrees_y / 2))
    degrees_x = (distance_x / math.cos(average_latitude)) / DEGREE_IN_METERS
    return (degrees_y + latitude, degrees_x + longitude)

def equirectangular_move(latitude, longitude, bearing, distance,
        compass_bearing=True):
    '''
    move on hypothetical equirectangular earth

    a purely latitudinal move should be same on all 3 models

    >>> equirectangular_move(60.0, -110.0, 0, DEGREE_IN_METERS)
    (61.0, -110.0)

    a longitudinal move will only equal latitudinal in this model

    >>> equirectangular_move(60.0, -110.0, -90, DEGREE_IN_METERS)
    (60.0, -111.0)
    '''
    if compass_bearing:  # expressed as clockwise degrees from due north
        radians = math.radians(cartesian(bearing))
    else:
        radians = math.radians(bearing)
    dx = math.sin(radians) * (distance / DEGREE_IN_METERS)
    dy = math.cos(radians) * (distance / DEGREE_IN_METERS)
    logging.debug('dx %s, dy %s, new latitude %s, new longitude %s',
                  dx, dy, latitude + dx, longitude + dy)
    return (latitude + dx, longitude + dy)

def latitude_to_rho(latitude):
    '''
    convert degrees latitude to azimuthal equidistant radius and back

    >>> latitude_to_rho(90)  # north pole
    0
    >>> latitude_to_rho(0)  # equator
    90
    >>> latitude_to_rho(-90)  # south pole
    180
    >>> latitude_to_rho(180)  # rho to latitude
    -90
    '''
    return 90 - latitude

rho_to_latitude = latitude_to_rho  # same as compass() and cartesian()

def relative_bearing(bearing, longitude, compass_bearing=True):
    '''
    correct bearing for azimuthal equidistant "flat earth"

    it is relative to the longitude angle, which always points "north"

    return as cartesian angle in radians, *not* compass

    >>> round(relative_bearing(0, 0), 2)
    -1.57
    >>> round(relative_bearing(0, 180), 2)
    1.57
    >>> round(relative_bearing(0, 90), 2)
    3.14
    >>> round(relative_bearing(10, 180), 2)
    1.4
    '''
    if not compass_bearing:
        bearing = compass(bearing)
    logging.debug('bearing %s, longitude %s', bearing, longitude)
    bearing = cartesian(180 + longitude + bearing)
    logging.debug('relative bearing: %s', bearing)
    return math.radians(bearing)

def azimuthal_equidistant_move(latitude, longitude, bearing, distance,
        compass_bearing=True):
    '''
    move on hypothetical flat earth

    there must be a way to do this without going back and forth from
    Cartesian system, but math is hard and this will have to do for now.

    a purely latitudinal move should be same on all 3 models
    but "purely latitudinal" on this model can only be from the
    bottom of the "disk", longitude 180

    >>> azimuthal_equidistant_move(60.0, 180.0, 0, DEGREE_IN_METERS)
    (61.0, 180.0)

    a move westward at 60 degrees north should cover about 2 degrees,
    and due to circular latitude "lines" should be south of starting point

    >>> azimuthal_equidistant_move(0.0, 180.0, -90, DEGREE_IN_METERS)
    (-0.005555384098371974, -179.36340642403653)
    >>> azimuthal_equidistant_move(60.0, 180.0, -90, DEGREE_IN_METERS)
    (59.98333796039273, -178.0908475670036)
    '''
    logging.debug('move: %s, %s, %s, %s, %s', latitude, longitude,
                  bearing, distance, compass_bearing)
    radians = relative_bearing(bearing, longitude, compass_bearing)
    rho, theta = latitude_to_rho(latitude), math.radians(longitude)
    x = rho * math.sin(theta)
    y = rho * math.cos(theta)
    logging.debug('before: x %s, y %s, rho %s, theta %s', x, y, rho, theta)
    logging.debug('check on theta %s: %s', theta, math.atan2(y, x))
    dx, dy = equirectangular_move(0, 0, bearing, distance, False)
    x, y = x + dx, y + dy
    rho = math.sqrt((x * x) + (y * y))
    theta = math.atan2(y, x)
    logging.debug('after: x %s, y %s, rho %s, theta %s', x, y, rho, theta)
    return (rho_to_latitude(rho), compass(math.degrees(theta)))

def maximum_delta(latitude, longitude, bearing, distance, span):
    '''
    find the maximum distance to move that "sees" all SRTM3 samples

    >>> round(maximum_delta(0, 0, 0, 0, 0))
    93
    >>> round(maximum_delta(60, 0, 0, 0, 0))
    46
    '''
    extremes = latitude_extremes(latitude, longitude, bearing, distance, span)
    seconds = float(SAMPLE_SECONDS) / 3600
    return spherical_distance(extremes[1], 0, extremes[1], seconds)

if R == 0:
    move = azimuthal_equidistant_move
elif R in [float('-inf'), float('inf')]:
    move = equirectangular_move
else:
    move = spherical_move

if __name__ == '__main__':
    args = sys.argv[1:]
    if args:
        panorama(*map(float, args))
    else:
        import doctest
        doctest.testmod()
