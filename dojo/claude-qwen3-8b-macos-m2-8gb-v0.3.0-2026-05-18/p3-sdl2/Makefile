CC = clang
CFLAGS = $(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --libs)

all: main

main: src/main.c
	$(CC) $(CFLAGS) src/main.c -o main $(LDFLAGS)

test: tests/test_main.c
	$(CC) $(CFLAGS) tests/test_main.c -o test_main $(LDFLAGS)

clean:
	rm -f main test_main
