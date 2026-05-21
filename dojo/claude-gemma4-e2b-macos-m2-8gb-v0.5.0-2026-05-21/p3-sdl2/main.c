#include <SDL.h>
#include <SDL2/SDL_video.h>
#include <SDL2/SDL_timer.h>

#define SCREEN_WIDTH 640
#define SCREEN_HEIGHT 480

int main(int argc, char* argv[]) {
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        SDL_Log(SDL_LOG_CATEGORY_DEFAULT, "SDL_Init failed: %s", SDL_GetError());
        return 1;
    }

    SDL_Window* window = SDL_CreateWindow("SDL2 Line Renderer",
                                          SDL_WINDOWPOS_UNDEFINED,
                                          SDL_WINDOWPOS_UNDEFINED,
                                          SCREEN_WIDTH,
                                          SCREEN_HEIGHT,
                                          SDL_WINDOW_SHOWN);

    if (window == NULL) {
        SDL_Log(SDL_LOG_CATEGORY_DEFAULT, "SDL_CreateWindow failed: %s", SDL_GetError());
        SDL_Quit();
        return 1;
    }

    SDL_Surface* screen = SDL_CreateRGBSurface(0, SCREEN_WIDTH, SCREEN_HEIGHT, 32, 0, 0, 0, 0);

    // Fill the surface with a background color (e.g., black)
    SDL_FillRect(screen, NULL, SDL_MapRGBA(screen->format, 0, 0, 0, 255));

    // Create a renderer from the surface
    SDL_Renderer* renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);

    if (renderer == NULL) {
        SDL_Log(SDL_LOG_CATEGORY_DEFAULT, "SDL_CreateRenderer failed: %s", SDL_GetError());
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    // Set the renderer draw color (e.g., red)
    SDL_SetRenderDrawColor(renderer, 255, 0, 0, 255);

    // Render the line (example: a diagonal line)
    SDL_RenderClear(renderer);

    // Draw a line from (0, 0) to (SCREEN_WIDTH, SCREEN_HEIGHT)
    SDL_RenderDrawLine(renderer, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);

    // Update the screen
    SDL_RenderPresent(renderer);

    // Wait for a key press to close the window
    SDL_Event e;
    SDL_Delay(1000); // Keep window open for a moment
    SDL_PollEvent(&e);
    if (e.type == SDL_QUIT) {
        break;
    }

    // Clean up
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();

    return 0;
}