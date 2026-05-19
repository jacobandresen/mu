## Files
- [x] Makefile
- [x] src/main.c — SDL2 program to render a line

## Test Command
make

## Dependencies
- gcc
- sdl2-config
- clang-tidy
```

## Repair History
- final test gate: all retries exhausted — still failing. Error:
  ```
  Usage: /opt/homebrew/bin/sdl2-config [--prefix[=DIR]] [--exec-prefix[=DIR]] [--version] [--cflags] [--libs] [--static-libs]
  gcc -o line_renderer src/main.c 
  src/main.c:1:3: error: invalid preprocessing directive
      1 | # Line Renderer with SDL2
        |   ^
  ```
- test repair attempt 1 — still failing. Error:
  ```
  Usage: /opt/homebrew/bin/sdl2-config [--prefix[=DIR]] [--exec-prefix[=DIR]] [--version] [--cflags] [--libs] [--static-libs]
  gcc -o line_renderer src/main.c 
  src/main.c:1:10: fatal error: 'SDL.h' file not found
      1 | #include <SDL.h>
        |          ^~~~~~~
  ```
