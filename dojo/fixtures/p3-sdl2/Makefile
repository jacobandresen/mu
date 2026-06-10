CC      = clang
CFLAGS  = $(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --libs)

.PHONY: all test clean

all: test_line

test_line: draw_line.c test_line.c draw_line.h
	$(CC) $(CFLAGS) -o $@ draw_line.c test_line.c $(LDFLAGS)

test: test_line
	SDL_VIDEODRIVER=dummy ./test_line

clean:
	rm -f test_line
