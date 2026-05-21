CC=gcc
CFLAGS=-Wall -Wextra -std=c99
LDFLAGS=-lSDL2
SDL_CFLAGS=$(sdl2-config)

TARGET=line_renderer
SOURCES=main.c

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CC) $(CFLAGS) $(SOURCES) -o $(TARGET) $(LDFLAGS)

clean:
	rm -f $(TARGET)