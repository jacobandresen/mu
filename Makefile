.PHONY: install deps

# Editable install: generates the `mu` console script on PATH and pulls the
# runtime dependencies declared in pyproject.toml (httpx, lmstudio, inquirerpy,
# pyflakes, autoflake).
install:
	pip3 install --break-system-packages -e .

# Back-compat alias — the editable install above already installs deps.
deps: install
