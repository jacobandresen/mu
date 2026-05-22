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
        "SDL Line Renderer",
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
    SDL_LockSurface(screen);
    SDL_FillRect(screen, NULL, SDL_MapRGBA(screen->format, 255, 255, 255, 255));
    SDL_UnlockSurface(screen);


    // Main loop
    int quit = 0;
    SDL_Event e;

    while (!quit) {
        // Handle events
        while (SDL_PollEvent(&e) != 0) {
            if (e.type == SDL_QUIT) {
                quit = 1;
            }
        }

        // Clear screen (set to black)
        SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
        SDL_RenderClear(renderer);

        // --- Draw a line ---
        // Define the line coordinates (e.g., a diagonal line)
        SDL_Point start = { 50, 50 };
        SDL_Point end = { SCREEN_WIDTH - 50, SCREEN_HEIGHT - 50 };

        // Set drawing color (e.g., red)
        SDL_SetRenderDrawColor(renderer, 255, 0, 0, 255);

        // Draw the line
        SDL_RenderDrawLine(renderer, start.x, start.y, end.x, end.y);

        // Update screen
        SDL_RenderPresent(renderer);
    }

    // Cleanup
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();

    return 0;
}