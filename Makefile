# use Bash and disable builtin rules
SHELL := /bin/bash
MAKEFLAGS += --no-builtin-rules
SCRIPTS := $(wildcard *.py)
PYLINT := $(SCRIPTS:.py=.pylint)
DOCTEST := $(SCRIPTS:.py=.doctest)
# now begins the actual Makefile
DUMP_SAMPLES ?= 1
SRTM3 := https://gnixl.com/srtm/srtm3
DEM_DATA := /usr/local/share/gis/hgt
ISLA_SAN_JOSE := (-20, 24.164640, -110.312864, 180)
BUCKEYE := (-118, 37.053, -119.393, 200)
# estimate camera (eye) height is 5 feet converted to meters
CAMERA_HEIGHT = 1.538
DRYRUN ?= --dry-run
EARTH_RADIUS_MILES ?= inf
COEFFICIENT_OF_REFRACTION ?= .25
SPAN ?= 60.0
OPT ?= -OO
OCEANFRONT ?= True
WGET ?= wget --no-check-certificate --no-clobber
REQUIRED := N24W111.hgt  N25W112.hgt  N36W115.hgt  N37W115.hgt \
 N43W120.hgt N24W112.hgt  N26W111.hgt  N36W116.hgt  N37W120.hgt N25W111.hgt \
 N26W112.hgt  N36W117.hgt  N39W119.hgt
ifneq ($(SHOWENV),)
 export
else
 export EARTH_RADIUS_MILES COEFFICIENT_OF_REFRACTION SPAN DEM_DATA OCEANFRONT \
  ADAPTIVE_LIGHTENING SHOW_LOCATION DUMP_SAMPLES DELETE_IMAGE_AFTER_DISPLAY \
  CAMERA_HEIGHT
endif
all: doctests $(PYLINT) panorama
/tmp/%.hgt:
	cd /tmp && filename=$* && prefix=$${filename:0:3} && \
	 $(WGET) $(SRTM3)/$$prefix/$*.hgt || \
	 dd if=/dev/zero of=$@ bs=2884802 count=1
$(DEM_DATA):
	sudo mkdir -p $@
	sudo chown -R $(USER):$(USER) $@
$(DEM_DATA)/%.hgt: /tmp/%.hgt | $(DEM_DATA)
	mv $< $@
%.fetch: $(DEM_DATA)/%.hgt
	@echo $* already downloaded
panorama: panorama.py $(REQUIRED:.hgt=.fetch)
	python $(OPT) -c "import $(<:.py=); print($(<:py=$@)$(ISLA_SAN_JOSE))"
buckeye: panorama.py $(REQUIRED:.hgt=.fetch)
	python $(OPT) -c "import $(<:.py=); print($(<:py=panorama)$(BUCKEYE))"
showfile: hgtread.py $(REQUIRED:.hgt=.fetch)
	DUMP_SAMPLES=1 python $< 37.0102656 -119.7659941
%.doctest: %.py
	python -m doctest $<
%.pylint: %.py
	pylint $<
doctests: $(REQUIRED:.hgt=.fetch) $(DOCTEST)
overview: overview.py
	python $< 37.0102656 -119.7659941
segments: 30_mile_segments.ps
	gs $<
look histogram: hgtread.py
	python -c "import $(<:.py=); print $(<:py=$@)$(ISLA_SAN_JOSE)"
gitupdate: earthcurvature.py  hgtread.py  Makefile  panorama.py  README.md screenshots
	rsync -avuz $(DRYRUN) $+ /usr/src/jcomeauictx/curvature/
togit:
	@echo Relocating to git sources. ^D to return here.
	cd /usr/src/jcomeauictx/curvature && bash -l
shell:
	# bring up a subshell with environment variables exported
	bash -l
env:
ifneq ($(SHOWENV),)
	$@
else
	$(MAKE) SHOWENV=1 $@
endif
.PHONY: %.fetch
.PRECIOUS: $(DEM_DATA)/%.hgt
