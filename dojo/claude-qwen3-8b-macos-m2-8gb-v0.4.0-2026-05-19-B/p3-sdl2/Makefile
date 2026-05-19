CC = gcc
CFLAGS = $(shell sdl2-config --cflags)
LDLIBS = $(shell sdl2-config --libs)

sdl_line: main.c
	$(CC) $(CFLAGS) -o sdl_line main.c $(LDLIBS)

clean:
	rm -f sdl_line