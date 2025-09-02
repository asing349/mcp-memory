.PHONY: dev test fmt lint seed bench

dev:
	uvicorn mcp_memory.server:app --reload

test:
	pytest -q

fmt:
	ruff check --fix .
	black .

lint:
	ruff check .
	black --check .

seed:
	python scripts/seed.py

bench:
	python scripts/bench.py
