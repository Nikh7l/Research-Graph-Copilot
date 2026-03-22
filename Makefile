.PHONY: lint format test type-check dev

lint:
	ruff check app/ tests/

format:
	ruff format app/ tests/

format-check:
	ruff format --check app/ tests/

type-check:
	mypy app/

test:
	pytest tests/ -v

dev:
	uvicorn app.main:app --reload

all: lint type-check test
