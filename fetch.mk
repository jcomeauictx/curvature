# use Bash
SHELL := /bin/bash
# disable builtin rules
MAKEFLAGS += --no-builtin-rules
DEM_DATA := /usr/local/share/gis/hgt
SRTM3 := https://dds.cr.usgs.gov/srtm/version2_1/SRTM3
all: N24W111.fetch $(DEM_DATA)/N24W111.hgt
$(DEM_DATA):
	sudo mkdir -p $@
	sudo chown -R $(USER):$(USER) $@
$(DEM_DATA)/%.hgt: /tmp/%.hgt | $(DEM_DATA)
	mv $< $@
%.fetch: $(DEM_DATA)/%.hgt
	@echo $*.fetch invoked
/tmp/%.hgt.zip:
	cd /tmp && wget -nc $(SRTM3)/North_America/$*.hgt.zip || \
	 (dd if=/dev/zero of=$(@:.zip=) bs=2884802 count=1; zip $@ $(@:.zip=))
/tmp/%.hgt: /tmp/%.hgt.zip
	cd /tmp && unzip -u $<
