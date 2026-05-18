package sensors

import (
	"os"
	"regexp"
	"strings"
)

// FixNoTargets detects a Makefile written as a plain shell script (no `target:` lines)
// and wraps the commands in a default `all:` target with tab-indented recipes.
// This happens when the model writes a Makefile like a shell script instead of proper make syntax.
func FixNoTargets(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	content := string(data)
	targetRE := regexp.MustCompile(`(?m)^[a-zA-Z_.][a-zA-Z0-9._-]*\s*:`)
	if targetRE.MatchString(content) {
		return false, nil
	}
	lines := strings.Split(strings.TrimRight(content, "\n"), "\n")
	var recipes []string
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		recipes = append(recipes, "\t"+trimmed)
	}
	if len(recipes) == 0 {
		return false, nil
	}
	result := ".DEFAULT_GOAL := all\n\nall:\n" + strings.Join(recipes, "\n") + "\n"
	return true, os.WriteFile(f, []byte(result), 0644)
}

// FixInlineRecipe fixes Makefiles where the model put the recipe on the same line as the
// target (e.g. "build: go build -o server"). BSD make interprets everything after the colon
// as prerequisites, not a recipe, and triggers implicit rules (e.g. m2c for .mod files).
// Splits such lines into target + tab-indented recipe on the next line.
func FixInlineRecipe(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	lines := strings.Split(string(data), "\n")
	changed := false
	var out []string
	knownTargets := map[string]bool{
		"all": true, "clean": true, "install": true, "test": true,
		"build": true, "run": true, "format": true, "lint": true,
		"check": true, "release": true, "debug": true, "help": true,
	}
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if len(line) > 0 && line[0] != '\t' && !strings.HasPrefix(trimmed, "#") &&
			!strings.HasPrefix(trimmed, ".") && !strings.Contains(trimmed, "=") {
			colonIdx := strings.Index(trimmed, ":")
			if colonIdx > 0 && colonIdx < len(trimmed)-1 {
				target := strings.TrimSpace(trimmed[:colonIdx])
				afterColon := strings.TrimSpace(trimmed[colonIdx+1:])
				if knownTargets[target] && strings.Contains(afterColon, " ") &&
					!strings.HasPrefix(afterColon, "=") {
					out = append(out, target+":")
					out = append(out, "\t"+afterColon)
					changed = true
					continue
				}
			}
		}
		out = append(out, line)
	}
	if !changed {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(strings.Join(out, "\n")), 0644)
}

// FixDuplicateVar detects when the same Makefile variable is assigned more than once
// at the top level (e.g. LDFLAGS defined twice). This happens when the model repeats
// a corrected assignment instead of replacing the first one. Keeps the first definition
// and removes subsequent duplicates.
func FixDuplicateVar(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	varRE := regexp.MustCompile(`^([A-Z_][A-Z0-9_]*)\s*[?:+]?=`)
	lines := strings.Split(string(data), "\n")
	seen := map[string]bool{}
	changed := false
	var out []string
	for _, line := range lines {
		if m := varRE.FindStringSubmatch(line); m != nil {
			if seen[m[1]] {
				changed = true
				continue
			}
			seen[m[1]] = true
		}
		out = append(out, line)
	}
	if !changed {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(strings.Join(out, "\n")), 0644)
}
