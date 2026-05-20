package plan

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strings"
)

type Task struct {
	FilePath    string
	Description string
	Done        bool
	InProgress  bool
}

type Plan struct {
	Tasks       []Task
	TestCommand string
	PlanContext string // Files + Test Command + Dependencies sections
}

var taskRE = regexp.MustCompile(`^- \[([ x~])\] (\S+)(.*)$`)

func ParseContent(content string) (*Plan, error) {
	lines := strings.Split(content, "\n")
	p := &Plan{}
	for _, line := range lines {
		m := taskRE.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		t := Task{FilePath: m[2]}
		rest := strings.TrimSpace(m[3])
		if dash := strings.Index(rest, "—"); dash >= 0 {
			t.Description = strings.TrimSpace(rest[dash+len("—"):])
		} else if dash := strings.Index(rest, "-"); dash >= 0 {
			t.Description = strings.TrimSpace(rest[dash+1:])
		}
		switch m[1] {
		case "x":
			t.Done = true
		case "~":
			t.InProgress = true
		}
		p.Tasks = append(p.Tasks, t)
	}
	p.TestCommand = extractTestCommand(lines)
	p.PlanContext = extractPlanContext(lines)
	return p, nil
}

func Parse(path string) (*Plan, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	p := &Plan{}
	lines := strings.Split(string(data), "\n")

	// Extract tasks
	for _, line := range lines {
		m := taskRE.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		t := Task{FilePath: m[2]}
		rest := strings.TrimSpace(m[3])
		if dash := strings.Index(rest, "—"); dash >= 0 {
			t.Description = strings.TrimSpace(rest[dash+len("—"):])
		} else if dash := strings.Index(rest, "-"); dash >= 0 {
			t.Description = strings.TrimSpace(rest[dash+1:])
		}
		switch m[1] {
		case "x":
			t.Done = true
		case "~":
			t.InProgress = true
		}
		p.Tasks = append(p.Tasks, t)
	}

	p.TestCommand = extractTestCommand(lines)
	p.PlanContext = extractPlanContext(lines)
	return p, nil
}

func extractTestCommand(lines []string) string {
	inSection := false
	for _, line := range lines {
		if regexp.MustCompile(`^##\s+Test Command\s*$`).MatchString(line) {
			inSection = true
			continue
		}
		if inSection && strings.HasPrefix(line, "## ") {
			break
		}
		if inSection {
			trimmed := strings.TrimSpace(line)
			trimmed = strings.TrimPrefix(trimmed, "```")
			trimmed = strings.TrimSuffix(trimmed, "```")
			trimmed = strings.Trim(trimmed, "`")
			trimmed = strings.TrimSpace(trimmed)
			if trimmed != "" {
				return trimmed
			}
		}
	}
	return ""
}

func extractPlanContext(lines []string) string {
	wantSections := map[string]bool{"Files": true, "Test Command": true, "Dependencies": true, "Notes": true}
	var buf strings.Builder
	inSection := false
	for _, line := range lines {
		if m := regexp.MustCompile(`^## ([A-Za-z ]+)\s*$`).FindStringSubmatch(line); m != nil {
			inSection = wantSections[strings.TrimSpace(m[1])]
		}
		if inSection {
			buf.WriteString(line)
			buf.WriteByte('\n')
		}
	}
	return buf.String()
}

func NextTask(p *Plan) *Task {
	for i := range p.Tasks {
		if !p.Tasks[i].Done && !p.Tasks[i].InProgress {
			return &p.Tasks[i]
		}
	}
	return nil
}

func TasksRemaining(p *Plan) bool {
	return NextTask(p) != nil
}

func MarkTaskDone(path, filePath string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	lines := strings.Split(string(data), "\n")
	done := false
	for i, line := range lines {
		if done {
			break
		}
		m := taskRE.FindStringSubmatch(line)
		if m == nil || m[1] != " " {
			continue
		}
		if m[2] == filePath {
			lines[i] = "- [x] " + m[2] + m[3]
			done = true
		}
	}
	if !done {
		return fmt.Errorf("task not found in PLAN.md: %s", filePath)
	}
	return os.WriteFile(path, []byte(strings.Join(lines, "\n")), 0644)
}

var thinkingRE = regexp.MustCompile(`\s?/think\s?|\s?</?think(ing)?>\s?`)

func StripThinkingArtifacts(path string) (bool, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return false, err
	}
	cleaned := thinkingRE.ReplaceAllString(string(data), "")
	if cleaned == string(data) {
		return false, nil
	}
	return true, os.WriteFile(path, []byte(cleaned), 0644)
}

func CheckGoalAlignment(p *Plan, goal string) (bool, []string) {
	planText := strings.ToLower(p.PlanContext)
	goalLower := strings.ToLower(goal)
	stopwords := map[string]bool{
		// articles, prepositions, conjunctions
		"and": true, "the": true, "via": true, "with": true,
		"for": true, "from": true, "that": true, "this": true,
		"are": true, "not": true, "make": true, "into": true,
		"also": true, "both": true, "each": true, "just": true,
		"like": true, "more": true, "only": true, "over": true,
		"some": true, "such": true, "then": true, "when": true,
		"will": true, "have": true, "must": true, "been": true,
		"your": true, "them": true, "than": true, "even": true,
		// task-description verbs that appear in nearly every goal
		"write": true, "using": true, "create": true, "show": true,
		"include": true, "returns": true, "support": true, "runs": true,
		"provide": true, "list": true, "uses": true, "call": true,
		"print": true, "read": true, "take": true, "back": true,
		"work": true, "build": true, "adds": true, "does": true,
		"writes": true, "again": true, "program": true, "table": true,
		"contains": true, "inserted": true, "entry": true, "given": true,
		"should": true, "store": true, "data": true, "able": true,
	}

	var missing []string
	found := false
	re := regexp.MustCompile(`[a-z0-9]+`)
	for _, w := range re.FindAllString(goalLower, -1) {
		if len(w) < 4 || stopwords[w] {
			continue
		}
		if strings.Contains(planText, w) {
			found = true
		} else {
			missing = append(missing, w)
		}
	}
	return found, missing
}

func CountTasks(p *Plan) (total, done int) {
	for _, t := range p.Tasks {
		total++
		if t.Done {
			done++
		}
	}
	return
}

func RelevantFilesContext(p *Plan, target string) string {
	targetDir := dirOf(target)
	targetBase := baseOf(target)
	targetStem := stemOf(targetBase)
	moduleStem := strings.TrimPrefix(targetStem, "test_")

	var out strings.Builder
	count := 0
	max := 6
	for _, t := range p.Tasks {
		if count >= max {
			break
		}
		if !t.Done {
			continue
		}
		f := t.FilePath
		if _, err := os.Stat(f); err != nil {
			continue
		}
		fbase := baseOf(f)
		fext := extOf(fbase)
		fstem := stemOf(fbase)
		fdir := dirOf(f)

		include := false
		if fext == "h" || fext == "hpp" {
			include = true
		}
		if fdir == targetDir {
			include = true
		}
		if fstem == moduleStem {
			include = true
		}
		if !include {
			continue
		}
		data, err := os.ReadFile(f)
		if err != nil {
			continue
		}
		out.WriteString("### " + f + "\n```\n")
		out.Write(data)
		out.WriteString("\n```\n\n")
		count++
	}
	return out.String()
}

func PendingSourceFiles(p *Plan, current string) string {
	var out strings.Builder
	found := false
	for _, t := range p.Tasks {
		if t.Done || t.InProgress {
			continue
		}
		if t.FilePath == current {
			found = true
			continue
		}
		if found {
			out.WriteString("  " + t.FilePath + "\n")
		}
	}
	return out.String()
}

func IsBuildFile(name string) bool {
	base := baseOf(name)
	switch base {
	case "Makefile", "CMakeLists.txt", "setup.py", "Cargo.toml",
		"build.sh", "package.json", "pyproject.toml", "meson.build", "go.mod":
		return true
	}
	if strings.HasSuffix(name, ".csproj") {
		return true
	}
	return false
}

// HasPendingBuildFile returns true if any build file (Makefile, Cargo.toml, etc.) is still
// pending in the plan. Used to skip the inter-iteration test gate when the test command
// depends on a Makefile/build-system that hasn't been written yet.
func HasPendingBuildFile(p *Plan) bool {
	for _, t := range p.Tasks {
		if !t.Done && IsBuildFile(t.FilePath) {
			return true
		}
	}
	return false
}

// FixDotnetTestCommand rewrites the test command when dotnet is used without a .csproj
// in the file list. When the test command is "dotnet test" or bare "dotnet run" but no
// test project is listed, rewrites to "dotnet run --project <first-csproj>".
func FixDotnetTestCommand(planPath string, p *Plan) (bool, error) {
	cmd := strings.TrimSpace(p.TestCommand)
	isDotnetTest := cmd == "dotnet test" || strings.HasPrefix(cmd, "dotnet test ")
	isDotnetRun := cmd == "dotnet run" || strings.HasPrefix(cmd, "dotnet run ")
	if !isDotnetTest && !isDotnetRun {
		return false, nil
	}

	// Find the first .csproj in the file list
	var csproj string
	for _, t := range p.Tasks {
		if strings.HasSuffix(t.FilePath, ".csproj") {
			csproj = t.FilePath
			break
		}
	}
	if csproj == "" {
		return false, nil
	}

	// If test command already points to this csproj, nothing to do
	if strings.Contains(cmd, csproj) {
		return false, nil
	}

	// Rewrite bare "dotnet test" → "dotnet run --project <csproj>" for simple programs
	// (when no separate test .csproj exists, just run the program as the test)
	var newCmd string
	testCsproj := ""
	for _, t := range p.Tasks {
		if strings.HasSuffix(t.FilePath, ".csproj") && t.FilePath != csproj {
			testCsproj = t.FilePath
			break
		}
	}
	if testCsproj != "" {
		// Two csproj files: src + tests — use the test one
		newCmd = "dotnet test " + testCsproj
	} else {
		// Single csproj: run the program
		newCmd = "dotnet run --project " + csproj
	}

	data, err := os.ReadFile(planPath)
	if err != nil {
		return false, err
	}
	content := string(data)
	updated := strings.ReplaceAll(content, "\n"+cmd+"\n", "\n"+newCmd+"\n")
	if updated == content {
		return false, nil
	}
	return true, os.WriteFile(planPath, []byte(updated), 0644)
}

// NormalizeEmbeddedFiles extracts file content from plan sections like
// "## Makefile\n```makefile\n...\n```" that the model writes instead of
// listing them under ## Files. It writes the file to disk, adds it to the
// ## Files section as [x] (already done), and returns the list of filenames
// extracted.
func NormalizeEmbeddedFiles(planPath string) ([]string, error) {
	data, err := os.ReadFile(planPath)
	if err != nil {
		return nil, err
	}
	lines := strings.Split(string(data), "\n")

	// case-insensitive section names → canonical filename
	knownBuildFiles := map[string]string{
		"makefile": "Makefile", "cmakelists.txt": "CMakeLists.txt",
		"cargo.toml": "Cargo.toml", "build.sh": "build.sh",
		"package.json": "package.json", "pyproject.toml": "pyproject.toml",
	}

	type section struct{ name, content string }
	var extracted []section

	var currentSection string
	var inFence bool
	var fenceContent strings.Builder
	fenceRE := regexp.MustCompile("^```[a-zA-Z]*\\s*$")
	h2RE := regexp.MustCompile(`^## ([A-Za-z0-9._\-]+)\s*$`)

	for _, line := range lines {
		if m := h2RE.FindStringSubmatch(line); m != nil {
			rawName := m[1]
			if canonical, ok := knownBuildFiles[strings.ToLower(rawName)]; ok {
				currentSection = canonical
				inFence = false
				fenceContent.Reset()
				continue
			}
			currentSection = ""
			continue
		}
		if currentSection == "" {
			continue
		}
		if !inFence && fenceRE.MatchString(line) {
			inFence = true
			continue
		}
		if inFence && strings.TrimSpace(line) == "```" {
			extracted = append(extracted, section{name: currentSection, content: fenceContent.String()})
			currentSection = ""
			inFence = false
			fenceContent.Reset()
			continue
		}
		if inFence {
			fenceContent.WriteString(line)
			fenceContent.WriteByte('\n')
		}
	}

	if len(extracted) == 0 {
		return nil, nil
	}

	// Write extracted files to disk and patch PLAN.md
	var names []string
	planText := string(data)
	for _, s := range extracted {
		if err := os.WriteFile(s.name, []byte(s.content), 0644); err != nil {
			continue
		}
		names = append(names, s.name)

		// If not already listed in ## Files, add it as [x]
		taskLine := "- [x] " + s.name
		if !strings.Contains(planText, "- [ ] "+s.name) && !strings.Contains(planText, "- [x] "+s.name) {
			// Add after "## Files" header
			planText = strings.Replace(planText,
				"## Files\n",
				"## Files\n"+taskLine+" — auto-extracted from plan\n",
				1)
		} else {
			// Already listed — mark it done
			planText = strings.ReplaceAll(planText, "- [ ] "+s.name, "- [x] "+s.name)
		}
	}

	return names, os.WriteFile(planPath, []byte(planText), 0644)
}

// FixGraphicalTestCommand replaces test commands that run graphical binaries
// (matching the libRE patterns for SDL2, OpenGL, ncurses etc.) with a
// compile-only equivalent. Returns true if a replacement was made.
func FixGraphicalTestCommand(planPath string, goalIsGraphical bool) (bool, error) {
	if !goalIsGraphical {
		return false, nil
	}
	data, err := os.ReadFile(planPath)
	if err != nil {
		return false, err
	}
	lines := strings.Split(string(data), "\n")
	inTestCmd := false
	changed := false
	for i, line := range lines {
		if regexp.MustCompile(`^##\s+Test Command\s*$`).MatchString(line) {
			inTestCmd = true
			continue
		}
		if inTestCmd && strings.HasPrefix(line, "## ") {
			break
		}
		if inTestCmd {
			trimmed := strings.TrimSpace(line)
			if trimmed == "" {
				continue
			}
			// If the test command runs the binary (./binary or just binary), replace with make-only
			if isRunCommand(trimmed) {
				lines[i] = "make"
				changed = true
			}
			inTestCmd = false
		}
	}
	if !changed {
		return false, nil
	}
	return true, os.WriteFile(planPath, []byte(strings.Join(lines, "\n")), 0644)
}

func isRunCommand(cmd string) bool {
	// matches: make test, make run, ./foo, ./foo args, make && ./foo
	runRE := regexp.MustCompile(`(^|\|\||&&)\s*(\./[^\s]+|make\s+(test|run|exec))`)
	if runRE.MatchString(cmd) {
		return true
	}
	// pure "make" alone is fine (compile only)
	return false
}

// NormalizeTestCommand applies portable fixups to the test command:
//   - Replaces bare "python " with "python3 " so the command works in non-login
//     bash subprocesses where the "python" alias is not available.
func NormalizeTestCommand(planPath string) (bool, error) {
	data, err := os.ReadFile(planPath)
	if err != nil {
		return false, err
	}
	content := string(data)
	updated := content

	// python → python3 (modern systems; avoids alias-not-found in bash -c)
	// Replace both line-start and inline "python " (e.g. after "&&")
	updated = strings.ReplaceAll(updated, "\npython ", "\npython3 ")
	updated = strings.ReplaceAll(updated, "&& python ", "&& python3 ")
	updated = strings.ReplaceAll(updated, "| python ", "| python3 ")

	if updated == content {
		return false, nil
	}
	return true, os.WriteFile(planPath, []byte(updated), 0644)
}

// FixPythonMakefileTest rewrites pytest invocations in a Makefile to prepend
// PYTHONPATH=. so tests can import modules from the project root.
// Models frequently emit bare "pytest" which fails with ModuleNotFoundError when
// the test file does "import app" and pytest doesn't add cwd to sys.path.
func FixPythonMakefileTest(makefilePath string) (bool, error) {
	data, err := os.ReadFile(makefilePath)
	if err != nil {
		return false, err
	}
	content := string(data)
	// Only act on Makefiles that call pytest without PYTHONPATH already set
	if !strings.Contains(content, "pytest") {
		return false, nil
	}
	if strings.Contains(content, "PYTHONPATH") {
		return false, nil
	}
	// Replace tab-indented "pytest" and "python -m pytest" recipe lines
	lines := strings.Split(content, "\n")
	changed := false
	for i, line := range lines {
		if len(line) == 0 || line[0] != '\t' {
			continue
		}
		trimmed := strings.TrimSpace(line)
		if trimmed == "pytest" || strings.HasPrefix(trimmed, "pytest ") {
			lines[i] = "\tPYTHONPATH=. " + trimmed
			changed = true
		} else if trimmed == "python3 -m pytest" || strings.HasPrefix(trimmed, "python3 -m pytest ") {
			lines[i] = "\tPYTHONPATH=. " + trimmed
			changed = true
		} else if trimmed == "python -m pytest" || strings.HasPrefix(trimmed, "python -m pytest ") {
			lines[i] = "\tPYTHONPATH=. " + trimmed
			changed = true
		}
	}
	if !changed {
		return false, nil
	}
	return true, os.WriteFile(makefilePath, []byte(strings.Join(lines, "\n")), 0644)
}

// FixNoMakefileTestCommand rewrites "make" test commands when no Makefile is listed
// in the plan's file tasks. Derives an inline compile+run command from the first
// source file's extension so trivial programs don't stall on a missing Makefile.
// makeWithoutMakefileRE matches "make" or "make && ./binary" test commands that rely
// on a Makefile that isn't in the plan's file list.
var makeWithoutMakefileRE = regexp.MustCompile(`^make(\s*&&.*)?$`)

func FixNoMakefileTestCommand(planPath string, p *Plan) (bool, error) {
	if !makeWithoutMakefileRE.MatchString(strings.TrimSpace(p.TestCommand)) {
		return false, nil
	}
	for _, t := range p.Tasks {
		if IsBuildFile(t.FilePath) {
			return false, nil
		}
	}
	if len(p.Tasks) == 0 {
		return false, nil
	}
	src := p.Tasks[0].FilePath
	ext := extOf(baseOf(src))
	stem := stemOf(baseOf(src))

	var newCmd string
	switch ext {
	case "c":
		newCmd = "gcc " + src + " -o " + stem + " && ./" + stem
	case "cpp", "cc", "cxx":
		newCmd = "g++ " + src + " -o " + stem + " && ./" + stem
	case "py":
		newCmd = "python3 " + src
	case "go":
		newCmd = "go run " + src
	case "rs":
		newCmd = "rustc " + src + " -o " + stem + " && ./" + stem
	default:
		return false, nil
	}

	data, err := os.ReadFile(planPath)
	if err != nil {
		return false, err
	}
	// Replace the test command line — it appears as a bare "make" line in the section
	content := string(data)
	updated := strings.ReplaceAll(content, "\nmake\n", "\n"+newCmd+"\n")
	if updated == content {
		return false, nil
	}
	return true, os.WriteFile(planPath, []byte(updated), 0644)
}

// runtimeArtifactExts lists file extensions that are generated at runtime and
// should never appear as write targets in a plan.
var runtimeArtifactExts = map[string]bool{
	"db": true, "sqlite": true, "sqlite3": true,
	"o": true, "obj": true, "pyc": true, "class": true, "bin": true,
}

// DropRuntimeArtifacts removes tasks whose file extension marks them as
// runtime-generated artifacts (e.g. .db, .sqlite, .o). Returns the dropped paths.
func DropRuntimeArtifacts(planPath string, p *Plan) []string {
	var dropped []string
	for _, t := range p.Tasks {
		ext := strings.ToLower(extOf(baseOf(t.FilePath)))
		if runtimeArtifactExts[ext] {
			dropped = append(dropped, t.FilePath)
		}
	}
	if len(dropped) == 0 {
		return nil
	}

	data, err := os.ReadFile(planPath)
	if err != nil {
		return nil
	}
	lines := strings.Split(string(data), "\n")
	var out []string
	for _, line := range lines {
		m := taskRE.FindStringSubmatch(line)
		if m != nil {
			ext := strings.ToLower(extOf(baseOf(m[2])))
			if runtimeArtifactExts[ext] {
				continue // drop this line
			}
		}
		out = append(out, line)
	}
	_ = os.WriteFile(planPath, []byte(strings.Join(out, "\n")), 0644)
	return dropped
}

func RecoverFromLog(logPath, planPath string) (bool, error) {
	data, err := os.ReadFile(logPath)
	if err != nil || len(data) == 0 {
		return false, nil
	}
	fenceRE := regexp.MustCompile(`^` + "\\s*```" + `([Mm]arkdown|md)?\s*$`)
	closingFenceRE := regexp.MustCompile(`^` + "\\s*```" + `\s*$`)
	scanner := bufio.NewScanner(strings.NewReader(string(data)))
	inBlock := false
	var content strings.Builder
	for scanner.Scan() {
		line := scanner.Text()
		if !inBlock && fenceRE.MatchString(line) {
			inBlock = true
			continue
		}
		if inBlock && closingFenceRE.MatchString(line) {
			break
		}
		if inBlock {
			content.WriteString(line)
			content.WriteByte('\n')
		}
	}
	if content.Len() == 0 {
		return false, nil
	}
	return true, os.WriteFile(planPath, []byte(content.String()), 0644)
}

func RecoverFileFromLog(logPath, target string) (bool, error) {
	data, err := os.ReadFile(logPath)
	if err != nil || len(data) == 0 {
		return false, nil
	}
	fenceRE := regexp.MustCompile("^\\s*```[a-zA-Z]*\\s*$")
	closingFenceRE := regexp.MustCompile("^\\s*```\\s*$")
	scanner := bufio.NewScanner(strings.NewReader(string(data)))
	inBlock := false
	var content strings.Builder
	for scanner.Scan() {
		line := scanner.Text()
		if !inBlock && fenceRE.MatchString(line) {
			inBlock = true
			continue
		}
		if inBlock && closingFenceRE.MatchString(line) {
			break
		}
		if inBlock {
			content.WriteString(line)
			content.WriteByte('\n')
		}
	}
	if content.Len() == 0 {
		return false, nil
	}
	if err := os.MkdirAll(dirOf(target), 0755); err != nil {
		return false, err
	}
	return true, os.WriteFile(target, []byte(content.String()), 0644)
}

// path helpers (avoid importing filepath here to keep this package light)
func dirOf(p string) string {
	i := strings.LastIndex(p, "/")
	if i < 0 {
		return "."
	}
	return p[:i]
}

func baseOf(p string) string {
	i := strings.LastIndex(p, "/")
	return p[i+1:]
}

func extOf(name string) string {
	i := strings.LastIndex(name, ".")
	if i < 0 {
		return ""
	}
	return name[i+1:]
}

func stemOf(name string) string {
	i := strings.LastIndex(name, ".")
	if i < 0 {
		return name
	}
	return name[:i]
}
