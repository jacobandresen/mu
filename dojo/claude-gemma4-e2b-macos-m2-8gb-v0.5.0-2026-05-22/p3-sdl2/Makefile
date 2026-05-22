CC = gcc
CFLAGS = -Wall -Wextra -std=c11 $(shell sdl2-config --cflags)
LDFLAGS = -lSDL2 -lm $(shell sdl2-config --libs)

SRC = main.c

all: line_renderer

line_renderer: main.o
	$(CC) $(CFLAGS) $^ -o $@ $(LDFLAGS)