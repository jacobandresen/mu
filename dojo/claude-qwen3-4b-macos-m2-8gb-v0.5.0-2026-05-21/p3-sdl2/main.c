/*
 * main.c - Render a line on screen using SDL2
 *
 * This file demonstrates how to render a line on screen using SDL2.
 * It initializes SDL, creates a window, and draws a line using SDL's
 * rendering API.
 */

#include <SDL.h>

int main(int argc, char* argv[]) {
    // Initialize SDL
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "SDL could not initialize! SDL_Error: %s\n", SDL_GetError());
        return 1;
    }

    // Create a window
    SDL_Window* window = SDL_CreateWindow(
        "SDL2 Line Example",
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        800,
        600,
        SDL_WINDOW_SHOWN
    );

    if (!window) {
        fprintf(stderr, "Window could not be created! SDL_Error: %s\n", SDL_GetError());
        SDL_Quit();
        return 1;
    }

    // Create a renderer
    SDL_Renderer* renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
    if (!renderer) {
        fprintf(stderr, "Renderer could not be created! SDL_Error: %s\n", SDL_GetError());
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    // Set render target to the window
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);

    // Clear the screen
    SDL_RenderClear(renderer);

    // Draw a line from (100, 100) to (700, 500)
    SDL_SetRenderDrawColor(renderer, 255, 0, 0, 255);
    SDL_RenderDrawLine(renderer, 100, 100, 700, 500);

    // Present the rendered content
    SDL_RenderPresent(renderer);

    // Wait a bit to see the result
    SDL_Delay(3000);

    // Cleanup
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();

    return 0;
}
