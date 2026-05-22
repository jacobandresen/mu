# Makefile for SDL2 line renderer
CC = gcc
CFLAGS = -I/opt/homebrew/include/SDL2 -D_THREAD_SAFE
LDFLAGS = -L/opt/homebrew/lib -lSDL2

line_renderer: main.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o line_renderer main.c