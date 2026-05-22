#include <SDL.h>
#include <stdio.h>

#define SCREEN_WIDTH 640
#define SCREEN_HEIGHT 480

int main(int argc, char* argv[]) {
    // Initialize SDL
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        printf("SDL could not be initialized! SDL_Error: %s\n", SDL_GetError());
        return 1;
    }

    // Create window
    SDL_Window* window = SDL_CreateWindow(
        "SDL2 Line Renderer",
        SDL_WINDOWPOS_UNDEFINED,
        SDL_WINDOWPOS_UNDEFINED,
        SCREEN_WIDTH,
        SCREEN_HEIGHT,
        SDL_WINDOW_SHOWN
    );

    if (window == NULL) {
        printf("Window could not be created! SDL_Error: %s\n", SDL_GetError());
        SDL_Quit();
        return 1;
    }

    // Create renderer
    SDL_Renderer* renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
    if (renderer == NULL) {
        printf("Renderer could not be created! SDL_Error: %s\n", SDL_GetError());
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    // Set drawing color (e.g., white)
    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);

    // Create a surface to draw on (optional, but good practice for rendering)
    SDL_Surface* screen = SDL_CreateRGBSurface(0, SCREEN_WIDTH, SCREEN_HEIGHT, 32, 0, 0, 0, 0);
    if (!screen) {
        printf("Failed to create surface: %s\n", SDL_GetError());
        SDL_DestroyRenderer(renderer);
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    // Clear screen to a background color (e.g., black)
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    SDL_RenderClear(renderer);

    // --- Render a line ---
    // Define the line coordinates (e.g., from (10, 10) to (SCREEN_WIDTH-10, SCREEN_HEIGHT-10))
    SDL_Point start = { 10, 10 };
    SDL_Point end = { SCREEN_WIDTH - 10, SCREEN_HEIGHT - 10 };

    // Set the drawing color for the line (e.g., red)
    SDL_SetRenderDrawColor(renderer, 255, 0, 0, 255);

    // Draw the line using SDL_RenderDrawLine
    SDL_RenderDrawLine(renderer, start.x, start.y, end.x, end.y);

    // Update screen
    SDL_RenderPresent(renderer);

    // Clean up resources
    SDL_FreeSurface(screen);
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();

    return 0;
}