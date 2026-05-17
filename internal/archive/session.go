package archive

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/jacobandresen/mu/internal/plan"
)

type Session struct {
	ID          string
	Goal        string
	ProjectDir  string
	StartTime   time.Time
	ArchivePath string
	MaxIter     int
	LogDir      string
}

func NewSession(goal, archiveDir, logDir string, maxIter int) (*Session, error) {
	safeGoal := regexp.MustCompile(`[^A-Za-z0-9_-]`).ReplaceAllStringFunc(
		strings.ReplaceAll(strings.ReplaceAll(goal, " ", "_"), "/", "-"),
		func(s string) string { return "" },
	)
	if len(safeGoal) > 40 {
		safeGoal = safeGoal[:40]
	}
	id := time.Now().Format("20060102-150405") + "-" + safeGoal
	archivePath := filepath.Join(archiveDir, id)

	projectDir, _ := os.Getwd()
	s := &Session{
		ID:          id,
		Goal:        goal,
		ProjectDir:  projectDir,
		StartTime:   time.Now(),
		ArchivePath: archivePath,
		MaxIter:     maxIter,
		LogDir:      logDir,
	}

	if err := os.MkdirAll(archivePath, 0755); err != nil {
		return s, nil // not fatal
	}
	// Write partial tombstone immediately — survives SIGKILL
	tomb := fmt.Sprintf(`{"session_id":%q,"goal":%q,"outcome":"unknown","exit_code":-1}`+"\n", id, goal)
	_ = os.WriteFile(filepath.Join(archivePath, "meta.json"), []byte(tomb), 0644)
	return s, nil
}

func (s *Session) Finalize(exitCode int, p *plan.Plan) {
	_ = os.MkdirAll(filepath.Join(s.ArchivePath, "logs"), 0755)

	if _, err := os.Stat(s.LogDir); err == nil {
		copyDir(s.LogDir, filepath.Join(s.ArchivePath, "logs"))
	}

	var tasksTotal, tasksDone int
	if p != nil {
		tasksTotal, tasksDone = plan.CountTasks(p)
		if data, err := os.ReadFile("PLAN.md"); err == nil {
			_ = os.WriteFile(filepath.Join(s.ArchivePath, "PLAN-final.md"), data, 0644)
		}
	}

	outcome := map[int]string{
		0: "success",
		1: "error",
		2: "max_iterations",
		3: "stalled",
	}[exitCode]
	if outcome == "" {
		outcome = "unknown"
	}

	endTime := time.Now()
	duration := int(endTime.Sub(s.StartTime).Seconds())

	meta := map[string]any{
		"session_id":       s.ID,
		"goal":             s.Goal,
		"project_dir":      s.ProjectDir,
		"start_time":       s.StartTime.UTC().Format(time.RFC3339),
		"end_time":         endTime.UTC().Format(time.RFC3339),
		"duration_seconds": duration,
		"max_iterations":   s.MaxIter,
		"outcome":          outcome,
		"exit_code":        exitCode,
		"tasks_total":      tasksTotal,
		"tasks_done":       tasksDone,
	}
	data, err := json.MarshalIndent(meta, "", "  ")
	if err != nil {
		return
	}
	_ = os.WriteFile(filepath.Join(s.ArchivePath, "meta.json"), append(data, '\n'), 0644)
	fmt.Fprintf(os.Stderr, "==> [mu-agent] Session archived -> %s\n", s.ArchivePath)
}

func copyDir(src, dst string) {
	entries, err := os.ReadDir(src)
	if err != nil {
		return
	}
	_ = os.MkdirAll(dst, 0755)
	for _, e := range entries {
		srcPath := filepath.Join(src, e.Name())
		dstPath := filepath.Join(dst, e.Name())
		if e.IsDir() {
			copyDir(srcPath, dstPath)
		} else {
			data, err := os.ReadFile(srcPath)
			if err == nil {
				_ = os.WriteFile(dstPath, data, 0644)
			}
		}
	}
}
