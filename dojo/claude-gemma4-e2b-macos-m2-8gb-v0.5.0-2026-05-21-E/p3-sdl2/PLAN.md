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
  Makefile:2: *** missing separator.  Stop.
  ```
- test repair attempt 2 — still failing. Error:
  ```
  gcc -Wall -Wextra -std=c99 -I/usr/include/SDL2 -c main.c -o main.o
  main.c:1:10: fatal error: 'SDL.h' file not found
      1 | #include <SDL.h>
        |          ^~~~~~~
  1 error generated.
  ```
- test repair attempt 1 — still failing. Error:
  ```
  Makefile:16: warning: overriding commands for target `all'
  Makefile:4: warning: ignoring old commands for target `all'
  make: *** No rule to make target `line_renderer', needed by `all'.  Stop.
  ```
