.PHONY: sync check lint format typecheck test

sync:
	uv sync --extra dev

check: lint typecheck test

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck:
	uv run mypy src

test:
	uv run pytest tests -v --cov=rdc --cov-report=term-missing --cov-fail-under=80
