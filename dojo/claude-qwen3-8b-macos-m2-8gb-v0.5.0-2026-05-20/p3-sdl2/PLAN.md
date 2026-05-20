## Files
- [x] main.c — implementation
- [x] Makefile — build and link

## Test Command
make

## Dependencies
gcc or clang, SDL2

## Repair History
- final test gate: all retries exhausted — still failing. Error:
  ```
  gcc -I/opt/homebrew/include/SDL2 -D_THREAD_SAFE -o line main.c -L/opt/homebrew/lib -lSDL2
  main.c:2:5: error: use of undeclared identifier 'SDL_bool'
      2 |     SDL_bool running = SDL_TRUE;
        |     ^~~~~~~~
  main.c:3:12: error: use of undeclared identifier 'running'
  ```
- test repair attempt 1 — still failing. Error:
  ```
  gcc -I/opt/homebrew/include/SDL2 -D_THREAD_SAFE -o line main.c -L/opt/homebrew/lib -lSDL2
  main.c:17:5: error: use of undeclared identifier 'bool'
     17 |     bool running = true;
        |     ^~~~
  main.c:18:12: error: use of undeclared identifier 'running'
  ```
