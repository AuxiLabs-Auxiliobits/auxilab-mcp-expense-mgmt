# Convenience targets. Every one is a single command you can also run directly — the
# right-hand column of `make help` is literally what each target executes, so nothing here
# is required to work on the project.
#
# `make` itself is not installed by default on Windows. The recipes below avoid rm, find,
# grep and sed and shell out to Python instead, so they behave identically on Windows,
# macOS and Linux wherever make *is* available (Git Bash, WSL, nmake alternatives, or a
# package manager). If you have no make, run the underlying commands directly.
.PHONY: help install demo cli mcp test coverage lint lint-enterprise fmt samples screenshots build clean

help:            ## show this help
	@python -c "import re,sys;[print(f'{m[1]:<16} {m[2]}') for l in open('Makefile',encoding='utf-8') if (m:=re.match(r'^([a-z-]+):.*?## (.*)$$',l))]"

install:         ## pip install -r requirements-dev.txt
	pip install -r requirements-dev.txt

demo:            ## python app.py            (browser UI on http://127.0.0.1:7860)
	python app.py

cli:             ## python cli.py            (terminal demo, no browser)
	python cli.py

mcp:             ## python mcp_server.py     (MCP server over stdio)
	python mcp_server.py

test:            ## pytest
	pytest

coverage:        ## pytest --cov --cov-report=html
	pytest --cov --cov-report=term --cov-report=html
	@python -c "print('HTML report: htmlcov/index.html')"

lint:            ## ruff check . && ruff format --check .
	ruff check .
	ruff format --check .

lint-enterprise: ## ruff check enterprise --select F --isolated   (archived code, defects only)
	ruff check enterprise --select F --isolated

fmt:             ## ruff format . && ruff check --fix .
	ruff format .
	ruff check --fix .

samples:         ## python demo/generate_samples.py
	python demo/generate_samples.py

screenshots:     ## python docs/capture_screenshots.py   (needs playwright + pillow)
	python docs/capture_screenshots.py

build:           ## python -m build && twine check dist/*
	python -m build
	python -m twine check dist/*

clean:           ## delete caches, build output and the local database
	@python -c "import shutil,pathlib,itertools;[shutil.rmtree(p,ignore_errors=True) for p in ['.pytest_cache','.ruff_cache','.gradio','htmlcov','dist','build']];[p.unlink(missing_ok=True) for p in map(pathlib.Path,['coverage.xml','junit.xml','.coverage'])];[p.unlink(missing_ok=True) for p in pathlib.Path('local_db').glob('sqlite.db*')];[shutil.rmtree(p,ignore_errors=True) for p in itertools.chain(pathlib.Path('.').rglob('__pycache__'),pathlib.Path('.').rglob('*.egg-info')) if '.venv' not in str(p)];print('cleaned')"
