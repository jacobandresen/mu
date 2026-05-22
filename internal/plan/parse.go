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
