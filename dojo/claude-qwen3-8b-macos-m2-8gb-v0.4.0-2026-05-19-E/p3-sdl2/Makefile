CC = gcc
CFLAGS = $(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --libs)$(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --ldflags)
TARGET = line_renderer

all: $(TARGET)

$(TARGET): src/main.c
	$(CC) -o $(TARGET) src/main.c $(LDFLAGS)

clean:
	rm -f $(TARGET)