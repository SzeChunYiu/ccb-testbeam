.PHONY: mc-help mc-test mc-smoke

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

mc-help:
	$(PYTHON) -m ccb_mc_validation --help

mc-test:
	$(PIP) install -e ".[dev]" -q
	$(PYTHON) -m pytest tests/ -q

mc-smoke: mc-help
	$(PIP) install -e ".[dev]" -q
	$(PYTHON) -m ccb_mc_validation audit --repo-root .
	$(PYTHON) -m ccb_mc_validation synthesize --config configs/mc_validation/base.yaml
	$(PYTHON) -m ccb_mc_validation mv0-digitize --config configs/mc_validation/base.yaml
