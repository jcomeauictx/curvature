DUMP_SAMPLES ?= 1
SRTM3 := https://dds.cr.usgs.gov/srtm/version2_1/SRTM3
DEM_DATA := /usr/local/share/gis/hgt
SCRIPTS := $(wildcard *.py)
ISLA_SAN_JOSE := (110, 24.164640, -110.312864, 180)
DRYRUN ?= --dry-run
EARTH_RADIUS_MILES ?= 0
COEFFICIENT_OF_REFRACTION ?= .25
SPAN ?= 60.0
OPT ?= -OO
export
panorama: panorama.py
	python $(OPT) -c "import $(<:.py=); print $(<:py=$@)$(ISLA_SAN_JOSE)"
showfile: hgtread.py
	DUMP_SAMPLES=1 python $< 37.0102656 -119.7659941
%.doctest: %.py
	python -m doctest $<
doctests: $(SCRIPTS:.py=.doctest)
overview: overview.py
	python $< 37.0102656 -119.7659941
segments: 30_mile_segments.ps
	gs $<
/tmp/%.hgt.zip:
	cd /tmp && wget -nc $(SRTM3)/North_America/$*.hgt.zip || \
	 (dd if=/dev/zero of=$(@:.zip=) bs=2884802 count=1; zip $@ $(@:.zip=))
/tmp/%.hgt: /tmp/%.hgt.zip
	cd /tmp && unzip -u $<
$(DEM_DATA)/%.hgt: /tmp/%.hgt
	mv $< $@
%.fetch:
	$(MAKE) $(DEM_DATA)/$*.hgt
look: hgtread.py
	python -c "import $(<:.py=); print $(<:py=$@)$(ISLA_SAN_JOSE)"
gitupdate: earthcurvature.py  hgtread.py  Makefile  panorama.py  README.md
	rsync -avuz $(DRYRUN) $+ /usr/src/jcomeauictx/curvature/
togit:
	@echo Relocating to git sources. ^D to return here.
	cd /usr/src/jcomeauictx/curvature && bash -l
