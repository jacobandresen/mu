package sensors

import (
	"os"
	"regexp"
	"strings"
)

// moduleHostRe matches the start of a valid Go module hostname inside a path.
// Used to strip accidental leading characters (e.g. "hgithub.com/..." → "github.com/...").
var moduleHostRe = regexp.MustCompile(`(?i)(github\.com|golang\.org|gopkg\.in|k8s\.io|sigs\.k8s\.io|go\.uber\.org|gonum\.org|cloud\.google\.com)/`)

func stripModulePrefix(s string) string {
	if loc := moduleHostRe.FindStringIndex(s); loc != nil && loc[0] > 0 {
		return s[loc[0]:]
	}
	return s
}

// FixGoMod detects go.mod files where the model wrote bare "pkg version" lines instead of
// wrapping them in a require block. Bare lines with a "/" in the module path are moved into
// a require block; bare names without "/" (e.g. "gin v1.9.1") are dropped — they are
// unresolvable and would produce a malformed require block.
func FixGoMod(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	lines := strings.Split(string(data), "\n")
	validDirectives := map[string]bool{
		"module": true, "go": true, "require": true, "replace": true,
		"exclude": true, "retract": true, "toolchain": true, "//": true, "": true,
	}
	var kept []string
	var bareReqs []string
	dropped := false
	inBlock := false
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "//") {
			kept = append(kept, line)
			continue
		}
		if strings.HasSuffix(trimmed, "(") {
			inBlock = true
			kept = append(kept, line)
			continue
		}
		if trimmed == ")" {
			inBlock = false
			kept = append(kept, line)
			continue
		}
		if inBlock {
			fields := strings.Fields(trimmed)
			if len(fields) >= 2 && !strings.Contains(fields[0], "/") && strings.Contains(fields[1], "/") {
				// Space-separated spurious prefix: "h github.com/foo v1.2.3" → strip first token
				kept = append(kept, "\t"+strings.Join(fields[1:], " "))
				dropped = true
			} else if len(fields) >= 1 {
				// Concatenated spurious prefix: "hgithub.com/foo v1.2.3" → strip leading char(s)
				if fixed := stripModulePrefix(fields[0]); fixed != fields[0] {
					fields[0] = fixed
					kept = append(kept, "\t"+strings.Join(fields, " "))
					dropped = true
				} else {
					kept = append(kept, line)
				}
			} else {
				kept = append(kept, line)
			}
			continue
		}
		first := strings.Fields(trimmed)[0]
		if validDirectives[first] {
			kept = append(kept, line)
		} else if strings.Contains(first, "/") {
			// Bare "github.com/foo/bar v1.2.3" line — valid module path, collect as require
			bareReqs = append(bareReqs, "\t"+trimmed)
		} else {
			// Unknown directive (e.g. "testmod", "tools") — drop it
			dropped = true
		}
	}
	if len(bareReqs) == 0 && !dropped {
		return false, nil
	}
	result := strings.Join(kept, "\n")
	result = strings.TrimRight(result, "\n")
	if len(bareReqs) > 0 {
		result += "\n\nrequire (\n" + strings.Join(bareReqs, "\n") + "\n)\n"
	} else {
		result += "\n"
	}
	return true, os.WriteFile(f, []byte(result), 0644)
}

// FixGoMakefile ensures Go Makefiles run 'go mod init' and 'go get' BEFORE 'go build'.
// Models commonly generate the build target with 'go build' first and dependency setup after,
// which fails because the module isn't initialized when the build runs.
func FixGoMakefile(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	content := string(data)

	if !strings.Contains(content, "go build") {
		return false, nil
	}

	goBuildIdx := strings.Index(content, "go build")
	goModIdx := strings.Index(content, "go mod")
	goGetIdx := strings.Index(content, "go get")

	if (goModIdx >= 0 && goModIdx < goBuildIdx) || (goGetIdx >= 0 && goGetIdx < goBuildIdx) {
		return false, nil
	}

	lines := strings.Split(content, "\n")
	fixed := false
	var out []string
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if len(line) > 0 && line[0] == '\t' {
			if !fixed && strings.HasPrefix(trimmed, "go build") {
				out = append(out, "\ttest -f go.mod || go mod init server")
				out = append(out, "\tgo mod tidy || go get ./...")
				fixed = true
			}
		}
		out = append(out, line)
	}

	if !fixed {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(strings.Join(out, "\n")), 0644)
}

// knownVersions maps module paths to their pinned stable version.
// Used by FixGoModVersions to correct hallucinated or non-existent version tags.
var knownVersions = map[string]string{
	"github.com/gin-gonic/gin": "v1.9.1",
}

// FixGoModVersions replaces known-bad module versions with pinned stable ones.
// Models sometimes hallucinate version numbers (e.g. gin v1.9.2 which does not exist).
func FixGoModVersions(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	content := string(data)
	changed := false
	for mod, pinned := range knownVersions {
		// Match "github.com/foo/bar vX.Y.Z" where vX.Y.Z is NOT the pinned version
		re := regexp.MustCompile(`(?m)(` + regexp.QuoteMeta(mod) + `)\s+(v[0-9]+\.[0-9]+\.[0-9]+[^\s]*)`)
		content = re.ReplaceAllStringFunc(content, func(match string) string {
			parts := re.FindStringSubmatch(match)
			if len(parts) >= 3 && parts[2] != pinned {
				changed = true
				return parts[1] + " " + pinned
			}
			return match
		})
	}
	if !changed {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(content), 0644)
}
