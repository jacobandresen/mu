---
name: sdl2-writer
description: SDL2 C program rules — correct Makefile flags, initialization sequence, event loop, and pixel-level testing without headless drivers.
---

## Project structure

Split the drawing logic out of `main.c` so `test_render.c` can test it independently:

- **`draw.h`** — the drawing function (header-only with `static inline`)
- **`main.c`** — window setup, calls `draw_scene`, event loop
- **`test_render.c`** — uses `SDL_CreateSoftwareRenderer` for pixel verification; no display or special driver needed

## Makefile

```makefile
CFLAGS  = $(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --libs)

all: sdl2_line test_render

sdl2_line: main.c draw.h
	cc $(CFLAGS) -o sdl2_line main.c $(LDFLAGS)

test_render: test_render.c draw.h
	cc $(CFLAGS) -o test_render test_render.c $(LDFLAGS)
```

**Critical rules:**
- Use `cc` or `clang` — never just `c`.
- Never prefix `$(shell sdl2-config --libs/--cflags)` with a bare `-L` or `-I`.
- Never use `\t` as an escape sequence in Makefile recipes — use real tab characters.
- Always put `$(LDFLAGS)` **after** the source file — linkers are order-sensitive.

## draw.h — the scene

```c
#pragma once
#include <SDL.h>

static inline void draw_scene(SDL_Renderer *ren, int w, int h) {
    SDL_SetRenderDrawColor(ren, 0, 0, 0, 255);
    SDL_RenderClear(ren);
    SDL_SetRenderDrawColor(ren, 255, 255, 255, 255);
    SDL_RenderDrawLine(ren, 0, 0, w - 1, h - 1);
    SDL_RenderPresent(ren);
}
```

## main.c — interactive window

**Use `#include <SDL.h>`** with sdl2-config — it already sets `-I/.../include/SDL2`. Do not use `<SDL2/SDL.h>`.

```c
#include <SDL.h>
#include <stdio.h>
#include "draw.h"

#define W 640
#define H 480

int main(int argc, char *argv[]) {
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "SDL_Init error: %s\n", SDL_GetError());
        return 1;
    }

    SDL_Window *win = SDL_CreateWindow("Title",
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        W, H, SDL_WINDOW_SHOWN);
    if (!win) { SDL_Quit(); return 1; }

    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, 0);
    if (!ren) { SDL_DestroyWindow(win); SDL_Quit(); return 1; }

    draw_scene(ren, W, H);

    /* keep window open; auto-exit after 3 s of inactivity */
    SDL_Event e;
    while (SDL_WaitEventTimeout(&e, 3000))
        if (e.type == SDL_QUIT || e.type == SDL_KEYDOWN) break;

    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
```

## test_render.c — pixel verification

`SDL_CreateSoftwareRenderer` renders into a CPU surface with no display driver involvement — no `SDL_VIDEODRIVER=dummy` needed. Use `SDL_PIXELFORMAT_ARGB8888` (24-bit surfaces may silently produce blank output with some SDL builds).

```c
#include <SDL.h>
#include <stdio.h>
#include "draw.h"

#define W 640
#define H 480

static Uint32 get_pixel(SDL_Surface *s, int x, int y) {
    Uint8 *p = (Uint8 *)s->pixels + y * s->pitch + x * 4;
    return *(Uint32 *)p;
}

static int is_white(SDL_Surface *s, int x, int y) {
    SDL_Color c;
    SDL_GetRGBA(get_pixel(s, x, y), s->format, &c.r, &c.g, &c.b, &c.a);
    return c.r > 200 && c.g > 200 && c.b > 200;
}

static int is_dark(SDL_Surface *s, int x, int y) {
    SDL_Color c;
    SDL_GetRGBA(get_pixel(s, x, y), s->format, &c.r, &c.g, &c.b, &c.a);
    return c.r < 50 && c.g < 50 && c.b < 50;
}

int main(void) {
    SDL_Init(0);

    SDL_Surface *surf = SDL_CreateRGBSurfaceWithFormat(0, W, H, 32, SDL_PIXELFORMAT_ARGB8888);
    if (!surf) { fprintf(stderr, "surface: %s\n", SDL_GetError()); return 1; }

    SDL_Renderer *ren = SDL_CreateSoftwareRenderer(surf);
    if (!ren) { fprintf(stderr, "renderer: %s\n", SDL_GetError()); return 1; }

    draw_scene(ren, W, H);
    SDL_DestroyRenderer(ren);

    /* diagonal hit rate */
    int n = W < H ? W : H;
    int hits = 0;
    for (int i = 0; i < n; i++) {
        int x = i * (W - 1) / (n - 1);
        int y = i * (H - 1) / (n - 1);
        if (is_white(surf, x, y)) hits++;
    }
    if (hits * 100 / n < 50) {
        fprintf(stderr, "FAIL: only %d%% diagonal pixels are white\n", hits * 100 / n);
        SDL_FreeSurface(surf); SDL_Quit(); return 1;
    }

    /* background: midpoints of each edge are clearly off the diagonal */
    int dark = is_dark(surf,W/2,1) + is_dark(surf,W/2,H-2) +
               is_dark(surf,1,H/2) + is_dark(surf,W-2,H/2);
    if (dark < 3) {
        fprintf(stderr, "FAIL: background not dark (%d/4)\n", dark);
        SDL_FreeSurface(surf); SDL_Quit(); return 1;
    }

    printf("PASS: %d%% of %d diagonal pixels white; background dark\n",
           hits * 100 / n, n);
    SDL_FreeSurface(surf);
    SDL_Quit();
    return 0;
}
```

**Test command:**
```
make && ./test_render
```

No headless driver, no Python, no BMP files. The real window opens when you run `./sdl2_line`.

## Common errors and fixes

- `Undefined symbols: _SDL_CreateWindow` — `$(LDFLAGS)` must appear after the source file, not before.
- `sdl2-config: command not found` — macOS: `brew install sdl2`; Linux: `apt install libsdl2-dev`.
- `SDL.h: No such file or directory` — missing `$(CFLAGS)` in compile command.
- `SDL_CreateSoftwareRenderer` produces all-black pixels — surface format was 24-bit; use `SDL_PIXELFORMAT_ARGB8888` (32-bit).
