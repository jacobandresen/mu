---
name: sdl2-writer
description: SDL2 C program rules — correct Makefile flags, initialization sequence, and event loop. Apply to any task that uses SDL2.
---

## Makefile flags

Use `sdl2-config` to get the correct flags for the current platform:

```makefile
CFLAGS  = $(shell sdl2-config --cflags)
LDFLAGS = $(shell sdl2-config --libs)

sdl2_app: main.c
	cc $(CFLAGS) -o sdl2_app main.c $(LDFLAGS)
```

**Critical rules:**
- Use `cc` or `clang` as the compiler — never just `c` (that is not a valid compiler name).
- Never add a bare `-L` or `-I` before `$(shell sdl2-config --libs/--cflags)` — the output already contains the full flag (e.g. `-L/opt/homebrew/lib -lSDL2`). Adding `-L` before it produces `-L -L/path` which the linker rejects.
- Never use `\t` as an escape sequence in Makefile variable values or recipes — it is not interpreted as a tab character. Use real whitespace.
- Always put `$(LDFLAGS)` **after** the source file in the compile command — linkers are order-sensitive.
- The binary target name must match what the test command runs (e.g. `./sdl2_line`).

## SDL2 initialization sequence

**Use `#include <SDL.h>`** when building with `$(shell sdl2-config --cflags)` — `sdl2-config` already sets `-I/.../include/SDL2` so the plain `<SDL.h>` resolves correctly. Do not use `<SDL2/SDL.h>` with sdl2-config flags (that would look for `SDL2/SDL2/SDL.h` which doesn't exist).

```c
#include <SDL.h>

int main(int argc, char *argv[]) {
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "SDL_Init error: %s\n", SDL_GetError());
        return 1;
    }

    SDL_Window *win = SDL_CreateWindow("Title",
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        640, 480, SDL_WINDOW_SHOWN);
    if (!win) {
        SDL_Quit();
        return 1;
    }

    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_ACCELERATED);
    if (!ren) {
        SDL_DestroyWindow(win);
        SDL_Quit();
        return 1;
    }

    /* draw here */
    SDL_SetRenderDrawColor(ren, 0, 0, 0, 255);
    SDL_RenderClear(ren);
    SDL_SetRenderDrawColor(ren, 255, 255, 255, 255);
    SDL_RenderDrawLine(ren, 0, 0, 640, 480);
    SDL_RenderPresent(ren);
    SDL_Delay(1000);

    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
```

## Common errors and fixes

- `Undefined symbols: _SDL_CreateWindow` etc. — linker can't find SDL2. The `$(shell sdl2-config --libs)` expansion produced empty or `-L` only. Verify the Makefile has `LDFLAGS = $(shell sdl2-config --libs)` with no prefix, and that `$(LDFLAGS)` appears after the source file.
- `sdl2-config: command not found` — SDL2 not installed. On macOS: `brew install sdl2`. On Linux: `apt install libsdl2-dev`.
- `SDL.h: No such file or directory` — missing `$(shell sdl2-config --cflags)` in CFLAGS.
- `SDL_WINDOWPOS_CENTERED` not found — include `<SDL.h>` (which is the correct form when using sdl2-config).
