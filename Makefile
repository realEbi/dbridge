.DEFAULT_GOAL := help

UV ?= uv
PYTEST_ARGS ?=

.PHONY: help manual-prepare test test-cov

help:
	@printf '%s\n' \
		'make manual-prepare  Sync dependencies and rebuild persistent SQLite/DuckDB samples (resets sample data)' \
		'make test            Run the automated test suite' \
		'make test-cov        Run the suite with the 85% coverage gate' \
		'make help            Show these commands' \
		'' \
		'Options: UV=uv, PYTEST_ARGS="-q" (or a test path / pytest options)'

manual-prepare:
	$(UV) run python scripts/make_sample_db.py

test:
	$(UV) run --group test pytest $(PYTEST_ARGS)

test-cov:
	$(UV) run --group test pytest --cov $(PYTEST_ARGS)
