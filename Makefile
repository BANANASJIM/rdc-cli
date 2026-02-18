.PHONY: check lint format typecheck test

check: lint typecheck test

lint:
	ruff check src tests
	ruff format --check src tests

format:
	ruff format src tests
	ruff check --fix src tests

typecheck:
	mypy src

test:
	pytest tests -v --cov=rdc --cov-report=term-missing --cov-fail-under=80
