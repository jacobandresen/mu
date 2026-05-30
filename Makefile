.PHONY: install deps venv check

# Editable install into the active venv (run after `python3 -m venv .venv && source .venv/bin/activate`).
# Never installs into the system Python — use a venv or pipx.
install:
	pip install -e '.[dev]'

# Create a local .venv and install mu in editable mode with dev extras.
venv:
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
	@echo "Activate with: source .venv/bin/activate"

# Back-compat alias.
deps: install
