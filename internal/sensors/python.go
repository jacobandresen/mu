package sensors

import (
	"os"
	"os/exec"
	"path/filepath"
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

// FixTestImportModule fixes test files that import from a module that doesn't exist on disk
// but a similarly-named module does. Common when the model names the test import differently
// from the implementation file (e.g. "from todo_manager import ..." but only "todo.py" exists).
// Scans "from X import ..." lines and replaces X with the actual .py filename when X.py is absent
// but a .py file in the same directory shares enough name characters with X.
func FixTestImportModule(filePath string) (bool, error) {
	if !strings.HasSuffix(filePath, ".py") {
		return false, nil
	}
	base := strings.ToLower(strings.TrimSuffix(filePath, ".py"))
	if !strings.HasPrefix(base, "test_") && !strings.HasSuffix(base, "_test") {
		return false, nil // only applies to test files
	}
	data, err := os.ReadFile(filePath)
	if err != nil {
		return false, err
	}
	content := string(data)
	dir := filepath.Dir(filePath)

	// Collect non-test .py files in the same directory
	entries, err := os.ReadDir(dir)
	if err != nil {
		return false, nil
	}
	var candidates []string
	for _, e := range entries {
		n := e.Name()
		if !strings.HasSuffix(n, ".py") || strings.HasPrefix(n, "test_") || strings.HasSuffix(n, "_test.py") {
			continue
		}
		candidates = append(candidates, strings.TrimSuffix(n, ".py"))
	}

	changed := false
	lines := strings.Split(content, "\n")
	for i, line := range lines {
		trimmed := strings.TrimSpace(line)
		if !strings.HasPrefix(trimmed, "from ") && !strings.HasPrefix(trimmed, "import ") {
			continue
		}
		// Extract module name from "from MODULE import ..." or "import MODULE"
		var moduleName string
		if strings.HasPrefix(trimmed, "from ") {
			parts := strings.Fields(trimmed)
			if len(parts) >= 2 {
				moduleName = parts[1]
			}
		} else {
			parts := strings.Fields(trimmed)
			if len(parts) >= 2 {
				moduleName = strings.Split(parts[1], ".")[0]
			}
		}
		if moduleName == "" {
			continue
		}
		// Check if module exists
		if _, err := os.Stat(filepath.Join(dir, moduleName+".py")); err == nil {
			continue // module exists, no fix needed
		}
		// Find best matching candidate
		best := ""
		for _, cand := range candidates {
			// Match if the module name and candidate share a significant prefix/substring
			ml := strings.ToLower(moduleName)
			cl := strings.ToLower(cand)
			if strings.HasPrefix(ml, cl) || strings.HasPrefix(cl, ml) ||
				strings.Contains(ml, cl) || strings.Contains(cl, ml) {
				best = cand
				break
			}
		}
		if best == "" || best == moduleName {
			continue
		}
		lines[i] = strings.ReplaceAll(line, moduleName, best)
		changed = true
	}
	if !changed {
		return false, nil
	}
	return true, os.WriteFile(filePath, []byte(strings.Join(lines, "\n")), 0644)
}

// FixSQLiteInitDb detects Python sqlite3 modules where a table-init function (create_table,
// initialize_db, init_db, setup_db, etc.) exists but is only called inside
// "if __name__ == '__main__'". When tests import the module directly that block never runs,
// so all DB operations fail with "no such table". Adds a module-level call after the function.
func FixSQLiteInitDb(filePath string) (bool, error) {
	if !strings.HasSuffix(filePath, ".py") {
		return false, nil
	}
	// Skip test files — they import from the module; the call belongs in the module, not tests.
	base := strings.ToLower(strings.TrimSuffix(filePath, ".py"))
	if strings.HasPrefix(base, "test_") || strings.HasSuffix(base, "_test") {
		return false, nil
	}
	data, err := os.ReadFile(filePath)
	if err != nil {
		return false, err
	}
	content := string(data)
	if !strings.Contains(content, "sqlite3") {
		return false, nil
	}

	// Find candidate init function name
	initNames := []string{"create_table", "initialize_db", "init_db", "setup_db", "create_tables", "init_database"}
	funcName := ""
	for _, name := range initNames {
		if strings.Contains(content, "def "+name+"(") {
			funcName = name
			break
		}
	}
	if funcName == "" {
		return false, nil
	}

	// Already called at module scope (outside __main__)?
	// Search for an unindented standalone call like "\nfoo()" rather than
	// "def foo()" which also contains "foo()" as a substring.
	mainIdx := strings.Index(content, "if __name__")
	standaloneCall := "\n" + funcName + "()"
	callSite := strings.Index(content, standaloneCall)
	if callSite >= 0 && (mainIdx < 0 || callSite < mainIdx) {
		return false, nil // already at module scope
	}

	// Find the end of the function definition to insert after it
	defLine := "def " + funcName + "("
	defIdx := strings.Index(content, defLine)
	if defIdx < 0 {
		return false, nil
	}
	// Walk past the function body by finding the next top-level def/class or __main__
	rest := content[defIdx+len(defLine):]
	insertAfter := defIdx + len(defLine)
	for _, marker := range []string{"\ndef ", "\nclass ", "\nif __name__"} {
		idx := strings.Index(rest, marker)
		if idx >= 0 {
			candidate := defIdx + len(defLine) + idx
			if candidate > insertAfter {
				insertAfter = candidate
			}
			break
		}
	}
	// Insert a module-level call right before the next top-level construct
	insert := "\n" + funcName + "()\n"
	fixed := content[:insertAfter] + insert + content[insertAfter:]
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
