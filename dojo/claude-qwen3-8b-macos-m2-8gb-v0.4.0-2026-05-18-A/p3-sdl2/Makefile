# Makefile for SDL2 line drawing
CFLAGS = $(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --libs)

sdl_line: main.c
	gcc $(CFLAGS) $(LDFLAGS) -o $@ $< -lm