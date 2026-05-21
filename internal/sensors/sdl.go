package sensors

import (
	"os"
	"path/filepath"
	"strings"
)

// IsSDLSource reports whether f is a C/C++ source file that may include SDL2 headers.
func IsSDLSource(f string) bool {
	ext := strings.ToLower(filepath.Ext(f))
	return ext == ".c" || ext == ".cpp" || ext == ".cc" || ext == ".cxx"
}

// FixSDLInclude rewrites SDL2/SDL.h includes to SDL.h. Homebrew on macOS installs SDL2
// headers directly under the include path, so #include <SDL2/SDL.h> fails while
// #include <SDL.h> works.
func FixSDLInclude(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	orig := string(data)
	fixed := strings.ReplaceAll(orig, `#include <SDL2/SDL.h>`, `#include <SDL.h>`)
	fixed = strings.ReplaceAll(fixed, `#include "SDL2/SDL.h"`, `#include <SDL.h>`)
	if fixed == orig {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(fixed), 0644)
}

// FixSDLDestroySurface replaces SDL3's SDL_DestroySurface with SDL2's SDL_FreeSurface.
// Models trained on mixed SDL2/SDL3 data sometimes emit the SDL3 API which is absent in SDL2.
func FixSDLDestroySurface(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	orig := string(data)
	fixed := strings.ReplaceAll(orig, "SDL_DestroySurface(", "SDL_FreeSurface(")
	if fixed == orig {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(fixed), 0644)
}

// FixSDLMissingInclude adds #include <SDL.h> at the top of a C/C++ file that uses
// SDL_ symbols but has no SDL include. Models sometimes write the function body
// without the header.
func FixSDLMissingInclude(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	orig := string(data)
	if strings.Contains(orig, "#include") && strings.Contains(orig, "SDL") {
		return false, nil // has some include, let FixSDLInclude handle it
	}
	if !strings.Contains(orig, "SDL_") {
		return false, nil // no SDL symbols, nothing to fix
	}
	return true, os.WriteFile(f, []byte("#include <SDL.h>\n"+orig), 0644)
}
