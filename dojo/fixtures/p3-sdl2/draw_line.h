#pragma once
#include <SDL.h>

/*
 * draw_line — draw a visible line on an SDL2 renderer.
 *
 * The renderer has already been cleared to black (RGB 0, 0, 0).
 * Use SDL_SetRenderDrawColor to choose a non-black color, then
 * SDL_RenderDrawLine to draw at least one line spanning 30+ pixels.
 * Do NOT call SDL_RenderPresent — the test harness calls it.
 */
void draw_line(SDL_Renderer *ren);
