.PHONY: install test demo watch watch-step watch-eval gui-demo gui-live gui-live-heuristic gui-paused gui-record gui-replay benchmark benchmark-full lint format clean

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

gui-live:
	python -m polytopia.renderers.gui.live_runner

gui-live-heuristic:
	python -m polytopia.renderers.gui.live_runner --bot heuristic --delay 0.4

gui-paused:
	python -m polytopia.renderers.gui.live_runner --paused

gui-record:
	mkdir -p replays
	python -m polytopia.renderers.gui.live_runner --record replays/last_game.json

gui-replay:
	@if [ -z "$(FILE)" ]; then echo "Usa: make gui-replay FILE=replays/partida.json"; exit 1; fi
	python -m polytopia.renderers.gui.replay_player $(FILE) --delay 0.5

benchmark:
	python -m experiments.benchmark

benchmark-full:
	python -m experiments.benchmark --n 50

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
