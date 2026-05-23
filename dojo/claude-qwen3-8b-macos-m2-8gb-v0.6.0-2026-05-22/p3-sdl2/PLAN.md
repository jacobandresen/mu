## Files
- [x] main.c — SDL2 program to render a line on screen

## Test Command
make run

## Dependencies
Makefile
```

## Files
- [x] Makefile — Makefile to compile and run the SDL2 program using sdl2-config
```

## Files
- [x] main.c — SDL2 program to render a line on screen
```

## Dependencies
sdl2-config
```

## Test Command
make run
````

## Repair History
- final test gate: all retries exhausted — still failing. Error:
  ```
  clang -I/opt/homebrew/include/SDL2 -D_THREAD_SAFE -o main main.c -L/opt/homebrew/lib -lSDL2
  main.c:1:10: fatal error: 'SDL2/SDL.h' file not found
      1 | #include <SDL2/SDL.h>
        |          ^~~~~~~~~~~~
  1 error generated.
  ```
- test repair attempt 2 — still failing. Error:
  ```
  make: *** No rule to make target `run'.  Stop.
  ```
- test repair attempt 1 — still failing. Error:
  ```
  clang -I/opt/homebrew/include/SDL2 -D_THREAD_SAFE -o main main.c -L/opt/homebrew/lib -lSDL2
  main.c:1:10: fatal error: 'SDL2/SDL.h' file not found
      1 | #include <SDL2/SDL.h>
        |          ^~~~~~~~~~~~
  1 error generated.
  ```
