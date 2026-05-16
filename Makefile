.PHONY: install test demo watch watch-step watch-eval gui-demo lint format clean

install:
	pip install -e ".[dev]"

test:
	pytest

demo:
	python -m polytopia.game_loop

watch:
	python -m polytopia.game_loop --watch --delay 0.5

watch-step:
	python -m polytopia.game_loop --watch --step

watch-eval:
	python -m polytopia.game_loop --watch --eval --delay 0.3

gui-demo:
	python -m polytopia.renderers.gui.main_renderer

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
