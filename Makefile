.PHONY: help activate test lint clean build publish publish-test

# Default target
help:
	@echo "Available targets:"
	@echo "  make activate     - Create venv and install dev dependencies"
	@echo "  make lint         - Run linters/formatters"
	@echo "  make clean        - Clean up test artifacts"
	@echo "  make build        - Build distribution packages"
	@echo "  make publish-test - Upload to TestPyPI"
	@echo "  make publish      - Upload to PyPI"

# Setup dev environment
activate:
	@echo "Setting up development environment..."
	python3 -m venv venv
	venv/bin/pip install -e ".[dev]"
	@echo "Done!"

# Format and lint code
lint:
	venv/bin/black .
	venv/bin/ruff check .
	venv/bin/yamllint -c .yamllint.yaml .github/

# Clean up test artifacts
clean:
	@echo "Cleaning up test artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@rm -rf dist/ build/ *.egg-info/
	@echo "Cleanup completed!"

# Build distribution packages
build: clean
	venv/bin/python -m build

# Upload to PyPI
publish: build
	venv/bin/twine upload dist/*
