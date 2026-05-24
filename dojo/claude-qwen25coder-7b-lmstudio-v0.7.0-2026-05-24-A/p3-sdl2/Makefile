CC = clang
CFLAGS = -Wall $(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --libs)

main: main.c
	$(CC) $(CFLAGS) -o main main.c $(LDFLAGS)
