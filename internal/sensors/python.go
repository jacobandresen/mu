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

// FixSQLiteBareListCursor fixes two recurring SQLite list bugs the model produces together:
//
//  Bug 1 — empty cursor in ternary:
//    cursor = conn.execute(q, params) if cond else conn.cursor()
//  conn.cursor() with no query returns [], silently breaking list methods.
//  Fixed by simplifying to: cursor = conn.execute(query)
//
//  Bug 2 — dict(row) on plain tuple rows:
//    return [dict(row) for row in cursor.fetchall()]
//  sqlite3 returns tuples by default; dict() on a tuple raises TypeError.
//  Fixed by replacing with: return list(cursor.fetchall())
func FixSQLiteBareListCursor(filePath string) (bool, error) {
	if !strings.HasSuffix(filePath, ".py") {
		return false, nil
	}
	data, err := os.ReadFile(filePath)
	if err != nil {
		return false, err
	}
	content := string(data)
	if !strings.Contains(content, ".cursor()") {
		return false, nil
	}
	lines := strings.Split(content, "\n")
	changed := false
	for i, line := range lines {
		trimmed := strings.TrimSpace(line)
		indent := line[:len(line)-len(strings.TrimLeft(line, " \t"))]

		// Bug 1: cursor = obj.execute(q, params) if cond else obj.cursor()
		if strings.Contains(trimmed, ".cursor()") && strings.Contains(trimmed, ".execute(") {
			elseIdx := strings.Index(trimmed, " if ")
			executeIdx := strings.Index(trimmed, ".execute(")
			if elseIdx > 0 && executeIdx >= 0 && executeIdx < elseIdx {
				beforeIf := strings.TrimSpace(trimmed[:elseIdx])
				execOpen := strings.Index(beforeIf, ".execute(")
				depth, closeAt := 0, -1
				for j := execOpen + len(".execute(") - 1; j < len(beforeIf); j++ {
					if beforeIf[j] == '(' {
						depth++
					} else if beforeIf[j] == ')' {
						depth--
						if depth == 0 {
							closeAt = j
							break
						}
					}
				}
				if closeAt >= 0 {
					execInner := beforeIf[execOpen+len(".execute(") : closeAt]
					queryArg := execInner
					if ci := strings.Index(execInner, ", "); ci >= 0 {
						queryArg = strings.TrimSpace(execInner[:ci])
					}
					lhs := beforeIf[:execOpen]
					lines[i] = indent + lhs + ".execute(" + queryArg + ")"
					changed = true
					continue
				}
			}
		}

		// Bug 2: return [dict(row) for row in cursor.fetchall()]
		if strings.Contains(trimmed, "dict(row)") && strings.Contains(trimmed, "fetchall()") {
			lines[i] = indent + "return list(cursor.fetchall())"
			changed = true
		}
	}
	if !changed {
		return false, nil
	}
	return true, os.WriteFile(filePath, []byte(strings.Join(lines, "\n")), 0644)
}

// FixFlaskDbCreate detects Flask-SQLAlchemy apps where db.create_all() is only called
// inside "if __name__ == '__main__'" and adds a module-level call. When tests import the
// module, the __main__ block never runs so the tables are never created, causing all
// endpoint tests to fail with OperationalError.
func FixFlaskDbCreate(filePath string) (bool, error) {
	if !strings.HasSuffix(filePath, ".py") {
		return false, nil
	}
	data, err := os.ReadFile(filePath)
	if err != nil {
		return false, err
	}
	content := string(data)
	if !strings.Contains(content, "SQLAlchemy") {
		return false, nil
	}
	if !strings.Contains(content, "db.create_all()") {
		return false, nil
	}
	mainIdx := strings.Index(content, "if __name__")
	if mainIdx < 0 {
		return false, nil
	}
	createIdx := strings.Index(content, "db.create_all()")
	if createIdx < mainIdx {
		return false, nil // already at module scope
	}
	insert := "with app.app_context():\n    db.create_all()\n\n"
	fixed := content[:mainIdx] + insert + content[mainIdx:]
	return true, os.WriteFile(filePath, []byte(fixed), 0644)
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
