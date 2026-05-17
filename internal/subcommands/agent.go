package subcommands

import (
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/jacobandresen/mu/internal/archive"
	"github.com/jacobandresen/mu/internal/ollama"
	"github.com/jacobandresen/mu/internal/plan"
	"github.com/jacobandresen/mu/internal/ui"
	"github.com/spf13/cobra"
)

const (
	logDir     = ".mu"
	sessionDir = ".mu/code-session"

	// requiredSkillsVersion is the minimum dotfiles skills tag this agent was built against.
	// Update this when task-planner or other skills change in ~/Projects/dotfiles.
	requiredSkillsVersion = "skills-v1.1"
)

type agentConfig struct {
	Goal            string
	TargetDir       string
	MaxIter         int
	Force           bool
	PlannerTimeout  int
	WriterTimeout   int
	AgentModel      string
	BaseModel       string
	Thinking        string
	PlannerThinking string
	WriterThinking  string
	Combined        int // -1=auto, 0=off, 1=on
	ArchiveDir      string
	Complexity      string
}

func NewAgentCmd() *cobra.Command {
	var cfg agentConfig
	cmd := &cobra.Command{
		Use:   "agent [flags] \"goal\"",
		Short: "Autonomous goal-to-code orchestrator",
		Long: `Drives an autonomous coding loop from a plain-English goal:
  1. Runs the task-planner skill to produce a tracked PLAN.md
  2. Repeatedly runs mu run until all tasks are done or the iteration limit is reached`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			cfg.Goal = args[0]
			return runAgent(cfg)
		},
	}
	cmd.Flags().StringVarP(&cfg.TargetDir, "dir", "d", "", "Create/enter PATH before running")
	cmd.Flags().IntVarP(&cfg.MaxIter, "max-iter", "n", 10, "Maximum iterations")
	cmd.Flags().BoolVar(&cfg.Force, "force", false, "Skip the existing-project guard")
	return cmd
}

func runAgent(cfg agentConfig) error {
	// Read env vars
	cfg.AgentModel = orEnv(cfg.AgentModel, "MU_AGENT_MODEL")
	cfg.BaseModel = orEnv("qwen3:8b", "MU_AGENT_BASE_MODEL")
	cfg.Thinking = os.Getenv("MU_AGENT_THINKING")
	cfg.PlannerThinking = os.Getenv("MU_AGENT_PLANNER_THINKING")
	cfg.WriterThinking = os.Getenv("MU_AGENT_WRITE_THINKING")
	if cfg.PlannerThinking == "" {
		cfg.PlannerThinking = cfg.Thinking
	}
	if cfg.WriterThinking == "" {
		cfg.WriterThinking = cfg.Thinking
	}
	if v := os.Getenv("MU_AGENT_PLANNER_TIMEOUT"); v != "" {
		cfg.PlannerTimeout, _ = strconv.Atoi(v)
	}
	home, _ := os.UserHomeDir()
	cfg.ArchiveDir = os.Getenv("MU_AGENT_ARCHIVE_DIR")
	if cfg.ArchiveDir == "" {
		cfg.ArchiveDir = filepath.Join(home, ".mu", "sessions")
	}

	// Combined mode from env
	cfg.Combined = -1
	if v := os.Getenv("MU_AGENT_COMBINED"); v != "" {
		n, _ := strconv.Atoi(v)
		cfg.Combined = n
	}

	// Auto-tune by complexity
	detectComplexity(&cfg)

	// Directory setup
	if cfg.TargetDir != "" {
		if err := os.MkdirAll(cfg.TargetDir, 0755); err != nil {
			return fmt.Errorf("create dir: %w", err)
		}
		if err := os.Chdir(cfg.TargetDir); err != nil {
			return fmt.Errorf("enter dir: %w", err)
		}
	}

	// Standalone guard
	if err := checkStandalone(cfg.Force); err != nil {
		return err
	}

	// Setup
	if err := os.MkdirAll(logDir, 0755); err != nil {
		return fmt.Errorf("create log dir: %w", err)
	}

	// Model setup
	if cfg.AgentModel == "" {
		model, err := ensureAgentModel(cfg.BaseModel)
		if err != nil {
			fmt.Fprintf(os.Stderr, "WARNING: could not create agent model: %v — using %s\n", err, cfg.BaseModel)
			cfg.AgentModel = cfg.BaseModel
		} else {
			cfg.AgentModel = model
		}
	}
	_ = ollama.UnloadOthers(cfg.AgentModel)

	// Session
	sess, _ := archive.NewSession(cfg.Goal, cfg.ArchiveDir, logDir, cfg.MaxIter)

	// Signal handler
	var currentPlan *plan.Plan
	var exitCode int

	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigs
		fmt.Fprintln(os.Stderr, "\nInterrupted.")
		sess.Finalize(130, currentPlan)
		os.Exit(130)
	}()
	defer func() {
		sess.Finalize(exitCode, currentPlan)
	}()

	// Planning phase
	if _, err := os.Stat("PLAN.md"); err == nil {
		agentLog("PLAN.md already exists — skipping task-planner.")
		if err := validateExistingPlan(); err != nil {
			exitCode = 1
			return err
		}
	} else {
		planLog := filepath.Join(logDir, "plan.log")
		if err := runPlanningPhase(&cfg, planLog); err != nil {
			exitCode = 1
			return err
		}
	}

	stripped, _ := plan.StripThinkingArtifacts("PLAN.md")
	if stripped {
		agentLog("WARNING: thinking artifact tokens stripped from PLAN.md")
	}

	// Extract files embedded as code blocks in PLAN.md (e.g. ## Makefile section)
	if extracted, err := plan.NormalizeEmbeddedFiles("PLAN.md"); len(extracted) > 0 {
		agentLog("Extracted embedded files from PLAN.md: %s", strings.Join(extracted, ", "))
		_ = err
	}

	// Fix test commands that would try to run graphical/interactive binaries
	goalIsGraphical := graphicalRE.MatchString(cfg.Goal)
	if fixed, _ := plan.FixGraphicalTestCommand("PLAN.md", goalIsGraphical); fixed {
		agentLog("Rewrote graphical test command to compile-only.")
	}

	// Normalize test command portability (python → python3, etc.)
	if fixed, _ := plan.NormalizeTestCommand("PLAN.md"); fixed {
		agentLog("Normalized test command for portability.")
	}

	p, err := plan.Parse("PLAN.md")
	if err != nil {
		exitCode = 1
		return fmt.Errorf("parse PLAN.md: %w", err)
	}
	currentPlan = p

	// Fix "make" test command when no Makefile is in the task list (trivial programs)
	if fixed, _ := plan.FixNoMakefileTestCommand("PLAN.md", p); fixed {
		agentLog("Rewrote trivial test command: no Makefile in plan, using inline compile.")
		p, _ = plan.Parse("PLAN.md")
		currentPlan = p
	}

	// Fix dotnet test/run command when no matching .csproj is referenced
	if fixed, _ := plan.FixDotnetTestCommand("PLAN.md", p); fixed {
		agentLog("Rewrote dotnet test command to reference .csproj from file list.")
		p, _ = plan.Parse("PLAN.md")
		currentPlan = p
	}

	ok, missing := plan.CheckGoalAlignment(p, cfg.Goal)
	if !ok {
		agentLog("WARNING: PLAN.md contains none of the goal keywords — plan may be misaligned.")
	} else if len(missing) > 0 {
		agentLog("NOTE: PLAN.md is missing some goal terms: %s", strings.Join(missing, ", "))
	}

	// Snapshot initial plan
	os.MkdirAll(sess.ArchivePath, 0755)
	if data, err := os.ReadFile("PLAN.md"); err == nil {
		_ = os.WriteFile(filepath.Join(sess.ArchivePath, "PLAN-initial.md"), data, 0644)
	}

	// Mark combined-mode source file done if it was written during planning
	combinedSrc := os.Getenv("_MU_AGENT_COMBINED_SRC")
	if combinedSrc != "" {
		if _, err := os.Stat(combinedSrc); err == nil {
			agentLog("Combined mode: %s written during planning — marking done.", combinedSrc)
			_ = plan.MarkTaskDone("PLAN.md", combinedSrc)
			p, _ = plan.Parse("PLAN.md")
			currentPlan = p
		}
	}

	// Build system prompt
	projectDir, _ := os.Getwd()
	autonomousSystem := buildAutonomousSystem(projectDir)

	// Write loop
	for i := 1; i <= cfg.MaxIter; i++ {
		task := plan.NextTask(p)
		if task == nil {
			agentLog("All tasks complete.")
			break
		}

		agentLog("Iteration %d / %d: %s", i, cfg.MaxIter, task.FilePath)
		iterLog := filepath.Join(logDir, fmt.Sprintf("iter-%02d.log", i))
		iterErrLog := filepath.Join(logDir, fmt.Sprintf("iter-%02d.err", i))

		writePrompt := buildWritePrompt(cfg.Goal, task, p, projectDir)

		if !runWriter(&cfg, task.FilePath, iterLog, iterErrLog, writePrompt, autonomousSystem) {
			if _, err := os.Stat(task.FilePath); err != nil {
				// Retry with simpler prompt
				agentLog("Writer did not produce %s — retrying.", task.FilePath)
				retryLog := filepath.Join(logDir, fmt.Sprintf("iter-%02d-retry.log", i))
				retryErrLog := filepath.Join(logDir, fmt.Sprintf("iter-%02d-retry.err", i))
				retryPrompt := fmt.Sprintf("Write file NOW: `%s`\nDerive every detail from GOAL and PLAN.md. Make your own decisions.\nCall Write exactly once with the complete file contents. Stop immediately after.\n\nGOAL: %s\n%s",
					task.FilePath, cfg.Goal, p.PlanContext)
				if !runWriter(&cfg, task.FilePath, retryLog, retryErrLog, retryPrompt, autonomousSystem) {
					agentLog("Iteration %d: %s not written after retry.", i, task.FilePath)
					exitCode = 3
					return fmt.Errorf("stalled: model did not write %s", task.FilePath)
				}
			}
		}

		// Post-write: fix SDL2 include path (model writes SDL2/SDL.h; macOS homebrew needs SDL.h)
		if goalIsGraphical && isSDLSource(task.FilePath) {
			if fixedSDL, _ := fixSDLInclude(task.FilePath); fixedSDL {
				agentLog("Fixed SDL2 include path in %s.", task.FilePath)
			}
		}

		// Post-write: fix .csproj TargetFramework to match installed dotnet version
		if strings.HasSuffix(task.FilePath, ".csproj") {
			if fixedFw, _ := fixCsprojTargetFramework(task.FilePath); fixedFw {
				agentLog("Fixed TargetFramework in %s to match installed dotnet.", task.FilePath)
			}
		}

		// Test gate after test files
		testCmd := p.TestCommand
		if testCmd != "" && isTestFile(task.FilePath) {
			testLog := filepath.Join(logDir, fmt.Sprintf("tests-iter-%02d.log", i))
			if !runTests(testCmd, testLog) {
				agentLog("Tests failing after %s — invoking repair agent.", task.FilePath)
				fixLog := filepath.Join(logDir, fmt.Sprintf("fix-%02d.log", i))
				testTail := tailFile(testLog, 80)
				runRepair(&cfg, testCmd, testTail, fixLog, sessionDir, autonomousSystem)
				if !runTests(testCmd, testLog) {
					agentLog("Tests still failing after repair for %s.", task.FilePath)
					exitCode = 3
					return fmt.Errorf("stalled: tests still failing after repair")
				}
			}
		}

		if plan.IsBuildFile(task.FilePath) {
			checkBuildFilePaths(task.FilePath, p)
		}

		if err := plan.MarkTaskDone("PLAN.md", task.FilePath); err != nil {
			agentLog("WARNING: could not mark task done: %v", err)
		}
		agentLog("Marked done: %s", task.FilePath)
		fmt.Printf("\n  %s\n\n", ui.Green("Iteration "+strconv.Itoa(i)+" done: "+task.FilePath))

		// Re-parse plan
		p, _ = plan.Parse("PLAN.md")
		currentPlan = p
	}

	// Final test gate
	if !plan.TasksRemaining(p) || p == nil {
		if err := finalTestGate(&cfg, p, autonomousSystem); err != nil {
			exitCode = 3
			return err
		}
		agentLog("Goal complete.")
		fmt.Printf("\n  %s\n\n", ui.Green("Goal complete!"))
		exitCode = 0
		return nil
	}

	fmt.Fprintf(os.Stderr, "mu-agent: warning: reached max iterations (%d) with tasks remaining\n", cfg.MaxIter)
	exitCode = 2
	return fmt.Errorf("max iterations reached")
}

// ── Complexity detection ─────────────────────────────────────────────────────

var libRE = regexp.MustCompile(`(?i)SDL2|OpenGL|ncurses|dotnet|C#|csharp|tensorflow|pytorch|django|flask|opencv|wxwidgets`)

// graphicalRE matches goals that produce windowed/graphical programs that cannot be run headlessly
var graphicalRE = regexp.MustCompile(`(?i)SDL2|OpenGL|ncurses|wxwidgets`)

func detectComplexity(cfg *agentConfig) {
	words := len(strings.Fields(cfg.Goal))
	hasLib := libRE.MatchString(cfg.Goal)

	var complexity string
	switch {
	case hasLib:
		complexity = "complex"
	case words <= 4:
		complexity = "trivial"
	default:
		complexity = "simple"
	}
	cfg.Complexity = complexity

	if cfg.PlannerThinking == "" {
		cfg.PlannerThinking = "off"
	}
	if cfg.WriterThinking == "" {
		cfg.WriterThinking = "off"
	}

	if cfg.PlannerTimeout == 0 {
		cfg.PlannerTimeout = map[string]int{"trivial": 120, "simple": 200, "complex": 360}[complexity]
	}
	cfg.WriterTimeout = map[string]int{"trivial": 90, "simple": 220, "complex": 300}[complexity]

	if cfg.Combined == -1 {
		if complexity == "trivial" {
			cfg.Combined = 1
		} else {
			cfg.Combined = 0
		}
	}
}

// ── Model setup ──────────────────────────────────────────────────────────────

func ensureAgentModel(base string) (string, error) {
	parts := strings.SplitN(base, ":", 2)
	target := parts[0] + ":ralph"

	if _, err := ollama.ShowModel(target); err == nil {
		return target, nil
	}

	agentLog("Creating %s (temperature=0, thinking disabled) from %s ...", target, base)

	modelfile := fmt.Sprintf("FROM %s\nPARAMETER temperature 0\nPARAMETER num_ctx 4096\n", base)

	// Try to fetch and patch the template
	info, err := ollama.ShowModel(base)
	if err == nil {
		if tmpl, ok := info["template"].(string); ok && tmpl != "" {
			tmpl = patchTemplate(tmpl)
			modelfile += fmt.Sprintf("TEMPLATE \"\"\"\n%s\"\"\"\n", tmpl)
		}
	}

	if err := ollama.CreateModel(target, modelfile); err != nil {
		agentLog("WARNING: ollama create failed — using %s (temperature uncontrolled)", base)
		return base, nil
	}

	// Update models.json
	_ = upsertModelsJSON(modelsPath(), target)
	return target, nil
}

func patchTemplate(t string) string {
	old := "{{ if and $.IsThinkSet (not $.Think) -}}\n<think>\n\n</think>\n\n{{ end -}}"
	t = strings.ReplaceAll(t, old, "<think>\n\n</think>\n\n")
	old2 := "{{- if and $.IsThinkSet (eq $i $lastUserIdx) }}\n   {{- if $.Think -}}\n      {{- \" \"}}/think\n   {{- else -}}\n      {{- \" \"}}/no_think\n   {{- end -}}\n{{- end }}"
	t = strings.ReplaceAll(t, old2, " /no_think")
	return t
}

// ── Standalone guard ──────────────────────────────────────────────────────────

func checkStandalone(force bool) error {
	if _, err := os.Stat("PLAN.md"); err == nil {
		return nil // resume always allowed
	}
	if force {
		return nil
	}
	entries, _ := os.ReadDir(".")
	fileCount := 0
	for _, e := range entries {
		if !strings.HasPrefix(e.Name(), ".") {
			fileCount++
		}
	}
	gitCommits := 0
	if out, err := exec.Command("git", "rev-list", "--count", "HEAD").Output(); err == nil {
		gitCommits, _ = strconv.Atoi(strings.TrimSpace(string(out)))
	}
	if fileCount > 5 || gitCommits > 0 {
		wd, _ := os.Getwd()
		fmt.Fprintf(os.Stderr, "mu-agent: '%s' looks like an existing project (files: %d, git commits: %d)\n", wd, fileCount, gitCommits)
		fmt.Fprintln(os.Stderr, "  mu agent is designed for small apps in a standalone directory.")
		fmt.Fprintln(os.Stderr, "  Use --dir <path> to target a fresh directory, or --force to proceed anyway.")
		return fmt.Errorf("existing project guard")
	}
	return nil
}

// ── Planning ──────────────────────────────────────────────────────────────────

func validateExistingPlan() error {
	data, err := os.ReadFile("PLAN.md")
	if err != nil {
		return err
	}
	content := string(data)
	if regexp.MustCompile(`(?m)^### Group `).MatchString(content) {
		return fmt.Errorf("PLAN.md uses old '### Group N' format — delete it to re-plan")
	}
	if !regexp.MustCompile(`(?m)^- \[[ x~]\]`).MatchString(content) {
		return fmt.Errorf("existing PLAN.md has no task checklist — delete it to re-plan")
	}
	if !regexp.MustCompile(`(?im)^- \[[ x~]\].*\btest`).MatchString(content) {
		agentLog("WARNING: existing PLAN.md has no unit-test file — consider deleting to re-plan.")
	}
	return nil
}

func runPlanningPhase(cfg *agentConfig, planLog string) error {
	const maxAttempts = 2
	var planEC error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		logFile := planLog
		if attempt > 1 {
			logFile = filepath.Join(logDir, fmt.Sprintf("plan-attempt-%02d.log", attempt))
			agentLog("Planner attempt %d / %d (previous attempt produced no PLAN.md)", attempt, maxAttempts)
		} else {
			agentLog("Planning: %s (planner=%s writer=%s timeout=%ds complexity=%s)",
				cfg.Goal, cfg.PlannerThinking, cfg.WriterThinking, cfg.PlannerTimeout, cfg.Complexity)
		}

		if cfg.Combined == 1 && attempt == 1 {
			agentLog("Using combined plan+write mode (single pi session).")
			combinedSrc, err := runCombinedPlanner(cfg, logFile)
			if err == nil && combinedSrc != "" {
				os.Setenv("_MU_AGENT_COMBINED_SRC", combinedSrc)
			}
		} else {
			planEC = runPlanner(cfg, logFile)
		}

		if _, err := os.Stat("PLAN.md"); err == nil {
			break
		}
		if ok, _ := plan.RecoverFromLog(logFile, "PLAN.md"); ok {
			agentLog("Recovered PLAN.md from fenced block in %s", logFile)
			break
		}
		agentLog("Attempt %d: no PLAN.md produced", attempt)
		if attempt == maxAttempts {
			_ = planEC
			return fmt.Errorf("task-planner did not create PLAN.md after %d attempts — see %s/plan*.log", maxAttempts, logDir)
		}
	}

	data, _ := os.ReadFile("PLAN.md")
	if !regexp.MustCompile(`(?m)^- \[[ x~]\]`).Match(data) {
		return fmt.Errorf("PLAN.md has no task checklist — see %s/plan.log", logDir)
	}
	agentLog("PLAN.md created.")
	fmt.Println()
	planData, _ := os.ReadFile("PLAN.md")
	fmt.Println(string(planData))
	return nil
}

func runPlanner(cfg *agentConfig, logFile string) error {
	projectDir, _ := os.Getwd()
	prompt := buildPlannerPrompt(cfg.Goal, projectDir)
	autonomousSystem := buildAutonomousSystem(projectDir)

	args := []string{
		"--thinking", cfg.PlannerThinking,
		"--model", cfg.AgentModel,
		"--append-system-prompt", autonomousSystem,
	}
	// Load task-planner skill from dotfiles if available (requiredSkillsVersion)
	if skillContent := loadSkill("task-planner"); skillContent != "" {
		args = append(args, "--append-system-prompt", skillContent)
	}
	args = append(args, "-p", prompt)
	return runBackground("pi", args, logFile, cfg.PlannerTimeout, "PLAN.md", nil)
}

func loadSkill(name string) string {
	home, _ := os.UserHomeDir()
	path := filepath.Join(home, ".pi", "agent", "skills", name, "SKILL.md")
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return string(data)
}

func runCombinedPlanner(cfg *agentConfig, logFile string) (string, error) {
	projectDir, _ := os.Getwd()
	prompt := fmt.Sprintf(`Write TWO files in sequence using the Write tool.

STEP 1 — Write '%s/PLAN.md' with:

## Files
- [ ] <filename> — <one-line description>

## Test Command
<single command that exits non-zero on failure, no Makefile>

## Dependencies
<required tools>

Pick the simplest filename (main.c, main.py, etc.). Inline compilation in Test Command.

STEP 2 — Immediately after writing PLAN.md, write the source file listed in it.

Do not pause between steps. Write both files and then STOP. No explanations.

GOAL: %s`, projectDir, cfg.Goal)

	autonomousSystem := buildAutonomousSystem(projectDir)
	combinedTimeout := cfg.PlannerTimeout + cfg.WriterTimeout

	// We need to watch for both PLAN.md and the source file
	// Use a simple approach: run the background process and watch for both
	args := []string{
		"--thinking", cfg.PlannerThinking,
		"--model", cfg.AgentModel,
		"--append-system-prompt", autonomousSystem,
		"-p", prompt,
	}

	// Run and watch for PLAN.md + source file
	err := runBackgroundCombined(args, logFile, combinedTimeout)
	if err != nil {
		return "", err
	}

	// Find the source file that was written
	if _, e := os.Stat("PLAN.md"); e != nil {
		return "", fmt.Errorf("PLAN.md not written")
	}
	p, _ := plan.Parse("PLAN.md")
	if p != nil && len(p.Tasks) > 0 {
		src := p.Tasks[0].FilePath
		if _, e := os.Stat(src); e == nil {
			return src, nil
		}
	}
	return "", nil
}

// ── Background process management ────────────────────────────────────────────

func runBackground(name string, args []string, logFile string, timeout int, watchFile string, combinedWatch *string) error {
	f, err := os.Create(logFile)
	if err != nil {
		return err
	}
	defer f.Close()

	cmd := exec.Command(name, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.Stdout = f
	cmd.Stderr = f
	cmd.Stdin, _ = os.Open(os.DevNull)

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start %s: %w", name, err)
	}
	pid := cmd.Process.Pid

	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()

	start := time.Now()
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-done:
			fmt.Print("\r\033[K")
			if watchFile != "" {
				if _, err := os.Stat(watchFile); err == nil {
					return nil
				}
			}
			return nil
		case <-ticker.C:
			elapsed := int(time.Since(start).Seconds())
			fmt.Printf("\r  %s %s", ui.Cyan("Planning"), ui.DrawProgressBar(elapsed, timeout, 40))

			if watchFile != "" {
				if _, err := os.Stat(watchFile); err == nil {
					fmt.Print("\r\033[K")
					agentLog("%s written — stopping planner early (%ds elapsed).", watchFile, elapsed)
					killProcess(pid)
					return nil
				}
			}
			if elapsed >= timeout {
				fmt.Print("\r\033[K")
				agentLog("Planner timed out after %ds — killing.", timeout)
				killProcess(pid)
				return fmt.Errorf("planner timeout")
			}
		}
	}
}

func runBackgroundCombined(args []string, logFile string, timeout int) error {
	f, err := os.Create(logFile)
	if err != nil {
		return err
	}
	defer f.Close()

	cmd := exec.Command("pi", args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.Stdout = f
	cmd.Stderr = f
	cmd.Stdin, _ = os.Open(os.DevNull)

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start pi: %w", err)
	}
	pid := cmd.Process.Pid

	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()

	start := time.Now()
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	var srcFile string
	planFoundAt := -1

	for {
		select {
		case <-done:
			fmt.Print("\r\033[K")
			return nil
		case <-ticker.C:
			elapsed := int(time.Since(start).Seconds())
			fmt.Printf("\r  %s %s", ui.Cyan("Planning"), ui.DrawProgressBar(elapsed, timeout, 40))

			if srcFile == "" {
				if _, err := os.Stat("PLAN.md"); err == nil {
					if p, _ := plan.Parse("PLAN.md"); p != nil && len(p.Tasks) > 0 {
						srcFile = p.Tasks[0].FilePath
						planFoundAt = elapsed
						agentLog("Combined: PLAN.md ready at %ds — watching for: %s", planFoundAt, srcFile)
					}
				}
			}
			if srcFile != "" {
				if _, err := os.Stat(srcFile); err == nil {
					fmt.Print("\r\033[K")
					agentLog("Combined: PLAN.md + %s written in %ds.", srcFile, elapsed)
					killProcess(pid)
					return nil
				}
			}
			if elapsed >= timeout {
				fmt.Print("\r\033[K")
				agentLog("Combined planner+writer timed out after %ds.", timeout)
				killProcess(pid)
				return fmt.Errorf("timeout")
			}
		}
	}
}

func killProcess(pid int) {
	_ = syscall.Kill(-pid, syscall.SIGTERM)
	time.Sleep(200 * time.Millisecond)
	_ = syscall.Kill(-pid, syscall.SIGKILL)
}

// ── Writer ────────────────────────────────────────────────────────────────────

func runWriter(cfg *agentConfig, targetFile, logFile, errLogFile, prompt, autonomousSystem string) bool {
	if dir := filepath.Dir(targetFile); dir != "." {
		os.MkdirAll(dir, 0755)
	}

	fOut, _ := os.Create(logFile)
	fErr, _ := os.Create(errLogFile)
	defer fOut.Close()
	defer fErr.Close()

	writeRules := "REMINDER: Call Write ONCE for the file you are given. Complete, runnable content. Stop immediately after. Nothing else."
	args := []string{
		"--thinking", cfg.WriterThinking,
		"--model", cfg.AgentModel,
		"--session-dir", sessionDir,
		"--append-system-prompt", autonomousSystem,
		"--append-system-prompt", writeRules,
		"-p", prompt,
	}

	cmd := exec.Command("pi", args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.Stdout = fOut
	cmd.Stderr = fErr
	cmd.Stdin, _ = os.Open(os.DevNull)

	if err := cmd.Start(); err != nil {
		return false
	}
	pid := cmd.Process.Pid

	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()

	start := time.Now()
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-done:
			_, err := os.Stat(targetFile)
			return err == nil
		case <-ticker.C:
			elapsed := int(time.Since(start).Seconds())
			if _, err := os.Stat(targetFile); err == nil {
				agentLog("%s written — stopping writer (%ds).", targetFile, elapsed)
				killProcess(pid)
				return true
			}
			if elapsed >= cfg.WriterTimeout {
				agentLog("Writer timed out after %ds for %s.", cfg.WriterTimeout, targetFile)
				killProcess(pid)
				return false
			}
		}
	}
}

// ── Test gate ─────────────────────────────────────────────────────────────────

func runTests(cmd, logFile string) bool {
	f, _ := os.Create(logFile)
	c := exec.Command("bash", "-c", cmd)
	c.Stdout = f
	c.Stderr = f
	err := c.Run()
	f.Close()
	return err == nil
}

func runRepair(cfg *agentConfig, testCmd, testTail, fixLog, sesDir, autonomousSystem string) {
	fixRules := fmt.Sprintf(`REPAIR PROTOCOL — follow these steps exactly:
1. Run '%s' via Bash to read the current failure output.
2. Fix the broken file: use Write to rewrite it entirely, or Edit with 3-5 lines of surrounding context so old_string is unique.
3. Stop immediately after writing the fix — do not run tests again, do not explain. The harness will verify.
4. Do not modify PLAN.md.`, testCmd)

	args := []string{
		"--thinking", cfg.WriterThinking,
		"--model", cfg.AgentModel,
		"--session-dir", sesDir,
		"--continue",
		"--append-system-prompt", autonomousSystem,
		"--append-system-prompt", fixRules,
		"-p", fmt.Sprintf("Tests are failing. Fix the broken code now — do not explain, just call Write or Edit.\n\nTest command: `%s`\nLast output (tail):\n%s", testCmd, testTail),
	}
	f, _ := os.Create(fixLog)
	defer f.Close()

	cmd := exec.Command("pi", args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	cmd.Stdout = f
	cmd.Stderr = f
	cmd.Stdin, _ = os.Open(os.DevNull)

	if err := cmd.Start(); err != nil {
		return
	}
	pid := cmd.Process.Pid

	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()

	start := time.Now()
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-done:
			return
		case <-ticker.C:
			elapsed := int(time.Since(start).Seconds())
			if testsSilent(testCmd) {
				agentLog("Repair: tests pass after %ds — stopping pi.", elapsed)
				killProcess(pid)
				return
			}
			if elapsed >= cfg.WriterTimeout {
				agentLog("Repair timed out after %ds — killing.", cfg.WriterTimeout)
				killProcess(pid)
				return
			}
		}
	}
}

func testsSilent(cmd string) bool {
	c := exec.Command("bash", "-c", cmd)
	c.Stdout = nil
	c.Stderr = nil
	return c.Run() == nil
}

func finalTestGate(cfg *agentConfig, p *plan.Plan, autonomousSystem string) error {
	testCmd := ""
	if p != nil {
		testCmd = p.TestCommand
	}
	if testCmd == "" {
		agentLog("No '## Test Command' in PLAN.md — skipping final test gate.")
		return nil
	}

	maxRetries := 3
	for attempt := 0; attempt <= maxRetries; attempt++ {
		testLog := filepath.Join(logDir, "tests-final.log")
		if runTests(testCmd, testLog) {
			return nil
		}
		if attempt == maxRetries {
			fmt.Printf("\n  %s\n\n", ui.Red("Tests still failing after "+strconv.Itoa(maxRetries)+" retries. Giving up."))
			return fmt.Errorf("final tests failed")
		}
		agentLog("Final tests failed — repair retry %d / %d", attempt+1, maxRetries)
		retryLog := filepath.Join(logDir, fmt.Sprintf("final-retry-%02d.log", attempt+1))
		testTail := tailFile(testLog, 200)
		runRepair(cfg, testCmd, testTail, retryLog, sessionDir, autonomousSystem)
	}
	return nil
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func agentLog(format string, args ...any) {
	msg := fmt.Sprintf(format, args...)
	fmt.Printf("==> [mu-agent] %s\n", msg)
}

func orEnv(def, key string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func isTestFile(f string) bool {
	base := filepath.Base(f)
	return strings.HasPrefix(f, "tests/") || strings.HasPrefix(f, "test/") ||
		strings.HasPrefix(base, "test_") || strings.Contains(base, "_test.")
}

func tailFile(path string, lines int) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	ls := strings.Split(string(data), "\n")
	if len(ls) <= lines {
		return string(data)
	}
	return strings.Join(ls[len(ls)-lines:], "\n")
}

func checkBuildFilePaths(buildFile string, p *plan.Plan) {
	content, _ := os.ReadFile(buildFile)
	contentStr := string(content)
	for _, t := range p.Tasks {
		if t.Done || plan.IsBuildFile(t.FilePath) {
			continue
		}
		base := filepath.Base(t.FilePath)
		if !strings.Contains(contentStr, t.FilePath) && strings.Contains(contentStr, base) {
			agentLog("WARNING: %s references '%s' but PLAN.md lists '%s' — path mismatch.", buildFile, base, t.FilePath)
		}
	}
}

func buildAutonomousSystem(projectDir string) string {
	return fmt.Sprintf(`You are a code-writing agent running autonomously in: %s

ROLE: You receive one task — write a specific file — and execute it immediately.

PROTOCOL:
1. Call the Write tool exactly once with the requested path and complete file contents.
2. Derive all implementation details from the GOAL and PLAN.md. Make your own decisions — never ask for clarification.
3. Stop the moment Write completes. No summary, no explanation, no additional output.

OFF-LIMITS:
- Never ask questions or request confirmation. Never say "shall I proceed?", "is that okay?", or anything similar.
- Never write files other than the one explicitly requested.
- No arbitrary network calls (curl, wget, fetch, http, etc.).
- Only install packages that are explicitly listed in PLAN.md.`, projectDir)
}

func buildPlannerPrompt(goal, projectDir string) string {
	return fmt.Sprintf(`Your only output must be one Write tool call that creates '%s/PLAN.md'. No chat text, no fenced code blocks.

REQUIREMENTS:

1. PLAN.md must contain a '## Files' section: a flat ordered list of files to create, one per line,
   in dependency order (dependencies before dependents).
   Each line: '- [ ] relative/path/to/file' optionally followed by ' — one-line description'.

   USE THE SIMPLEST STRUCTURE THAT FITS THE GOAL.

   TRIVIAL programs (single-function utilities, tiny scripts — anything that fits
   naturally in one source file): use exactly ONE file, no Makefile, no modules, no headers.
   Compile and run inline in the Test Command.

   NON-TRIVIAL programs (multiple genuinely distinct components, reusable libraries, command-line
   tools with options, programs that use external libraries like SDL2/OpenGL/etc.): use a Makefile.
   The Makefile MUST appear in the ## Files list as '- [ ] Makefile'. Do NOT put Makefile content
   in a separate '## Makefile' section — it belongs in the ## Files task list.

   INTERACTIVE / GRAPHICAL programs (SDL2, OpenGL, ncurses, games, anything that opens
   a window or reads from stdin in a loop) MUST NOT have unit test files.
   The only test for these programs is a build smoke test: 'make' (compile only, do NOT run the binary).
   The Test Command MUST be just 'make' — never './binary', never 'make test' that runs the program.

   RUNTIME ARTIFACTS: Do NOT list runtime-generated files (SQLite databases, output logs,
   generated images, temp files) under ## Files — only list source files that must be written.

   SDL2 on macOS/homebrew: sdl2-config --cflags sets the SDL2 directory on the include path,
   so source files must use '#include <SDL.h>' (not '#include <SDL2/SDL.h>').

2. LANGUAGE RULE: Use the exact language stated in the GOAL.
   - 'C' or 'using C' -> .c files compiled with gcc/clang. NEVER use C# (.cs / dotnet).
   - 'C++' or 'using C++' -> .cpp files compiled with g++/clang++.
   - 'Python' -> .py files. 'Go' -> .go files. 'Rust' -> .rs files. Etc.
   - 'C#' or 'dotnet' -> MUST include a .csproj file. List it FIRST in ## Files.
     Simple programs: one .csproj in root + Program.cs. Test Command: dotnet run --project <name>.csproj
     NEVER use 'dotnet test' or 'dotnet run' unless the .csproj appears in ## Files.

3. MAKEFILE COMPLETENESS: If the Test Command references a make target, the Makefile MUST define
   that target from the start. Define test targets with a recipe even if the test source file
   does not exist yet.

4. Module functions should return values rather than printing so they can be unit-tested.
   Exception: interactive or graphical programs.

5. Include '## Test Command' with a single shell command that exits non-zero on failure.
   All paths must be project-relative, not absolute.
   GRAPHICAL PROGRAMS: Test Command must be just 'make' (compile only).

6. Include '## Dependencies' listing the compiler and any required tools.

7. Plan only — do not implement. Write PLAN.md and stop.

GOAL: %s`, projectDir, goal)
}

func buildWritePrompt(goal string, task *plan.Task, p *plan.Plan, projectDir string) string {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("GOAL: %s\n\n## Plan\n%s", goal, p.PlanContext))

	existing := plan.RelevantFilesContext(p, task.FilePath)
	if existing != "" {
		sb.WriteString("\n\n## Reference files (do not rewrite)\n" + existing)
	}

	sb.WriteString(fmt.Sprintf("\n\n## Task\nWrite file: `%s`", task.FilePath))
	if task.Description != "" {
		sb.WriteString(fmt.Sprintf("\nPurpose: %s", task.Description))
	}

	if plan.IsBuildFile(task.FilePath) {
		pending := plan.PendingSourceFiles(p, task.FilePath)
		if pending != "" {
			sb.WriteString(fmt.Sprintf("\n\nCRITICAL — use these EXACT file paths from PLAN.md in `%s`. Do not simplify or alter any path:\n%s", task.FilePath, pending))
		}
	}

	sb.WriteString(`

## Steps
1. Determine the complete, correct content for the file from the goal and plan.
2. Call Write with the full, runnable content.
3. Stop immediately after Write — no other output.`)

	_ = projectDir
	return sb.String()
}

// fixCsprojTargetFramework rewrites the TargetFramework in a .csproj to match
// the installed dotnet major version. Models often generate net8.0 or net6.0
// even when a newer runtime is installed.
func fixCsprojTargetFramework(f string) (bool, error) {
	out, err := exec.Command("dotnet", "--version").Output()
	if err != nil {
		return false, nil
	}
	ver := strings.TrimSpace(string(out))
	// Extract major version (e.g. "10.0.300" → "10")
	parts := strings.SplitN(ver, ".", 2)
	if len(parts) == 0 {
		return false, nil
	}
	major := parts[0]
	want := "net" + major + ".0"

	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	content := string(data)
	// Replace any <TargetFramework>netX.Y</TargetFramework> where X != major
	re := regexp.MustCompile(`<TargetFramework>net\d+\.\d+</TargetFramework>`)
	fixed := re.ReplaceAllString(content, "<TargetFramework>"+want+"</TargetFramework>")
	if fixed == content {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(fixed), 0644)
}

func isSDLSource(f string) bool {
	ext := strings.ToLower(filepath.Ext(f))
	return ext == ".c" || ext == ".cpp" || ext == ".cc" || ext == ".cxx"
}

func fixSDLInclude(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	fixed := strings.ReplaceAll(string(data), `#include <SDL2/SDL.h>`, `#include <SDL.h>`)
	fixed = strings.ReplaceAll(fixed, `#include "SDL2/SDL.h"`, `#include <SDL.h>`)
	if fixed == string(data) {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(fixed), 0644)
}
