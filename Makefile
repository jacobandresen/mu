.PHONY: install deps venv openvino

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

# Install OpenVINO stack and download the right Mistral model.
# NPU detected  →  int4 channel-wise (Meteor Lake NPU-optimised)
# CPU/GPU       →  int4 asymmetric
# Safe to re-run: skips the ~3.6 GB download if the model is already present.
openvino: venv
	@echo "==> OpenVINO setup"
	@.venv/bin/pip install --quiet -e '.[openvino]'
	@.venv/bin/python scripts/setup_openvino.py --yes

# deps: full setup including OpenVINO on Intel Linux.
deps: venv
	@if grep -q "GenuineIntel" /proc/cpuinfo 2>/dev/null; then \
	    $(MAKE) --no-print-directory openvino; \
	fi

install: venv
