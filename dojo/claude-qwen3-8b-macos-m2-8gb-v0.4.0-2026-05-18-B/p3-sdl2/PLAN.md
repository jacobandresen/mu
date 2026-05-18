## Files
- [x] Makefile
- [x] src/main.c — C program to render a line using SDL2

## Test Command
make

## Dependencies
- gcc (C compiler)
- sdl2-config (SDL2 setup tool)
- clang-tidy (C linting)
```

## Repair History
- final test gate: all retries exhausted — still failing. Error:
  ```
  "_SDL_DestroyRenderer", referenced from:
        _main in main-5e770d.o
    "_SDL_DestroyWindow", referenced from:
        _main in main-5e770d.o
        _main in main-5e770d.o
  ```
- test repair attempt 1 — still failing. Error:
  ```
  "_SDL_DestroyRenderer", referenced from:
        _main in main-96ba8c.o
    "_SDL_DestroyWindow", referenced from:
        _main in main-96ba8c.o
        _main in main-96ba8c.o
  ```
