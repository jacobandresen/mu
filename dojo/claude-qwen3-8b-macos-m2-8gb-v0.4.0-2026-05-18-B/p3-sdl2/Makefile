CC = gcc
CFLAGS = $(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --libs)

line_renderer: src/main.c
	gcc $(CFLAGS) $(LDFLAGS) -o line_renderer src/main.c
LDFLAGS = $(shell sdl2-config --ldflags)

line_renderer: src/main.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o line_renderer src/main.c

clean:
	rm -f line_renderer