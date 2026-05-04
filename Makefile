reqs:
	uv sync

dev:
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
