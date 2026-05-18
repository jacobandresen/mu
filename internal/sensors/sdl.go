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
