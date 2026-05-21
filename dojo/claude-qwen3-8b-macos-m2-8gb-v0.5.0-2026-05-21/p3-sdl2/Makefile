# Compile with SDL2
CFLAGS = $(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --libs)

line_renderer: main.c
	gcc $(CFLAGS) $(LDFLAGS) -o line_renderer main.c