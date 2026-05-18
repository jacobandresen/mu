package sensors

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/jacobandresen/mu/internal/plan"
)

// FixRustPrintlnFormat fixes Rust files where the model wrote println!({}...) with an
// unquoted format string. The correct form is println!("{}", value). The error appears
// as "expected ',', found identifier" at the position after the unquoted '{}'.
func FixRustPrintlnFormat(filePath, lintError string) bool {
	if !strings.HasSuffix(filePath, ".rs") {
		return false
	}
	if !strings.Contains(lintError, "expected `,`") {
		return false
	}
	data, err := os.ReadFile(filePath)
	if err != nil {
		return false
	}
	// Replace println!({...}, with println!("{...}",
	re := regexp.MustCompile(`(println!|eprintln!|print!|eprint!|format!|write!|writeln!)\((\{[^"]*?\})`)
	fixed := re.ReplaceAllString(string(data), `$1("$2"`)
	if fixed == string(data) {
		return false
	}
	return os.WriteFile(filePath, []byte(fixed), 0644) == nil
}

// FixCargoTomlOrphanLib removes a [lib] section from Cargo.toml when the referenced
// source file does not exist. qwen3:8b sometimes adds [lib] path = "src/lib.rs" to
// binary-only projects, causing "can't find lib" errors from cargo.
func FixCargoTomlOrphanLib(cargoPath string) (bool, error) {
	data, err := os.ReadFile(cargoPath)
	if err != nil {
		return false, err
	}
	content := string(data)
	if !strings.Contains(content, "[lib]") {
		return false, nil
	}

	libPath := "src/lib.rs"
	libPathRe := regexp.MustCompile(`(?m)^\s*path\s*=\s*"([^"]+)"`)
	libSection := extractTOMLSection(content, "[lib]")
	if m := libPathRe.FindStringSubmatch(libSection); len(m) > 1 {
		libPath = m[1]
	}

	fullPath := filepath.Join(filepath.Dir(cargoPath), libPath)
	if _, statErr := os.Stat(fullPath); statErr == nil {
		return false, nil // file exists, leave it alone
	}

	sectionRe := regexp.MustCompile(`(?ms)\[lib\][^\[]*`)
	fixed := sectionRe.ReplaceAllString(content, "")
	fixed = strings.TrimSpace(fixed) + "\n"
	return true, os.WriteFile(cargoPath, []byte(fixed), 0644)
}

// FixCargoTomlOrphanLibOnRust is the lint-failure trigger for Rust source files: when
// cargo reports "can't find lib", walks up to the nearest Cargo.toml and removes the
// orphan [lib] section.
func FixCargoTomlOrphanLibOnRust(filePath, lintHead string) bool {
	if !strings.HasSuffix(filePath, ".rs") {
		return false
	}
	if !strings.Contains(lintHead, "can't find lib") {
		return false
	}
	dir := filepath.Dir(filePath)
	for {
		candidate := filepath.Join(dir, "Cargo.toml")
		if _, err := os.Stat(candidate); err == nil {
			fixed, _ := FixCargoTomlOrphanLib(candidate)
			return fixed
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return false
}

// FixMissingCargoToml injects a minimal Cargo.toml task into PLAN.md when the test
// command uses cargo but no Cargo.toml appears in the file list. Without Cargo.toml,
// every cargo command fails immediately with "could not find Cargo.toml".
func FixMissingCargoToml(planFile string, p *plan.Plan) bool {
	if p == nil || !strings.Contains(strings.ToLower(p.TestCommand), "cargo") {
		return false
	}
	for _, t := range p.Tasks {
		if strings.EqualFold(filepath.Base(t.FilePath), "cargo.toml") {
			return false
		}
	}

	pkgName := "app"
	for _, t := range p.Tasks {
		if strings.HasSuffix(t.FilePath, ".rs") {
			pkgName = strings.TrimSuffix(filepath.Base(t.FilePath), ".rs")
			break
		}
	}

	cargoContent := fmt.Sprintf("[package]\nname = \"%s\"\nversion = \"0.1.0\"\nedition = \"2021\"\n", pkgName)
	if err := os.WriteFile("Cargo.toml", []byte(cargoContent), 0644); err != nil {
		return false
	}

	data, err := os.ReadFile(planFile)
	if err != nil {
		return false
	}
	content := string(data)
	filesIdx := strings.Index(content, "## Files")
	if filesIdx < 0 {
		return false
	}
	afterHeader := content[filesIdx:]
	firstTask := strings.Index(afterHeader, "\n- [")
	if firstTask < 0 {
		return false
	}
	insertAt := filesIdx + firstTask + 1
	entry := "- [x] Cargo.toml — cargo project manifest (auto-injected)\n"
	content = content[:insertAt] + entry + content[insertAt:]
	return os.WriteFile(planFile, []byte(content), 0644) == nil
}

func extractTOMLSection(content, header string) string {
	idx := strings.Index(content, header)
	if idx < 0 {
		return ""
	}
	rest := content[idx+len(header):]
	nextSection := regexp.MustCompile(`\n\[`)
	loc := nextSection.FindStringIndex(rest)
	if loc != nil {
		return rest[:loc[0]]
	}
	return rest
}
