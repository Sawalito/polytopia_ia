.PHONY: install test demo lint format clean

install:
	pip install -e ".[dev]"

test:
	pytest

demo:
	python -m polytopia.game_loop

lint:
	ruff check src tests
	black --check src tests

format:
	black src tests
	ruff check --fix src tests

clean:
	rm -rf build dist *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
