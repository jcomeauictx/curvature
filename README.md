# Calculations of earth curvature

Although I'm firmly in the "spherical earth" camp, I have friends who range
from "curious about" to "convinced by" flat or hollow earth (on which we live
*on the inside*) hypotheses. This repository is my attempt to allow
exploration of these viewpoints so that the inquistive mind can test which
one holds up best to objective reality.

My eventual goal is to develop a site similar to Ulrich Deuschle's
[panorama generator](http://www.udeuschle.selfhost.pro/panoramas/makepanoramas_en.htm)
but having choice of output to match more than one of these 3 "theories".
That should give the most convincing proof of one "viewpoint" over the other,
since what one sees from a mountaintop should be distinctly different between
a "flat", "round", or "hollow" earth.

The Python script `earthcurvature.py`, based on the formulas shown at
[earthcurvature.com](http://earthcurvature.com/) and
[dizzib.github.io](https://dizzib.github.io/earth/curve-calc/) (although its
output differs from those sites by a small amount, probably due to my choice
of the value of `R` [earth radius]), should help lay one claim to rest:
that of "If there were 266 feet of curvature in 20 miles, I'd be able to see
it". The script output shows that in 1/10 of a mile -- 528 feet -- there is
only about *2mm* of "drop" due to curvature. If you've ever shot at targets
at 100 yards using an iron-sighted rifle, you'll know how small something looks
at that distance, and 528 feet is closer to *2* football fields' distance. So
if you can't see 2mm in 528 feet, you can't arguably see any curvature over
20 miles either. What you *should* be able to see, on a curved earth, is that
things at a distance are most often (except during anomalies of atmospheric
refraction) partially or fully hidden from view by that curve.

A problem with the dizzib and earthcurvature sites is that they don't allow
specification of a refractive index, which adjusts the "drop" by accounting
for the bending of light rays in the denser air typically found at earth's
surface. Typical values are .25 or .125. You can `pydoc earthcurvature` to
see how to use this in your calculations.

Flat-earth proponents will likely balk at the source of the SRTM3 data, their
arch-enemy NASA. However, anyone is free to create their own SRTM3 files with
elevation measurements more to their liking.

As of 2019-01-06, the panoramas generated by `panorama.py` are flat-earth
views, not the "dish" view centered on the North Pole typical of classical
FE belief, but an [equirectangular](https://en.wikipedia.org/wiki/Equirectangular_projection), which should show acceptable panoramas close to the equator, but
will be increasingly distorted the farther away you go. Another caveat is that
they are projected as if the viewer has a narrow vertical slit with which to
see, and so he is turning in place to see the panorama. And one more severe
limitation of the current state of the software is that it assumes a view over
the ocean, and will not show anything below "eye height".

But despite all those shortcomings, it can be useful in comparison with
Ulrich's panoramas at the link mentioned above, and seeing which more
accurately reflects the skyline you see at your current location.

# Getting Started

This assumes a typical Debian developer's system. Your mileage may vary.

```
sudo mkdir -p /usr/local/share/gis/hgt
sudo chown $USER.$USER /usr/local/share/gis/hgt /usr/src
mkdir -p /usr/src/jcomeauictx
cd /usr/src/jcomeauictx
git clone https://github.com/jcomeauictx/curvature.git
cd curvature/
sudo apt-get install zip imagemagick
make N37W120.fetch
make showfile  # shows part of Northern California west of Millerton Lake
make N24W111.fetch N24W112.fetch N25W111.fetch N25W112.fetch N26W111.fetch N26W112.fetch
make panorama  # shows flat-earth horizon in La Paz, MX looking at Isla San Jose
make EARTH_RADIUS_MILES=GLOBE panorama  # same view but adjusted for curvature
```
