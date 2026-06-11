/* Headless pixel-level test for draw_line().
 *
 * Run with SDL_VIDEODRIVER=offscreen (set by the Makefile test target).
 * Creates a software-rendered window, calls draw_line(), reads pixels back
 * via SDL_RenderReadPixels, and asserts that at least MIN_LINE_PIXELS
 * non-black pixels were drawn.
 */
#include <SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include "draw_line.h"

#define WIDTH           320
#define HEIGHT          240
#define MIN_LINE_PIXELS 30

int main(void) {
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
        return 1;
    }

    SDL_Window *win = SDL_CreateWindow("test",
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        WIDTH, HEIGHT, SDL_WINDOW_HIDDEN);
    if (!win) {
        fprintf(stderr, "SDL_CreateWindow: %s\n", SDL_GetError());
        SDL_Quit();
        return 1;
    }

    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_SOFTWARE);
    if (!ren) {
        fprintf(stderr, "SDL_CreateRenderer: %s\n", SDL_GetError());
        SDL_DestroyWindow(win);
        SDL_Quit();
        return 1;
    }

    SDL_SetRenderDrawColor(ren, 0, 0, 0, 255);
    SDL_RenderClear(ren);

    draw_line(ren);
    SDL_RenderPresent(ren);

    SDL_Surface *surf = SDL_CreateRGBSurfaceWithFormat(
        0, WIDTH, HEIGHT, 32, SDL_PIXELFORMAT_ARGB8888);
    if (!surf) {
        fprintf(stderr, "SDL_CreateRGBSurfaceWithFormat: %s\n", SDL_GetError());
        SDL_DestroyRenderer(ren);
        SDL_DestroyWindow(win);
        SDL_Quit();
        return 1;
    }
    SDL_RenderReadPixels(ren, NULL, SDL_PIXELFORMAT_ARGB8888,
                         surf->pixels, surf->pitch);

    int colored = 0;
    Uint32 *px = (Uint32 *)surf->pixels;
    for (int i = 0; i < WIDTH * HEIGHT; i++) {
        if ((px[i] & 0x00FFFFFF) != 0)
            colored++;
    }

    SDL_FreeSurface(surf);
    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();

    if (colored < MIN_LINE_PIXELS) {
        fprintf(stderr, "FAIL: %d non-black pixel(s), expected >= %d\n",
                colored, MIN_LINE_PIXELS);
        return 1;
    }
    printf("OK: %d non-black pixels — line confirmed.\n", colored);
    return 0;
}
