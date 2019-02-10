#!/usr/bin/python -OO
'''
read sample from HGT file

from http://gis.stackexchange.com/a/43756/1291

see also http://www.movable-type.co.uk/scripts/latlong.html
'''
import sys, os, struct, glob, logging, math, pprint, tempfile
from PIL import Image
from earthcurvature import earthcurvature, R, KM, GLOBE
logging.basicConfig(level=logging.DEBUG if __debug__ else logging.INFO)
DEM_DATA = os.getenv('DEM_DATA', '/usr/local/share/gis/hgt')
SAMPLE_SECONDS = 3  # 3 for SRTM3, 1 for SRTM1
DEGREE_IN_SECONDS = 60 * 60
# SAMPLES_PER_ROW 1201 for SRTM3, 3601 for SRTM1
SAMPLES_PER_ROW = (DEGREE_IN_SECONDS / SAMPLE_SECONDS) + 1
DEGREE_IN_SAMPLES = DEGREE_IN_SECONDS / SAMPLE_SECONDS
BYTES_PER_ROW = SAMPLES_PER_ROW * 2
PRETTYPRINTER = pprint.PrettyPrinter()
MAXVALUE = 9000  # meters. highest elevation on earth is about 9000m.
OPEN_FILES = {}
if R not in [float('-inf'), 0.0, float('inf')]:
    RADIUS = abs(R) * KM * 1000  # mean radius of earth in meters
else:  # equirectangular assumes distances same as latitudes along meridian
    RADIUS = GLOBE * KM * 1000

class Degree(tuple):
    '''
    encapsulate dealing with degrees as DMS tuples
    '''
    def __new__(cls, degree, sign=None):
        '''
        create Degree from decimal degree
        '''
        if type(degree) is not tuple:
            as_float = float(degree)
            return super(Degree, cls).__new__(cls, dms(as_float))
        else:
            return super(Degree, cls).__new__(cls, degree)

    def __init__(self, degree, sign=None):
        if sign is not None:
            self.sign = sign
        else:
            self.sign = math.copysign(1, self[0])

    def __add__(self, seconds):
        '''
        add number of seconds to Degree tuple

        must always be a number that will bring total exactly to 60
        or -60 on rollover.

        cannot be counted on to rollover degree, because it has no
        way of knowing if it should rollover at 180 (longitude) or
        90 (latitude).

        >>> Degree((0, 0, -3)) + 3
        (0, 0, 0)

        >>> Degree((-1, 0, 0)) + 3
        (0, -59.0, -57.0)
        '''
        if seconds == 0:
            return self
        if self == (0, 0, 0):  # change sign to what it will be after addition
            self.sign = seconds / abs(seconds)
        d, m, s = self
        s += seconds
        if abs(s) == 60 or (s != 0 and s / abs(s) != self.sign):
            s %= (self.sign * 60)
            m += (seconds / abs(seconds))
            if abs(m) == 60 or (m != 0 and m / abs(m) != self.sign):
                m %= (self.sign * 60)
                d += (seconds / abs(seconds))
        return Degree((d, m, s), self.sign)

def chunks(data, chunksize=2):
    '''
    yield successive chunks from data

    https://stackoverflow.com/a/312464/493161
    '''
    logging.debug('data starts with: %r', data[:10])
    for index in range(0, len(data), chunksize):
        yield data[index:index + chunksize]

def get_row(data, row):
    '''
    return a row from given 0-based index

    from http://dds.cr.usgs.gov/srtm/version2_1/Documentation/SRTM_Topo.pdf:

    "The names of individual data tiles refer to the longitude and 
    latitude of the lower-left (southwest) corner of the tile (this
    follows the DTED convention as opposed to the GTOPO30 standard).
    For example, the coordinates of the lower-left corner of tile 
    N40W118 are 40 degrees north latitude and 118 degrees west
    longitude. To be more exact, these coordinates refer to the
    geometric center of the lower left sample, which in the case of
    SRTM3 data will be about 90 meters in extent.

    "SRTM1 data are sampled at one arc-second of latitude and 
    longitude and each file contains 3601 lines and 3601 samples. 
    The rows at the north and south edges as well as the columns 
    at the east and west edges of each cell overlap and are identical
    to the edge rows and columns in the adjacent cell.

    "SRTM3 data are sampled at three arc-seconds and contain 1201
    lines and 1201 samples with similar overlapping rows and columns. 
    This organization also follows the DTED convention.  Unlike DTED,
    however, 3 arc-second data are generated in each case by 3x3
    averaging of the 1 arc-second data - thus 9 samples are combined 
    in each 3 arc-second data point. Since the primary error source 
    in the elevation data has the characteristics of random noise this
    reduces that error by roughly a factor of three.

    "This sampling scheme is sometimes called a 'geographic 
    projection', but of course it is not actually a projection in the
    mapping sense. It does not possess any of the characteristics
    usually present in true map projections, for example it is not 
    conformal, so that if it is displayed as an image geographic
    features will be distorted. However it is quite easy to handle
    mathematically, can be easily imported into most image processing
    and GIS software packages, and multiple cells can be assembled 
    easily into a larger mosaic (unlike the pesky UTM projection, for
    example.)

    "3.1 DEM File (.HGT)

    "The DEM is provided as 16-bit signed integer data in a simple
    binary raster. There are no header or trailer bytes embedded
    in the file. The data are stored in row major order (all the 
    data for row 1, followed by all the data for row 2, etc.).

    "All elevations are in meters referenced to the WGS84/EGM96
    geoid as documented at http://www.NGA.mil/GandG/wgsegm/."

    experimentation shows that the final row of a higher-latitude
    file matches closely, but not exactly, to the first row of the
    quadrant one degree lower at the same longitude. this means that
    the samples are stored north to south, west to east. luckily,
    that is also how PIL treats X and Y values, top to bottom and left
    to right.

    >>> len(get_row(read(os.path.join(DEM_DATA, 'N39W119.hgt')), 0))
    2402
    >>> s = get_row(read(get_hgt_file('37', '-114')[0]), 1200)
    >>> t = get_row(read(get_hgt_file('36', '-114')[0]), 0)
    >>> s == t  # this was False when I first tested!
    True
    >>> s[:16] == t[:16]  # this was True when I first tested, unnecessary now
    True
    '''
    offset = row * BYTES_PER_ROW
    rowdata = data[offset:offset + BYTES_PER_ROW]
    logging.debug('rowdata: %r ...' % rowdata[:32])
    return rowdata

def get_column(data, column):
    '''
    return a column from 0-based index

    see get_row() for explanation -- columns use the same format

    experimentation shows that the first column of each row is the
    overlap line, and in a NW sector file belongs to the latitude
    of the filename. which means that all following samples belong
    to the quadrant one degree less.

    >>> s=get_column(read(get_hgt_file('36', '-115')[0]), 0)
    >>> t=get_column(read(get_hgt_file('36', '-116')[0]), 1200)
    >>> s==t  # this was False when I first downloaded files
    True
    >>> s[:16]==t[:16]  # this is now unnecessary now previous test passes
    True
    '''
    columndata = ''
    for index in range(SAMPLES_PER_ROW):
        offset = (BYTES_PER_ROW * index) + (column * 2)
        columndata += data[offset:offset + 2]
    return columndata

def unpack_sample(sample):
    r'''
    unpack 2-byte sample into signed short

    from http://dds.cr.usgs.gov/srtm/version2_1/Documentation/SRTM_Topo.pdf:

    "All elevations are in meters referenced to the WGS84/EGM96
    geoid as documented at http://www.NGA.mil/GandG/wgsegm/.

    "Byte order is Motorola ("big-endian") standard with the most
    significant byte first. Since they are signed integers 
    elevations can range from -32767 to 32767 meters, encompassing 
    the range of elevation to be found on the Earth.

    "These data also contain occassional voids from a number of 
    causes such as shadowing, phase unwrapping anomalies, or other
    radar-specific causes. Voids are flagged with the value -32768."

    >>> unpack_sample('\x80\x00')
    -32768
    >>> unpack_sample('\x88\x88')
    -30584
    '''
    try:
        unpacked = struct.unpack('>h', sample)[0]
    except struct.error:
        raise ValueError('Bad sample for short: %r' % sample)
    return unpacked

def get_hgt_file(north, east):
    '''
    locate .hgt file up to three levels deep in DEM_DATA folder

    specify latitude and longitude as signed colon-separated numbers, e.g.
    ('50:24:58.888', '14:55:11.377')

    north and east numbers go from 00 to 89 (north) and 000 to 179 (east)
    south and west numbers go from 01 to 90 (south) and 001 to 180 (west)

    note that the files are named for the *southwesternmost* sample
    in the file, so for U.S. coordinates which are all in the NW,
    all samples other than the overlap line will have
    *lower* longitude values, and only the overlap line of latitude will
    have a higher latitude number.

    all files start at the northwesternmost point; samples are longitude
    first (columns) and latitude second (rows).

    examples: N00W001.hgt, if it existed, would start at latitude (1,0,0)
    and longitude (-1,0,0) and count up (to 0) in longitude,
    down in latitude.

    N00E000.hgt would start at latitude (1,0,0) and longitude (0,0,0)
    and count up in longitude, down in latitude.

    S01W001.hgt would start at latitude (0,0,0) and longitude (-1,0,0)
    and count up in both.

    S01E000.hgt would start at latitude (0,0,0) and longitude (0,0,0)
    and count up in both.

    return filename that contains given latitude and longitude;
    latitude and longitude of first sample (degrees);
    and delta latitude and longitude between samples (seconds).

    >>> get_hgt_file('43', '-119')
    ('/usr/local/share/gis/hgt/N43W120.hgt', 44, -120, -3, 3)
    '''
    latitude = degrees(north)
    if latitude < 0:
        lat = int(latitude)
        filebase = 'S%02d' % (abs(lat) + 1)
        d_lat = SAMPLE_SECONDS
    else:
        lat = int(latitude) + 1
        filebase = 'N%02d' % (lat - 1)
        d_lat = -SAMPLE_SECONDS
    longitude = degrees(east)
    if longitude < 0:
        lon = int(longitude) - 1
        filebase += 'W%03d.hgt' % abs(lon)
    else:
        lon = int(longitude)
        filebase += 'E%03d.hgt' % lon
    d_lon = SAMPLE_SECONDS
    matched = None
    globbed = [
        os.path.join(DEM_DATA, filebase),
        os.path.join(DEM_DATA, '*', filebase),
        os.path.join(DEM_DATA, '*', '*', filebase),
    ]
    for path in globbed:
        match = glob.glob(path)
        if match:
            matched = match[0]
            break
    if matched is None:
        raise(ValueError('No match for %s under %s' % (filebase, DEM_DATA)))
    else:
        logging.debug('Showing elevation for %s' % matched)
    return matched, lat, lon, d_lat, d_lon

def north_offset(north, direction):
    '''
    byte offset into .hgt file for given latitude and direction (+ or -)

    north is a DMS tuple; direction is a positive or negative number
    representing how many seconds of arc is covered by each sample

    >>> north_offset(Degree((37, 0, 0)), -SAMPLE_SECONDS)
    2882400
    >>> north_offset(Degree((-1, -59, -57)), -SAMPLE_SECONDS)
    2879998
    '''
    logging.debug('north: %s, direction: %d', repr(north), direction)
    row = abs((north[1] * 60) + north[2]) / abs(direction)
    if math.copysign(1, direction) != north.sign:
        logging.debug('north_offset from opposite end of file')
        row = SAMPLES_PER_ROW - row - 1
    logging.debug('row: %d', row)
    return row * BYTES_PER_ROW

def east_offset(east, direction):
    '''
    byte offset into row for given longitude and direction

    see north_offset for details

    >>> east_offset(Degree((-118, 0, 0)), -SAMPLE_SECONDS)
    0
    '''
    logging.debug('east: %s, direction: %d', repr(east), direction)
    offset = abs((east[1]) * 60 + east[2]) / abs(direction)
    logging.debug('offset before: %d', offset)
    if math.copysign(1, direction) != east.sign:
        logging.debug('east_offset from opposite end of row')
        offset = SAMPLES_PER_ROW - offset - 1
    logging.debug('offset after: %d', offset)
    return offset * 2  # 2 bytes per sample

def get_height(north, east):
    '''
    return height for a specific point

    >>> get_height(37.0102656, -119.7659941)
    210
    '''
    filename, lat, lon, d_lat, d_lon = get_hgt_file(north, east)
    logging.debug('d_lat: %d, d_lon: %d', d_lat, d_lon)
    dms_north = Degree(degrees(north))
    dms_east = Degree(degrees(east))
    offset = north_offset(dms_north, d_lat) + east_offset(dms_east, d_lon)
    infile = OPEN_FILES.setdefault(filename, open(filename, 'rb'))
    infile.seek(offset)
    sample = infile.read(2)
    height = unpack_sample(sample)
    logging.debug('height at %s %s: %d',
                  repr(dms_north), repr(dms_east), height)
    return height

def dms(degrees, roundto=SAMPLE_SECONDS):
    '''
    return tuple for degrees-minutes-seconds, given decimal degrees

    roundto value is the number of seconds, 3 for SRTM3

    >>> dms(20.25)
    (20, 15, 0)
    
    >>> dms(-20.25)
    (-20, -15, 0)
    '''
    d = int(degrees)
    m = int((degrees - d) * 60)
    s = (degrees - d - (m / 60.0)) * 3600
    rounded_s = (int(s) / roundto) * roundto
    return (d, m, rounded_s)

def decimal(dms):
    '''
    return decimal degrees, given degrees-minutes-seconds tuple of floats
    >>> decimal((20.0, 15.0, 0.0))
    20.25
    >>> decimal((-0.0, -15.0, -0.0))
    -0.25
    '''
    d = dms[0]
    m = dms[1] / 60.0
    s = dms[2] / (60.0 * 60.0)
    return d + m + s

def degrees(value):
    '''
    make sure value is decimal degrees

    can be passed in as string from command line, or as dms tuple
    '''
    try:
        return float(value)
    except TypeError as assuming_tuple:
        return decimal(value)
    except ValueError as assuming_dms_string:
        return decimal(map(float, value.split(':')))

def radians(value):
    '''
    return various degree formats as radians
    '''
    return math.radians(degrees(value))

def getrawdata(north, east):
    '''
    returns data in flat, one-dimensional list
    '''
    filename, latitude, longitude, d_lat, d_lon = get_hgt_file(north, east)
    databytes = read(filename)
    rawdata = [unpack_sample(sample) for sample in chunks(databytes)]
    return rawdata, north, east, d_lat, d_lon

def histogram(ignored, north, east, *alsoignored):
    '''
    return elevation values and counts of quadrant
    '''
    rawdata, north, east, d_lat, d_lon = getrawdata(north, east)
    values = sorted(set(rawdata))
    return {value: rawdata.count(value) for value in values}

def getdata(north, east):
    '''
    faster than dump_samples, returns only data in list of rows
    '''
    data, ignored, ignored, d_lat, d_lon = getrawdata(north, east)
    logging.debug('len(data): %d, sample: %r', len(data), data[:10])
    rowdata = chunks(data, chunksize=SAMPLES_PER_ROW)
    logging.debug('data loaded into 2D array')
    return rowdata, north, east, d_lat, d_lon

def flatten(rows):
    '''
    convert rows of sample values into flat list
    
    the list comprehension is about two orders of magnitude faster than
    sum(rows, [])
    '''
    return [sample for row in rows for sample in row]

def rows(imagedata):
    '''
    convert imagedata into rows of sample values
    '''
    return list(chunks(data, chunksize=SAMPLES_PER_ROW))

def lighten(sample, maxvalue=MAXVALUE):
    '''
    modify the values for better visibility

    it seems that 'I' data is taken as unsigned instead of signed, so
    the actual range is between 0 and 65535.
    '''
    multiplier = 65000 / (math.log10(maxvalue))
    lightened = -32768
    if sample not in [-32768, 0]:
        sign = math.copysign(1, sample)
        lightened = int(sign * multiplier * math.log10(abs(sample)) + 535)
    elif sample == 0:
        lightened = 535
    return min(max(lightened, 0), 65535)

def hgtimage(rowdata, north=None, east=None, d_lat=None, d_lon=None):
    '''
    convert row data from getdata() into PIL Image

    do any transformations necessary to bring out the detail
    '''
    image = Image.new('I', (1201, 1201), None)
    flattened = flatten(rowdata)
    logging.debug('flattened image data')
    values = sorted(set(flattened))
    logging.debug('first 5 values: %s', values[0:5])
    minvalue = values[0] if values[0] > -32768 else values[0:2][-1]
    maxvalue = values[-1]
    logging.debug('minvalue: %s, maxvalue: %s', minvalue, maxvalue)
    if not os.getenv('OCEANFRONT') and -32768 < minvalue < 0:
        logging.debug('setting minimum value to one')
        flattened = [n - minvalue + 1 for n in flattened]
        maxvalue += -minvalue + 1
        logging.debug('maxvalue readjusted to %d', maxvalue)
    if not os.getenv('ADAPTIVE_LIGHTENING'):
        maxvalue = MAXVALUE
        logging.debug('maxvalue set to %d', maxvalue)
    lightened = [lighten(n, maxvalue=maxvalue) for n in flattened]
    logging.debug('improved contrast')
    image.putdata(lightened)
    logging.debug('created image from rowdata')
    if os.getenv('SHOW_LOCATION') and north is not None and east is not None:
        mark_cross(image, north, east, d_lat, d_lon)
    return image

def mark_cross(image, north, east, d_lat, d_lon):
    '''
    mark a cross on an hgtimage at the given coordinates
    '''
    dms_north = Degree(degrees(north))
    dms_east = Degree(degrees(east))
    offset = (north_offset(dms_north, d_lat) + east_offset(dms_east, d_lon)) / 2
    data = list(image.getdata())
    try:
        data[offset] = 0
    except IndexError:
        logging.error('IndexError at index %d of %d', offset, len(data))
        raise
    # if we're at the end or beginning of a row or column, this won't work well
    data[offset - 1] = 0
    data[offset + 1] = 0
    data[offset - 1201] = 0
    data[offset + 1201] = 0
    image.putdata(data)

def dump_samples(north, east):
    '''
    dump out .hgt file as list of samples, with coordinates

    #>>> len(dump_samples('43', '-119')) == SAMPLES_PER_ROW ** 2
    #True
    '''
    filename, latitude, longitude, d_lat, d_lon = get_hgt_file(north, east)
    if longitude == 180:
        longitude = -180  # to avoid extra trickery later
    lat = Degree((latitude, 0, 0))
    lon = Degree((longitude, 0, 0))
    bumped_lon = longitude + (d_lon / abs(d_lon))
    data = read(filename)
    offset = 0
    datalist = []
    while offset < len(data):
        sample = unpack_sample(data[offset:offset+2])
        datalist.append((lat, lon, sample))
        if os.getenv('DUMP_SAMPLES'):
            logging.debug('sample: %s' % repr(datalist[-1]))
        offset += 2
        lon += d_lon
        if lon[1] == lon[2] == 0 and lon[0] != bumped_lon:
            lon = Degree((longitude, 0, 0))
            lat += d_lat
    return datalist

def read(filename):
    '''
    return binary data from file, closing it properly
    '''
    infile = open(filename, 'rb')
    data = infile.read()
    infile.close()
    return data

def show(image, prefix='hgt'):
    '''
    replace Image.show(), which converts 16-bit image (I) to 8-bit (L)
    '''
    handle, path = tempfile.mkstemp(prefix=prefix, suffix='.png')
    os.close(handle)
    image.save(path)
    logging.debug('displaying image %s', path)
    os.system('display %s' % path)
    if os.getenv('DELETE_IMAGE_AFTER_DISPLAY'):
        logging.debug('deleting image %s', path)
        os.unlink(path)

if __name__ == "__main__":
    show(hgtimage(*getdata(*sys.argv[1:])), '_'.join(sys.argv[1:]))
