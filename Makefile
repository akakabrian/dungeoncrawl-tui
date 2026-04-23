PY ?= python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYBIN := $(VENV)/bin/python

.PHONY: all venv run qa qa-only perf clean

all: venv

venv:
	$(PY) -m venv $(VENV)
	$(PIP) install -U pip setuptools wheel
	$(PIP) install -e .

run:
	$(PYBIN) wiz.py

qa:
	$(PYBIN) -m tests.qa

qa-only:
	$(PYBIN) -m tests.qa $(PAT)

perf:
	$(PYBIN) -m tests.perf

clean:
	rm -rf $(VENV) *.egg-info **/__pycache__ tests/out/*.svg
