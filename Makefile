.PHONY: setup dev dev-backend dev-frontend build test compile check analyze clean

setup:
	./setup.sh

dev:
	./dev.sh

dev-backend:
	./scripts/dev_backend.sh

dev-frontend:
	./scripts/dev_frontend.sh

build:
	cd frontend && npm run build

test:
	uv run python -m unittest discover -s tests

compile:
	uv run python -m compileall -q topaz_us backend diagnostics tests

check: compile test build

analyze:
	uv run python -m topaz_us.analysis.daily

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	find . -name "*.pyc" -delete
