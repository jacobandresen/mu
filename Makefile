.PHONY: install deps

install:
	ln -sf $(PWD)/bin/mu $(HOME)/.local/bin/mu

deps:
	pip3 install --break-system-packages -e .
