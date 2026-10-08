.PHONY: setup dev test lint evals seed backend-dev frontend-dev

# Install all dependencies
setup:
	cd backend && pip install -e ".[dev]"
	npm install

# Run both backend and frontend in development
dev:
	@echo "Starting backend on :8000 and frontend on :3000..."
	@make -j2 backend-dev frontend-dev

backend-dev:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	npm run dev

# Run all tests
test:
	cd backend && python -m pytest tests/ -v
	npm run lint

# Lint
lint:
	cd backend && ruff check . && ruff format --check .
	npm run lint

# Run P0 eval subset
evals:
	python evals/run_evals.py

# Load fixtures and create demo workspace
seed:
	@echo "Seeding demo data..."
	cd backend && python -m backend.seed
