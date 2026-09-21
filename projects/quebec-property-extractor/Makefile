
.PHONY: install test lint format clean

install:
	pip install -e .[dev]

test:
	pytest tests/unit tests/integration

lint:
	ruff check src tests

format:
	ruff format src tests

clean:
	rm -rf data/raw/* data/interim/* data/output/*