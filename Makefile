.PHONY: build install

build:
	go build -o bin/mu ./cmd/mu

install: build
	ln -sf $(PWD)/bin/mu $(HOME)/.local/bin/mu
