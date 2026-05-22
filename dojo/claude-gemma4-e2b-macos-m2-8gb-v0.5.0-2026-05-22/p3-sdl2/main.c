CC = gcc
CFLAGS = -Wall -Wextra -std=c11
LDFLAGS = -lSDL2

SRCS = main.c
OBJS = $(SRCS:.c=.o)
TARGET = line_renderer

$(TARGET): $(OBJS)
	$(CC) $(OBJS) -o $(TARGET) $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

main.c =
#include <SDL.h>
#include <stdio.h>

int main(int argc, char *argv[]) {
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "SDL could not be initialized! SDL_Error: %s\n", SDL_GetError());
        return 1;
    }

    // Set screen resolution
    int screen_width = 640;
    int screen_height = 480;

    // Create a window
    SDL_Window *window = SDL_CreateWindow("SDL2 Line Renderer",
                                          SDL_WINDOWPOS_UNDEFINED,
                                          SDL_WINDOWPOS_UNDEFINED,
                                          screen_width,
                                          screen_height,
                                          SDL_WINDOW_SHOWN);

    if (window == NULL) {
        fprintf(stderr, "Window could not be created! SDL_Error: %s\n", SDL_GetError());
        SDL_Quit();
        return 1;
    }

    // Create a renderer
    SDL_Renderer *renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
    if (renderer == NULL) {
        fprintf(stderr, "Renderer could not be created! SDL_Error: %s\n", SDL_GetError());
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    // Set draw color (e.g., white)
    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
    SDL_RenderClear(renderer);

    // Draw a line (e.g., a diagonal line)
    SDL_SetRenderDrawColor(renderer, 255, 0, 0, 255); // Red color
    SDL_RenderDrawLine(renderer, 0, 0, screen_width, screen_height);

    // Update screen
    SDL_RenderPresent(renderer);

    // Wait for user input and close window
    SDL_Delay(3000); // Wait for 3 seconds
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();

    return 0;
}