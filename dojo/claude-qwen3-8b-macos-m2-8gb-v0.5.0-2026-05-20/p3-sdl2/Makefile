CC = gcc
CFLAGS = $(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --libs)

line: main.c
	$(CC) $(CFLAGS) -o line main.c $(LDFLAGS)