.PHONY: install lint format test run clean

install:
	uv sync
	uv run pre-commit install

lint:
	uv run ruff check .
	uv run ty check src/

format:
	uv run ruff format .

test:
	uv run pytest

run:
	PYTHONPATH=src uv run python -m docs2pdf

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -delete
	rm -rf htmlcov
