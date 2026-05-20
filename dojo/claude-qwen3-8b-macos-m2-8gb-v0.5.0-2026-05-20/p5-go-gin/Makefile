build:
	go build -o ping
run:
	./ping
format:
	protofmt -w .
lint:
	gofmt -s -w .
	golint ./...
	go vet ./...
	go test -v ./...
	go mod tidy