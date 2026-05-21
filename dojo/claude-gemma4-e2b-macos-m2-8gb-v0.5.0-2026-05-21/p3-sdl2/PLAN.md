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
  gcc -Wall -Wextra -std=c99 main.c -o line_renderer -lSDL2
  main.c:1:10: fatal error: 'SDL.h' file not found
      1 | #include <SDL.h>
        |          ^~~~~~~
  1 error generated.
  ```
- test repair attempt 2 — still failing. Error:
  ```
  gcc -Wall -Wextra -std=c99 main.c -o line_renderer -lSDL2
  main.c:1:10: fatal error: 'SDL.h' file not found
      1 | #include <SDL.h>
        |          ^~~~~~~
  1 error generated.
  ```
- test repair attempt 1 — still failing. Error:
  ```
  gcc -Wall -Wextra -std=c99 main.c -o line_renderer -lSDL2
  main.c:1:10: fatal error: 'SDL.h' file not found
      1 | #include <SDL.h>
        |          ^~~~~~~
  1 error generated.
  ```
