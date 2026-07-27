.PHONY: mc-help mc-test mc-smoke plots plots-check plots-docs

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


plots:
	PYTHONPATH=src $(PYTHON) scripts/generate_paper_grade_wiki_figures.py --repo-root . --output docs/figures/paper

plots-check:
	PYTHONPATH=src $(PYTHON) scripts/check_plot_quality.py --repo-root .

plots-docs: plots
	PYTHONPATH=src $(PYTHON) scripts/update_wiki_plot_docs.py --repo-root .
