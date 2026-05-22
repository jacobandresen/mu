build:
	test -f go.mod || go mod init server
	go mod tidy || go get ./...
	go build -o ping .