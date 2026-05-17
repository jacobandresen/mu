CFLAGS += $(shell sdl2-config --cflags)
LDFLAGS += $(shell sdl2-config --libs)

all: main

main: main.c
	clang $(CFLAGS) -o main main.c $(LDFLAGS)

.PHONY: clean

clean:
	rm -f main