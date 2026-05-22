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
  gcc -Wall -Wextra -std=c99 -I/opt/homebrew/include/SDL2 -D_THREAD_SAFE -c main.c -o main.o
  main.c:71:5: error: call to undeclared function 'SDL_DestroySurface'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     71 |     SDL_DestroySurface(screen);
        |     ^
  main.c:7:14: warning: unused parameter 'argc' [-Wunused-parameter]
  ```
- test repair attempt 2 — still failing. Error:
  ```
  gcc -Wall -Wextra -std=c99 -I/opt/homebrew/include/SDL2 -D_THREAD_SAFE -c main.c -o main.o
  main.c:71:5: error: call to undeclared function 'SDL_DestroySurface'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     71 |     SDL_DestroySurface(screen);
        |     ^
  main.c:7:14: warning: unused parameter 'argc' [-Wunused-parameter]
  ```
- test repair attempt 1 — still failing. Error:
  ```
  gcc -Wall -Wextra -std=c99 -I/opt/homebrew/include/SDL2 -D_THREAD_SAFE -c main.c -o main.o
  main.c:71:5: error: call to undeclared function 'SDL_DestroySurface'; ISO C99 and later do not support implicit function declarations [-Wimplicit-function-declaration]
     71 |     SDL_DestroySurface(screen);
        |     ^
  main.c:7:14: warning: unused parameter 'argc' [-Wunused-parameter]
  ```
