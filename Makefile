PY := .venv/bin/python

.PHONY: setup download bench bench-caller bench-turn bench-tts bench-stt bench-memory bench-router bench-dialogues bench-contention report samples test lint format

setup:
	uv venv .venv --python 3.12
	. .venv/bin/activate && uv pip install -e ".[dev]"

download:
	$(PY) scripts/download_models.py

bench-turn:
	$(PY) -m bench.turn

bench-tts:
	$(PY) -m bench.tts

bench-stt:
	$(PY) -m bench.stt

bench-memory:
	$(PY) -m bench.memory

bench-router:
	$(PY) -m bench.router

bench-dialogues:
	$(PY) -m bench.dialogues --split test --models e2b e4b --brains single router --repeats 2

bench-contention:
	$(PY) -m bench.contention --model e2b

# Needs the agent already serving on --url; left out of `bench` for that reason.
bench-caller:
	$(PY) -m bench.caller --turns 220

samples:
	$(PY) scripts/voice_samples.py

report:
	$(PY) -m bench.report

# Run stages one at a time so they don't compete for the chip.
bench: bench-turn bench-tts bench-stt bench-memory bench-router bench-dialogues bench-contention report

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

format:
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .
