.DEFAULT_GOAL := help

UV ?= uv
MYSQL_COMPOSE := docker compose -f tests/adapters/mysql/compose.yaml
DBRIDGE_TEST_MYSQL_PORT ?= 33084
PYTEST_ARGS ?=

.PHONY: help manual-prepare check test test-cov mysql-up mysql-down test-mysql

help:
	@printf '%s\n' \
		'make manual-prepare  Sync dependencies and rebuild persistent SQLite/DuckDB samples (resets sample data)' \
		'make check           Run type and lint checks' \
		'make test            Run the automated test suite' \
		'make test-cov        Run the suite with the 85% coverage gate' \
		'make mysql-up        Start isolated MySQL 8.4 test server and wait for seed data' \
		'make test-mysql      Run real MySQL tests (installs mysql extra)' \
		'make mysql-down      Remove the isolated MySQL test server and its data' \
		'make help            Show these commands' \
		'' \
		'Options: UV=uv, PYTEST_ARGS="-q" (or a test path / pytest options)'

manual-prepare:
	$(UV) run python scripts/make_sample_db.py

check:
	$(UV) run --group types mypy src/dbridge tests
	$(UV) run ruff check src/dbridge tests

test:
	$(UV) run --group test pytest $(PYTEST_ARGS)

test-cov:
	$(UV) run --group test pytest --cov $(PYTEST_ARGS)

mysql-up:
	DBRIDGE_TEST_MYSQL_PORT=$(DBRIDGE_TEST_MYSQL_PORT) $(MYSQL_COMPOSE) up -d --wait --wait-timeout 240
	$(MYSQL_COMPOSE) exec -T mysql sh -c 'mysql -uroot -p"$$MYSQL_ROOT_PASSWORD" -Nse "SELECT COUNT(*) FROM dbridge_test.million_rows"'

mysql-down:
	$(MYSQL_COMPOSE) down --volumes

test-mysql:
	DBRIDGE_TEST_MYSQL_HOST=$${DBRIDGE_TEST_MYSQL_HOST:-127.0.0.1} \
	DBRIDGE_TEST_MYSQL_PORT=$(DBRIDGE_TEST_MYSQL_PORT) \
	$(UV) run --extra mysql --group test pytest tests/adapters/mysql $(PYTEST_ARGS)
