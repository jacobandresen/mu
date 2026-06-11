## Summary
Implement `draw_line(SDL_Renderer *ren)` in draw_line.c using SDL2.
The renderer is already cleared to black; draw a non-black line of at least
30 pixels using SDL_SetRenderDrawColor + SDL_RenderDrawLine.
The test harness (provided), Makefile (provided), and header (provided) are
already in place — only draw_line.c needs to be written.

## Files
- [ ] draw_line.c — implement `void draw_line(SDL_Renderer *ren)` as declared in draw_line.h
- [x] draw_line.h — API header (provided)
- [x] test_line.c — headless pixel test harness (provided)
- [x] Makefile — build and test rules using sdl2-config (provided)

## Test Command
make test

## Dependencies
clang>=14, make>=4, sdl2
