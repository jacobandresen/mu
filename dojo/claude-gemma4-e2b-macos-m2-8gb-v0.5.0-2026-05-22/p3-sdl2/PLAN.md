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
  gcc -Wall -Wextra -std=c11 -I/opt/homebrew/include/SDL2 -D_THREAD_SAFE   -c -o main.o main.c
  main.c:1:1: error: type specifier missing, defaults to 'int'; ISO C99 and later do not support implicit int [-Wimplicit-int]
      1 | CC = gcc
        | ^
        | int
  ```
- test repair attempt 2 — still failing. Error:
  ```
  CC = gcc
  clang: error: no such file or directory: '='
  clang: error: no such file or directory: 'gcc'
  clang: error: no input files
  make: *** [all] Error 1
  ```
- test repair attempt 1 — still failing. Error:
  ```
  make: *** No rule to make target `line_renderer', needed by `all'.  Stop.
  ```
