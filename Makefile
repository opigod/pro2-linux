SHELL := /usr/bin/env bash

.PHONY: setup build-libratbag build-piper udev check clean

setup: build-libratbag build-piper

build-libratbag:
	./scripts/build-libratbag.sh

build-piper:
	./scripts/build-piper.sh

udev:
	sudo ./scripts/install-udev.sh

check:
	python3 -m py_compile tools/pro2_profile.py tools/pro2_light.py tools/pro2_remap.py
	bash -n scripts/build-libratbag.sh scripts/build-piper.sh scripts/install-udev.sh
	bash -n scripts/pro2ctl scripts/pro2-piper scripts/pro2-special
	rm -rf tools/__pycache__

clean:
	rm -rf .build .run
