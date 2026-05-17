build:
	test -f go.mod || go mod init server
	go mod tidy 2>/dev/null || go get ./... 2>/dev/null || true
	go build -o bin/ping-server

run:
	go run main.go

test:
	go vet
	go test -race

all: build run
