package sensors

import (
	"os"
	"os/exec"
	"strings"
)

// FixMultilineSingleQuote fixes Python files where the model used a single-quoted string
// spanning multiple lines inside an execute() call. Python rejects multi-line single-quoted
// strings with "missing closing quote in string literal". Replaces the delimiter with triple quotes.
func FixMultilineSingleQuote(filePath, lintError string) bool {
	if !strings.HasSuffix(filePath, ".py") {
		return false
	}
	if !strings.Contains(lintError, "invalid-syntax") {
		return false
	}
	data, err := os.ReadFile(filePath)
	if err != nil {
		return false
	}
	lines := strings.Split(string(data), "\n")
	changed := false
	i := 0
	result := make([]string, 0, len(lines))
	for i < len(lines) {
		line := lines[i]
		idx := strings.Index(line, ".execute('")
		if idx >= 0 {
			openPos := idx + len(".execute(") // position of the opening '
			rest := line[openPos+1:]          // content after the opening '
			if !strings.Contains(rest, "'") {
				// Multi-line single-quoted string: replace opening ' with """
				line = line[:openPos] + `"""` + line[openPos+1:]
				result = append(result, line)
				i++
				for i < len(lines) {
					inner := lines[i]
					stripped := strings.TrimSpace(inner)
					if strings.HasSuffix(stripped, "'')") {
						closeIdx := strings.LastIndex(inner, "'')")
						inner = inner[:closeIdx] + `""")` + inner[closeIdx+3:]
						changed = true
						result = append(result, inner)
						i++
						break
					} else if strings.HasSuffix(stripped, "')") {
						closeIdx := strings.LastIndex(inner, "')")
						inner = inner[:closeIdx] + `""")` + inner[closeIdx+2:]
						changed = true
						result = append(result, inner)
						i++
						break
					}
					result = append(result, inner)
					i++
				}
				continue
			}
		}
		result = append(result, line)
		i++
	}
	if !changed {
		return false
	}
	return os.WriteFile(filePath, []byte(strings.Join(result, "\n")), 0644) == nil
}

// FixMissingCloseParen fixes Python files where conn.execute("""...""" is missing the
// closing ')'. The model sometimes writes triple-quoted strings correctly but forgets
// the closing paren, leaving the call unclosed and causing invalid-syntax at the next statement.
func FixMissingCloseParen(filePath, lintError string) bool {
	if !strings.HasSuffix(filePath, ".py") {
		return false
	}
	if !strings.Contains(lintError, "invalid-syntax") {
		return false
	}
	data, err := os.ReadFile(filePath)
	if err != nil {
		return false
	}
	lines := strings.Split(string(data), "\n")
	changed := false
	for i, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed != `"""` {
			continue
		}
		// Check if there's an open .execute(""" above this line without a matching )
		open := false
		for j := i - 1; j >= 0; j-- {
			prev := lines[j]
			if strings.Contains(prev, `.execute("""`) && !strings.Contains(prev, `""")`) {
				open = true
				break
			}
			if strings.Contains(prev, `""")`) {
				break
			}
		}
		if open {
			lines[i] = line + ")"
			changed = true
		}
	}
	if !changed {
		return false
	}
	return os.WriteFile(filePath, []byte(strings.Join(lines, "\n")), 0644) == nil
}

// RuffAutoFix runs "ruff check --fix" on filePath when ruff is available.
// Returns true if ruff ran (regardless of whether it changed anything).
func RuffAutoFix(filePath string) bool {
	if _, err := exec.LookPath("ruff"); err != nil {
		return false
	}
	if !strings.HasSuffix(strings.ToLower(filePath), ".py") {
		return false
	}
	exec.Command("ruff", "check", "--fix", "--select=E9,F", filePath).Run()
	return true
}
