#!/usr/bin/python -OO
'''
calculate curvature by various methods

none of the "curvature" websites referenced below take into account
atmospheric refraction. you can include it by setting the environment
variable COEFFICIENT_OF_REFRACTION, typically to about .25:

    jcomeau@aspire:~$ earthcurvature.py 10
    drop in 10.00000000 miles is 66.68347048 feet
    jcomeau@aspire:~$ COEFFICIENT_OF_REFRACTION=.25 earthcurvature.py 10
    drop in 10.00000000 miles is 50.01261449 feet

often you will see the coefficient expressed as 4/3. this is because they
have already inverted it using 1/(1-k). by another formula, which only
measures the effect on curvature from one end, it is expressed as 7/6,
which means a COEFFICIENT_OF_REFRACTION=.125

see https://www.metabunk.org
 /standard-atmospheric-refraction-empirical-evidence-and-derivation.t8703/
and https://en.wikipedia.org/wiki/Atmospheric_refraction
'''
from __future__ import print_function, division
# pylint: disable=consider-using-f-string
import sys, os, math, logging  # pylint: disable=multiple-imports
logging.basicConfig(level=logging.DEBUG if __debug__ else logging.INFO)
# a radius of 0 (zero) will be used to implement the Flat Earth Society
# viewpoint, using an azimuthal equidistant disk centered at the North Pole.
# a positive radius is a normal spherical earth.
# we use a negative radius to signify the "hollow earth" viewpoint
# in which we are living on the _inside_ of the globe.
# both infinity ('inf') and negative infinity ('-inf') will indicate an
# equirectangular flat earth.
GLOBE = 3959.0
try:
    ER = R = RADIUS = float(os.getenv('EARTH_RADIUS_MILES', 'inf'))
except (ValueError, TypeError) as failed_parse:
    # evaluate GLOBE or -GLOBE
    logging.warn('Failed parsing EARTH_RADIUS_MILES as float: %s', failed_parse)
    ER = R = RADIUS = eval(os.getenv('EARTH_RADIUS_MILES'))
K = float(os.getenv('COEFFICIENT_OF_REFRACTION') or '0.0')
if RADIUS > 0 and not math.isinf(RADIUS):
    ER = RADIUS / (1 - K)  # effective radius
elif K:
    logging.warn('Coefficient of refraction ignored without positive radius')
    K = 0.0
CONVEX = math.copysign(1, ER)
KM = 1.60934  # conversion factor, miles to kilometers, from Google
UNITS = ['mm', 'cm', 'm', 'km', 'inches', 'feet', 'yards', 'miles']

def earthcurvature(distance=1, unit='miles', dropunit='feet', height=0):
    '''
    earthcurvature.com formula, h = r * (1 - cos a)

    treats `distance` as being along the circumference
    
    `height` is observer height in dropunits. it is not taken into account
    by this formula, but will be by the dizzib method.
    '''
    distance = float(distance)
    if not ER or math.isinf(ER):
        h = 0
    else:
        c = 2 * math.pi * ER
        d = miles(distance, unit)
        a = (360 / c) * d
        h = convert(ER * (1 - math.cos(math.radians(a))), dropunit)
    logging.debug('locals(): %s', locals())
    return 'drop in %.08f %s is %.08f %s', (distance, unit, h, dropunit)

def dizzib(distance=1, unit='miles', dropunit='feet', height=0):
    '''
    https://github.com/dizzib/earthcalc formula

    d1 is distance to horizon. h1 is hidden height. h0 is observer height.

    d1 = math.sqrt((h0 ** 2) + (2 * R * h0))

    h1 = math.sqrt(((d0 - d1) ** 2) + (R ** 2)) - R

    in this formula `height` is taken into account, but `distance`
    is line-of-sight rather than over-the-sphere-surface.

    it returns distance to horizon as well as "drop", or "hidden height".

    use a `height` parameter of 0 to get similar results as that of
    `earthcurvature`.

    symlink this file as `dizzib` to test this calculation, e.g.:
    `sudo ln -s /usr/local/bin/earthcurvature.py /usr/local/bin/dizzib`
    '''
    distance, height = float(distance), float(height)
    if not ER or math.isinf(ER):
        h1, d1 = 0, float('inf')
    else:
        d0 = miles(distance, unit)
        h0 = miles(height, dropunit)
        d1 = math.sqrt((h0 ** 2) + (2 * abs(ER) * h0))
        d2 = d0 - d1
        h1 = convert(math.sqrt((d2 ** 2) + (ER ** 2)) - abs(ER), dropunit)
    logging.debug('locals(): %s', locals())
    format_string = 'distance to horizon: %.08f %s, hidden height: %.08f %s'
    return format_string, (d1, unit, CONVEX * h1, dropunit)

def parabolic(distance=1, unit='miles', dropunit='feet', height=0):
    '''
    simplest formula treats sphere as parabola, works OK for miles < 300;
    it really blows up at around 1000 miles.

    drop = 8 inches * (miles ** 2)

    symlink this file as `parabolic` to test this calculation, e.g:
    `sudo ln -s /usr/local/bin/earthcurvature.py /usr/local/bin/parabolic`
    '''
    distance = float(distance)
    drop = convert(inches_to_miles(8) * (miles(distance, unit) ** 2), dropunit)
    logging.debug('locals(): %s', locals())
    return 'drop in %.08f %s is %.08f %s', (distance, unit, drop, dropunit)

def convert(distance, unit = 'miles'):
    '''
    all calculations are done in miles, this converts to desired unit
    '''
    if unit in UNITS:
        function = globals().get(unit, None)
        if function is None or not callable(function):
            raise NotImplementedError('%s not yet implemented' % unit)
        return function(distance)
    else:
        raise ValueError('given distance unit %s not in %s', unit, UNITS)

def km(_miles):
    '''
    convert miles to kilometers
    '''
    return _miles * KM

def km_to_miles(amount):
    '''
    convert kilometers to miles
    '''
    return amount / KM

def m(_miles):
    '''
    convert miles to meters
    '''
    return km(_miles) * 1000

def m_to_miles(amount):
    '''
    convert meters to miles
    '''
    return km_to_miles(amount / 1000)

def cm(_miles):
    '''
    convert miles to centimeters
    '''
    return km(_miles) * 100000

def cm_to_miles(amount):
    '''
    convert centimeters to miles
    '''
    return km_to_miles(amount / 100000)

def mm(_miles):
    '''
    convert miles to millimeters
    '''
    return km(_miles) * 1000000

def mm_to_miles(amount):
    '''
    convert millimeters to miles
    '''
    return km_to_miles(amount / 1000000)

def yards(_miles):
    '''
    convert miles to yards
    '''
    return feet(_miles) / 3

def yards_to_miles(amount):
    '''
    convert yards to miles
    '''
    return feet_to_miles(amount * 3)

def feet(_miles):
    '''
    convert miles to feet
    '''
    return _miles * 5280

def feet_to_miles(amount):
    '''
    convert feet to miles
    '''
    return amount / 5280

def inches(_miles):
    '''
    convert miles to inches
    '''
    return feet(_miles) * 12

def inches_to_miles(amount):
    '''
    convert inches to miles
    '''
    return feet_to_miles(amount / 12)

def miles(distance, unit='miles'):
    '''
    convert any supported unit into miles
    '''
    conversion = '%s_to_miles' % unit
    function = globals().get(conversion, None)
    if function is None or not callable(function):
        raise NotImplementedError('%s not yet implemented' % conversion)
    return function(distance)

def miles_to_miles(distance):
    '''
    wish all jobs were this easy...
    '''
    return distance

if __name__ == '__main__':
    ARGS = sys.argv[1:]
    FUNCTION_NAME = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    FUNCTION = globals().get(FUNCTION_NAME, None)
    if FUNCTION is None or not callable(FUNCTION):
        raise NotImplementedError('%s not yet implemented' % FUNCTION_NAME)
    # all curvature functions should have same args as earthcurvature
    DEFAULTS = FUNCTION.func_defaults
    ARGS[len(ARGS):] = DEFAULTS[len(ARGS):]
    FORMAT_STRING, RESULTS = FUNCTION(*ARGS)
    print(FORMAT_STRING % RESULTS)
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
