.PHONY: install deps venv

# Create a local .venv and install mu in editable mode with dev extras.
# Symlinks .venv/bin/mu into ~/.local/bin so `mu` is on PATH without
# activating the venv. Works on Linux and macOS.
venv:
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
	mkdir -p $(HOME)/.local/bin
	ln -sf $(CURDIR)/.venv/bin/mu $(HOME)/.local/bin/mu
	@echo "Linked: ~/.local/bin/mu -> $(CURDIR)/.venv/bin/mu"
	@case ":$$PATH:" in \
	  *":$(HOME)/.local/bin:"*) echo "mu is ready — run: mu check" ;; \
	  *) echo "NOTE: add ~/.local/bin to PATH, then run: mu check" \
	        "\n  bash/zsh: echo 'export PATH=\"\$$HOME/.local/bin:\$$PATH\"' >> ~/.zshrc" ;; \
	esac

deps: venv

install: venv
