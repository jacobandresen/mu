run:
	go run main.go

build:
	go build -o server

format:
	protofmt -w .
	rg -all -i -f .
	protofmt -w .

lint:
	gofmt -s -d .
	golint .
	rg -all -i -f .
	protofmt -w .

install:
	go install

watch:
	go run main.go
	watch -n 1 "go run main.go"
