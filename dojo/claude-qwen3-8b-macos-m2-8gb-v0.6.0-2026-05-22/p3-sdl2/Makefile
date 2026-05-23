CC = clang
CFLAGS = -I/opt/homebrew/include/SDL2 -D_THREAD_SAFE
LDFLAGS = -L/opt/homebrew/lib -lSDL2

main: main.c
	$(CC) $(CFLAGS) -o main main.c $(LDFLAGS)

run: main
	./main