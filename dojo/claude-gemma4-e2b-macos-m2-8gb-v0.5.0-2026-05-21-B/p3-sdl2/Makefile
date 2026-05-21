CC=gcc
CFLAGS=-Wall -Wextra -std=c99 $(shell sdl2-config --cflags)
LDFLAGS=-lSDL2 $(shell sdl2-config --libs)
SRCS=main.c
OBJS=$(SRCS:.c=.o)
TARGET=sdl_line_renderer

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(OBJS) -o $(TARGET) $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)