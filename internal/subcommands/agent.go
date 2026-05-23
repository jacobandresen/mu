package subcommands

import (
	"context"
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

	"github.com/jacobandresen/mu/internal/agent"
	"github.com/jacobandresen/mu/internal/archive"
	"github.com/jacobandresen/mu/internal/lmstudio"
	"github.com/jacobandresen/mu/internal/plan"
	"github.com/jacobandresen/mu/internal/sensors"
	"github.com/jacobandresen/mu/internal/ui"
	"github.com/jacobandresen/mu/skills"
	"github.com/spf13/cobra"
)

const logDir = ".mu"

type agentConfig struct {
	Goal           string
	TargetDir      string
	MaxIter        int
	Force          bool
	PlannerTimeout int
	WriterTimeout  int
	Model          string
	Combined       int // -1=auto, 0=off, 1=on
	ArchiveDir     string
	Complexity     string
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
	cmd.Flags().StringVar(&cfg.Model, "model", "", "LM Studio model ID (overrides MU_AGENT_MODEL)")
	return cmd
}

func runAgent(cfg agentConfig) error {
	// Model selection: flag → env → first loaded model in LM Studio
	if cfg.Model == "" {
		cfg.Model = os.Getenv("MU_AGENT_MODEL")
	}
	if cfg.Model == "" {
		loaded, err := lmstudio.ListModels()
		if err != nil || len(loaded) == 0 {
			return fmt.Errorf("no model loaded in LM Studio — load a model first (mu model models)")
		}
		cfg.Model = loaded[0]
		agentLog("Using LM Studio model: %s", cfg.Model)
	}

	home, _ := os.UserHomeDir()
	cfg.ArchiveDir = os.Getenv("MU_AGENT_ARCHIVE_DIR")
	if cfg.ArchiveDir == "" {
		cfg.ArchiveDir = filepath.Join(home, ".mu", "sessions")
	}

	cfg.Combined = -1
	if v := os.Getenv("MU_AGENT_COMBINED"); v != "" {
		n, _ := strconv.Atoi(v)
		cfg.Combined = n
	}

	// Auto-tune timeouts by goal complexity
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
		if err := runPlanningPhase(&cfg); err != nil {
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

	// Simplify "show that X works" plans that incorrectly use pytest
	if fixed := fixDemonstrationScript("PLAN.md", p, cfg.Goal); fixed {
		agentLog("Simplified demonstration-script plan: removed test files, using direct execution.")
		p, _ = plan.Parse("PLAN.md")
		currentPlan = p
	}

	// Drop runtime-generated files (*.db, *.sqlite, *.o, etc.) the model mistakenly lists
	if dropped := plan.DropRuntimeArtifacts("PLAN.md", p); len(dropped) > 0 {
		agentLog("Dropped runtime artifact tasks from plan: %s", strings.Join(dropped, ", "))
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

	// Lint gate for combined-mode file (bypassed the write loop's lint check)
	if combinedSrc != "" {
		if fi, statErr := os.Stat(combinedSrc); statErr == nil {
			if lintCmd := lintCommand(combinedSrc, p); lintCmd != "" {
				lintLog := filepath.Join(logDir, "lint-combined.log")
				if !runLint(lintCmd, lintLog) {
					if sensors.RuffAutoFix(combinedSrc) && runLint(lintCmd, lintLog) {
						agentLog("Lint auto-fixed (ruff --fix): %s", combinedSrc)
					} else {
						agentLog("Lint failed for combined-mode %s — invoking repair.", combinedSrc)
						lintHead := headFile(lintLog, 60)
						deterministicFixed := (sensors.FixMultilineSingleQuote(combinedSrc, lintHead) ||
							sensors.FixMissingCloseParen(combinedSrc, lintHead)) &&
							runLint(lintCmd, lintLog)
						if deterministicFixed {
							agentLog("Lint auto-fixed (deterministic): %s", combinedSrc)
						} else {
							runRepairLint(&cfg, lintCmd, combinedSrc, lintHead, autonomousSystem)
							if !runLint(lintCmd, lintLog) {
								recordFailedRepair(fmt.Sprintf("lint repair for combined-mode %s", combinedSrc), headFile(lintLog, 5))
								exitCode = 3
								return fmt.Errorf("lint failed for combined-mode %s", combinedSrc)
							}
							agentLog("Lint passed after repair for combined-mode %s.", combinedSrc)
						}
					}
				} else {
					agentLog("Lint passed: %s", combinedSrc)
				}
			}
			_ = fi
		}
	}

	// Write loop
	for i := 1; i <= cfg.MaxIter; i++ {
		task := plan.NextTask(p)
		if task == nil {
			agentLog("All tasks complete.")
			break
		}

		agentLog("Iteration %d / %d: %s", i, cfg.MaxIter, task.FilePath)
		writePrompt := buildWritePrompt(cfg.Goal, task, p, projectDir)

		if !runWriter(&cfg, task.FilePath, writePrompt, autonomousSystem) {
			if _, err := os.Stat(task.FilePath); err != nil {
				agentLog("Writer did not produce %s — retrying.", task.FilePath)
				retryPrompt := fmt.Sprintf("Write file NOW: `%s`\nYou ONLY have the Write tool. Use it immediately — do not try to run commands or install packages.\nCall Write exactly once with the complete file contents. Stop immediately after.\n\nGOAL: %s\n%s",
					task.FilePath, cfg.Goal, p.PlanContext)
				if refCtx := plan.RelevantFilesContext(p, task.FilePath); refCtx != "" {
					retryPrompt += "\n\n## Reference files (do not rewrite)\n" + refCtx
					if isTestFile(task.FilePath) {
						retryPrompt += "\nCRITICAL: Call EXACT method/function names from the reference files above.\n"
					}
				}
				if !runWriter(&cfg, task.FilePath, retryPrompt, autonomousSystem) {
					agentLog("Iteration %d: %s not written after retry.", i, task.FilePath)
					exitCode = 3
					return fmt.Errorf("stalled: model did not write %s", task.FilePath)
				}
			}
		}

		// Detect near-empty written file
		if fi, statErr := os.Stat(task.FilePath); statErr == nil && fi.Size() < 100 {
			ext := strings.ToLower(filepath.Ext(task.FilePath))
			isConfigLike := ext == ".txt" || ext == ".toml" || ext == ".mod" || ext == ".sum" ||
				ext == ".json" || ext == ".yaml" || ext == ".yml" || ext == ".lock"
			if !plan.IsBuildFile(task.FilePath) && !isConfigLike {
				agentLog("Writer produced near-empty %s (%d bytes) — retrying.", task.FilePath, fi.Size())
				_ = os.Remove(task.FilePath)
				stubRetryPrompt := fmt.Sprintf("Write file NOW: `%s`\nYou ONLY have the Write tool. Use it immediately — do not try to run commands or install packages.\nCall Write exactly once with the complete file contents. Stop immediately after.\n\nGOAL: %s\n%s",
					task.FilePath, cfg.Goal, p.PlanContext)
				if refCtx := plan.RelevantFilesContext(p, task.FilePath); refCtx != "" {
					stubRetryPrompt += "\n\n## Reference files (do not rewrite)\n" + refCtx
					if isTestFile(task.FilePath) {
						stubRetryPrompt += "\nCRITICAL: Call EXACT method/function names from the reference files above.\n"
					}
				}
				if !runWriter(&cfg, task.FilePath, stubRetryPrompt, autonomousSystem) {
					agentLog("Iteration %d: %s still near-empty after retry.", i, task.FilePath)
				}
			}
		}

		// Post-write: correct test-file imports that reference a module name not on disk.
		if strings.HasSuffix(task.FilePath, ".py") {
			if fixedImp, _ := sensors.FixTestImportModule(task.FilePath); fixedImp {
				agentLog("Fixed %s: corrected import module name to match actual .py file on disk.", task.FilePath)
			}
		}

		// Post-write: repair general Makefile syntax errors (tabs, targets, recipes).
		if plan.IsBuildFile(task.FilePath) && strings.EqualFold(filepath.Base(task.FilePath), "makefile") {
			if fixedSpace, _ := sensors.FixMakefileSpaceIndent(task.FilePath); fixedSpace {
				agentLog("Fixed Makefile: converted space-indented recipes to tab-indented.")
			}
			if fixedOrphan, _ := sensors.FixOrphanTopLevelCommands(task.FilePath); fixedOrphan {
				agentLog("Fixed Makefile: wrapped orphan top-level commands in all: target.")
			}
			if fixedTargets, _ := sensors.FixNoTargets(task.FilePath); fixedTargets {
				agentLog("Fixed Makefile: wrapped shell commands in all: target (model wrote plain script).")
			}
			if fixedInline, _ := sensors.FixInlineRecipe(task.FilePath); fixedInline {
				agentLog("Fixed Makefile: split inline recipe onto tab-indented line.")
			}
			if fixedDup, _ := sensors.FixDuplicateVar(task.FilePath); fixedDup {
				agentLog("Fixed Makefile: removed duplicate variable assignments (kept first definition).")
			}
		}

		// Lint gate: run linter immediately after each source file is written
		if lintCmd := lintCommand(task.FilePath, p); lintCmd != "" {
			lintLog := filepath.Join(logDir, fmt.Sprintf("lint-iter-%02d.log", i))
			if !runLint(lintCmd, lintLog) {
				if sensors.RuffAutoFix(task.FilePath) && runLint(lintCmd, lintLog) {
					agentLog("Lint auto-fixed (ruff --fix): %s", task.FilePath)
				} else {
					agentLog("Lint failed for %s — invoking repair.", task.FilePath)
					lintHead := headFile(lintLog, 60)
					deterministicFixed := (sensors.FixMultilineSingleQuote(task.FilePath, lintHead) ||
						sensors.FixMissingCloseParen(task.FilePath, lintHead)) &&
						runLint(lintCmd, lintLog)
					if deterministicFixed {
						agentLog("Lint auto-fixed (deterministic): %s", task.FilePath)
					} else {
						runRepairLint(&cfg, lintCmd, task.FilePath, lintHead, autonomousSystem)
						if !runLint(lintCmd, lintLog) {
							agentLog("Lint still failing after repair for %s.", task.FilePath)
							recordFailedRepair(fmt.Sprintf("lint repair for %s", task.FilePath), headFile(lintLog, 5))
							exitCode = 3
							return fmt.Errorf("lint failed for %s", task.FilePath)
						}
						agentLog("Lint passed after repair for %s.", task.FilePath)
					}
				}
			} else {
				agentLog("Lint passed: %s", task.FilePath)
			}
		}

		// Test gate after test files — but only if no future build-file tasks remain.
		testCmd := p.TestCommand
		if testCmd != "" && isTestFile(task.FilePath) && !plan.HasPendingBuildFile(p) {
			testLog := filepath.Join(logDir, fmt.Sprintf("tests-iter-%02d.log", i))
			if !runTests(testCmd, testLog) {
				agentLog("Tests failing after %s — invoking repair loop.", task.FilePath)
				if !runTestRepairLoop(&cfg, testCmd, testLog, p, autonomousSystem) {
					agentLog("Tests still failing after repair loop for %s.", task.FilePath)
					recordFailedRepair(fmt.Sprintf("test repair after writing %s", task.FilePath), tailFile(testLog, 5))
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

var libRE = regexp.MustCompile(`(?i)SDL2|OpenGL|ncurses|dotnet|C#|csharp|tensorflow|pytorch|django|flask|opencv|wxwidgets|express|gin|cargo`)
var hardLibRE = regexp.MustCompile(`(?i)pytest|jest|xunit|nunit|rspec|cargo\s+test`)

func detectComplexity(cfg *agentConfig) {
	words := len(strings.Fields(cfg.Goal))
	hasLib := libRE.MatchString(cfg.Goal)

	var complexity string
	switch {
	case hasLib && hardLibRE.MatchString(cfg.Goal):
		complexity = "hard"
	case hasLib:
		complexity = "complex"
	case words <= 4:
		complexity = "trivial"
	default:
		complexity = "simple"
	}
	cfg.Complexity = complexity

	if cfg.PlannerTimeout == 0 {
		cfg.PlannerTimeout = map[string]int{"trivial": 120, "simple": 200, "complex": 360, "hard": 480}[complexity]
	}
	cfg.WriterTimeout = map[string]int{"trivial": 90, "simple": 220, "complex": 300, "hard": 400}[complexity]

	cfg.Combined = 0
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
	if _, err := os.Stat(".git"); err == nil {
		if out, err2 := exec.Command("git", "rev-list", "--count", "HEAD").Output(); err2 == nil {
			gitCommits, _ = strconv.Atoi(strings.TrimSpace(string(out)))
		}
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

func runPlanningPhase(cfg *agentConfig) error {
	const maxAttempts = 2
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		if attempt > 1 {
			agentLog("Planner attempt %d / %d (previous attempt produced no PLAN.md)", attempt, maxAttempts)
		} else {
			agentLog("Planning: %s (timeout=%ds complexity=%s)",
				cfg.Goal, cfg.PlannerTimeout, cfg.Complexity)
		}

		if cfg.Combined == 1 && attempt == 1 {
			agentLog("Using combined plan+write mode (single session).")
			combinedSrc, err := runCombinedPlanner(cfg)
			if err == nil && combinedSrc != "" {
				os.Setenv("_MU_AGENT_COMBINED_SRC", combinedSrc)
			}
		} else {
			runPlanner(cfg)
		}

		if _, err := os.Stat("PLAN.md"); err == nil {
			break
		}
		agentLog("Attempt %d: no PLAN.md produced", attempt)
		if attempt == maxAttempts {
			return fmt.Errorf("task-planner did not create PLAN.md after %d attempts", maxAttempts)
		}
	}

	data, _ := os.ReadFile("PLAN.md")
	if !regexp.MustCompile(`(?m)^- \[[ x~]\]`).Match(data) {
		return fmt.Errorf("PLAN.md has no task checklist")
	}
	agentLog("PLAN.md created.")
	fmt.Println()
	planData, _ := os.ReadFile("PLAN.md")
	fmt.Println(string(planData))
	return nil
}

func runPlanner(cfg *agentConfig) {
	projectDir, _ := os.Getwd()

	t0 := time.Now()
	system := buildPlannerSystem(projectDir)
	if core := skills.LoadAll([]string{"task-planner"}); core != "" {
		system += "\n\n" + core
	}
	timeout := time.Duration(cfg.PlannerTimeout) * time.Second
	msgs := []lmstudio.Message{
		{Role: "system", Content: system},
		{Role: "user", Content: buildPlannerPrompt(cfg.Goal, projectDir)},
	}
	fmt.Printf("  %s...\n", "Planning")
	callStart := time.Now()
	msg, stats, err := lmstudio.Chat(cfg.Model, msgs, nil, timeout)
	elapsed := time.Since(callStart)
	agentLog("chat: prompt=%d gen=%d time=%.1fs", stats.PromptTokens, stats.GeneratedTokens, elapsed.Seconds())
	agentLog("Planner: %.1fs", time.Since(t0).Seconds())
	if err != nil {
		agentLog("Planner error: %v", err)
		return
	}

	preview := msg.Content
	if len(preview) > 400 {
		preview = preview[:400]
	}
	agentLog("Planner raw: %q", preview)

	content := extractPlanContent(msg.Content)
	if content == "" {
		agentLog("Planner: empty response")
		return
	}

	if err := os.WriteFile("PLAN.md", []byte(content), 0644); err != nil {
		agentLog("Planner: could not write PLAN.md: %v", err)
	}
}

// extractPlanContent strips preamble/postamble from a model-generated PLAN.md.
func extractPlanContent(s string) string {
	s = strings.TrimSpace(s)
	// Strip thinking block
	if idx := strings.Index(s, "</think>"); idx >= 0 {
		s = strings.TrimSpace(s[idx+len("</think>"):])
	}
	// Unwrap markdown code block (```markdown ... ``` or ``` ... ```)
	if strings.HasPrefix(s, "```") {
		if nl := strings.Index(s, "\n"); nl >= 0 {
			inner := s[nl+1:]
			if end := strings.LastIndex(inner, "```"); end >= 0 {
				inner = strings.TrimSpace(inner[:end])
			}
			s = inner
		}
	}
	if idx := strings.Index(s, "## Files"); idx >= 0 {
		return s[idx:]
	}
	if strings.Contains(s, "- [ ]") {
		return s
	}
	return ""
}

func runCombinedPlanner(cfg *agentConfig) (string, error) {
	projectDir, _ := os.Getwd()

	var prompt string
	if cfg.Complexity == "trivial" {
		prompt = fmt.Sprintf(`Write TWO files in sequence using the Write tool.

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
	} else {
		prompt = buildPlannerPrompt(cfg.Goal, projectDir) + "\n\nAfter writing PLAN.md, immediately write the FIRST source file listed in ## Files. Do not pause between the two writes. Stop after the first source file is written."
	}

	systemPrompt := buildPlannerSystem(projectDir)
	if skillContent := skills.LoadAll([]string{"task-planner"}); skillContent != "" {
		systemPrompt += "\n\n" + skillContent
	}

	combinedTimeout := time.Duration(cfg.PlannerTimeout+cfg.WriterTimeout) * time.Second
	sess := agent.NewSession(systemPrompt)
	sess.WatchFunc = func() bool {
		if _, e := os.Stat("PLAN.md"); e != nil {
			return false
		}
		p, e := plan.Parse("PLAN.md")
		if e != nil || p == nil || len(p.Tasks) == 0 {
			return false
		}
		_, e = os.Stat(p.Tasks[0].FilePath)
		return e == nil
	}
	_, err := sess.Run(cfg.Model, prompt, "Planning", 30, "", combinedTimeout)
	if err != nil {
		if _, e := os.Stat("PLAN.md"); e != nil {
			agentLog("Combined planner: %v", err)
		}
	}

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

// ── Writer ────────────────────────────────────────────────────────────────────

func runWriter(cfg *agentConfig, targetFile, prompt, autonomousSystem string) bool {
	if dir := filepath.Dir(targetFile); dir != "." {
		os.MkdirAll(dir, 0755)
	}

	writeRules := "REMINDER: Call Write ONCE for the file you are given. Complete, runnable content. Stop immediately after. Nothing else."
	systemPrompt := autonomousSystem + "\n\n" + writeRules

	sess := agent.NewSession(systemPrompt)
	sess.Tools = agent.WriterToolDefs
	timeout := time.Duration(cfg.WriterTimeout) * time.Second
	ok, err := sess.Run(cfg.Model, prompt, "Writing", 15, targetFile, timeout)
	if err != nil {
		agentLog("Writer: %v", err)
	}
	return ok
}

// ── Test gate ─────────────────────────────────────────────────────────────────

func runTests(cmd, logFile string) bool {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	f, _ := os.Create(logFile)
	c := exec.CommandContext(ctx, "bash", "-c", cmd)
	c.Stdout = f
	c.Stderr = f
	err := c.Run()
	f.Close()
	return err == nil
}

const repairMaxIters = 6

const repairLoopRules = `REPAIR RULES — follow exactly:
1. You are fixing failing tests. Each turn, make ONE targeted change: call Edit, or Write to replace a whole file.
2. Do NOT run any commands. The test is run for you after each edit and the new output is shown to you.
3. Only modify files that already exist. Do not create new files. Do not touch PLAN.md.
4. Call the tool immediately — no prose, no explanation. Stop after one tool call.`

func runTestRepairLoop(cfg *agentConfig, testCmd, testLog string, p *plan.Plan, autonomousSystem string) bool {
	sess := agent.NewSession(autonomousSystem + "\n\n" + repairLoopRules)
	sess.Tools = agent.RepairToolDefs
	timeout := time.Duration(cfg.WriterTimeout) * time.Second
	runTest := func() (bool, string) {
		ok := runTests(testCmd, testLog)
		return ok, tailFile(testLog, 60)
	}
	reapply := func() { reapplyMakefileFix(p) }
	return sess.RepairLoop(cfg.Model, cfg.Goal, repairMaxIters, timeout, runTest, reapply)
}

func runRepairLint(cfg *agentConfig, lintCmd, filePath, lintHead, autonomousSystem string) {
	fileContent := ""
	if data, err := os.ReadFile(filePath); err == nil && len(data) < 3000 {
		fileContent = fmt.Sprintf("\n\nCurrent file:\n```\n%s\n```", string(data))
	}

	hint := ""
	isSingleQuoteIssue := strings.Contains(lintHead, "missing closing quote in string literal") ||
		(strings.Contains(lintHead, "invalid-syntax") && strings.Contains(lintHead, "execute('"))
	isMissingParen := strings.Contains(lintHead, "invalid-syntax") && strings.Contains(lintHead, "execute(") && !isSingleQuoteIssue
	if isSingleQuoteIssue {
		hint = "\n\nHINT: The error is a multi-line SQL string using single quotes — Python does not allow single-quoted strings to span multiple lines. Use Write to rewrite the file, replacing every multi-line single-quoted string with a triple-quoted string. Example: conn.execute('SQL\\n...') → conn.execute(\"\"\"SQL\\n...\"\"\")."
	} else if isMissingParen {
		hint = "\n\nHINT: The error is a missing closing ')' after a triple-quoted string in an execute() call. Find the line that ends with `\"\"\"` where the matching `execute(\"\"\"` has no closing `)`, and add `)` after the closing `\"\"\"`."
	}

	fixRules := fmt.Sprintf(`REPAIR PROTOCOL:
- Call Edit to make the smallest targeted change to fix %s. Only use Write if you must replace the entire file.
- Only modify %s. Do not create new files or modify other files.
- Do not modify PLAN.md.`, filePath, filePath)

	history := repairHistory()
	prompt := fmt.Sprintf("GOAL: %s\n\nLint failed for %s. Fix it now.\n\nLint errors:\n%s%s%s%s", cfg.Goal, filePath, lintHead, hint, fileContent, history)
	systemPrompt := autonomousSystem + "\n\n" + fixRules

	sess := agent.NewSession(systemPrompt)
	sess.Tools = agent.RepairToolDefs
	timeout := time.Duration(cfg.WriterTimeout) * time.Second
	_, err := sess.Run(cfg.Model, prompt, "Repairing", 4, "", timeout)
	if err != nil {
		agentLog("Lint repair: %v", err)
	}
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

	testLog := filepath.Join(logDir, "tests-final.log")
	if runTestRepairLoop(cfg, testCmd, testLog, p, autonomousSystem) {
		return nil
	}
	recordFailedRepair("final test gate: repair loop exhausted", tailFile(testLog, 30))
	fmt.Printf("\n  %s\n\n", ui.Red("Tests still failing after repair loop. Giving up."))
	return fmt.Errorf("final tests failed")
}

func reapplyMakefileFix(p *plan.Plan) {
	if p == nil {
		return
	}
	for _, task := range p.Tasks {
		if _, err := os.Stat(task.FilePath); err != nil {
			continue
		}
		if !plan.IsBuildFile(task.FilePath) || !strings.EqualFold(filepath.Base(task.FilePath), "makefile") {
			continue
		}
		if fixed, _ := sensors.FixMakefileSpaceIndent(task.FilePath); fixed {
			agentLog("Re-applied space-indent fix to %s after repair.", task.FilePath)
		}
		if fixed, _ := sensors.FixOrphanTopLevelCommands(task.FilePath); fixed {
			agentLog("Re-applied orphan-commands fix to %s after repair.", task.FilePath)
		}
		if fixed, _ := sensors.FixNoTargets(task.FilePath); fixed {
			agentLog("Re-applied no-targets fix to %s after repair.", task.FilePath)
		}
		if fixed, _ := sensors.FixInlineRecipe(task.FilePath); fixed {
			agentLog("Re-applied inline-recipe fix to %s after repair.", task.FilePath)
		}
		if fixed, _ := sensors.FixDuplicateVar(task.FilePath); fixed {
			agentLog("Re-applied duplicate-var fix to %s after repair.", task.FilePath)
		}
	}
}

func recordFailedRepair(label, errorSnippet string) {
	const planFile = "PLAN.md"
	data, err := os.ReadFile(planFile)
	if err != nil {
		return
	}
	content := string(data)

	snippet := strings.TrimSpace(errorSnippet)
	if len(strings.Split(snippet, "\n")) > 5 {
		lines := strings.Split(snippet, "\n")
		snippet = strings.Join(lines[:5], "\n")
	}

	entry := fmt.Sprintf("- %s — still failing. Error:\n  ```\n  %s\n  ```\n",
		label, strings.ReplaceAll(snippet, "\n", "\n  "))

	const header = "\n## Repair History\n"
	if idx := strings.Index(content, header); idx >= 0 {
		content = content[:idx+len(header)] + entry + content[idx+len(header):]
	} else {
		content = strings.TrimRight(content, "\n") + "\n" + header + entry
	}
	_ = os.WriteFile(planFile, []byte(content), 0644)
}

func repairHistory() string {
	data, err := os.ReadFile("PLAN.md")
	if err != nil {
		return ""
	}
	const header = "## Repair History"
	idx := strings.Index(string(data), header)
	if idx < 0 {
		return ""
	}
	section := strings.TrimSpace(string(data)[idx:])
	return "\n\n" + section + "\n\nDo NOT repeat approaches listed in Repair History above."
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

func headFile(path string, lines int) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	ls := strings.Split(string(data), "\n")
	if len(ls) <= lines {
		return string(data)
	}
	return strings.Join(ls[:lines], "\n")
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

func buildPlannerSystem(projectDir string) string {
	return fmt.Sprintf("You are a planning agent in: %s\nOutput ONLY the raw PLAN.md markdown. No preamble, no explanation, no code blocks.", projectDir)
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
- Only install packages that are explicitly listed in PLAN.md.
- Never read from stdin (Console.ReadLine, input(), scanf, etc.) unless the goal explicitly says "interactive". Programs that read stdin hang in non-interactive test environments. Use hardcoded values or command-line arguments instead.`, projectDir)
}

func buildPlannerPrompt(goal, projectDir string) string {
	return fmt.Sprintf("Output PLAN.md markdown for the following goal. No preamble, no code blocks, no explanation — only the raw markdown starting with ## Files.\n\nGOAL: %s\nDIR: %s", goal, projectDir)
}

func buildWritePrompt(goal string, task *plan.Task, p *plan.Plan, projectDir string) string {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("GOAL: %s\n\n## Plan\n%s", goal, p.PlanContext))

	existing := plan.RelevantFilesContext(p, task.FilePath)
	if existing != "" {
		sb.WriteString("\n\n## Reference files (do not rewrite)\n" + existing)
		if isTestFile(task.FilePath) {
			sb.WriteString("\nCRITICAL: Call EXACT method/function names from the reference files above. Do not rename or alias them.\n")
		}
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

// ── Lint ─────────────────────────────────────────────────────────────────────

func lintCommand(filePath string, p *plan.Plan) string {
	if plan.IsBuildFile(filePath) {
		return ""
	}
	ext := strings.ToLower(filepath.Ext(filePath))

	hasMakefile := false
	for _, t := range p.Tasks {
		if strings.EqualFold(filepath.Base(t.FilePath), "makefile") {
			hasMakefile = true
			break
		}
	}

	hasCargo := false
	for _, t := range p.Tasks {
		if strings.EqualFold(filepath.Base(t.FilePath), "cargo.toml") {
			hasCargo = true
			break
		}
	}
	hasTsConfig := false
	for _, t := range p.Tasks {
		base := strings.ToLower(filepath.Base(t.FilePath))
		if base == "tsconfig.json" || base == "tsconfig.base.json" {
			hasTsConfig = true
			break
		}
	}

	switch ext {
	case ".py":
		if _, err := exec.LookPath("ruff"); err == nil {
			return "ruff check --select=E9,F " + filePath
		}
		return "python3 -m py_compile " + filePath
	case ".go":
		if hasMakefile {
			return ""
		}
		dir := filepath.Dir(filePath)
		if dir == "." {
			return "go vet ."
		}
		return "go vet ./" + dir + "/..."
	case ".rs":
		if hasCargo {
			return "cargo check"
		}
		base := filepath.Base(filePath)
		stem := strings.TrimSuffix(base, filepath.Ext(base))
		return fmt.Sprintf("rustc --edition=2021 -Dwarnings %s -o /tmp/mu_lint_%s && rm -f /tmp/mu_lint_%s", filePath, stem, stem)
	case ".ts", ".tsx":
		if _, err := exec.LookPath("tsc"); err != nil {
			return ""
		}
		if hasTsConfig {
			return "tsc --noEmit"
		}
		return "tsc --noEmit --strict --target ES2020 --module commonjs " + filePath
	case ".c", ".h":
		if hasMakefile {
			return ""
		}
		return "gcc -fsyntax-only -Wall " + filePath
	case ".cpp", ".cc", ".cxx", ".hpp":
		if hasMakefile {
			return ""
		}
		return "g++ -fsyntax-only -Wall " + filePath
	}
	return ""
}

func runLint(lintCmd, logFile string) bool {
	f, _ := os.Create(logFile)
	defer f.Close()
	c := exec.Command("bash", "-c", lintCmd)
	c.Stdout = f
	c.Stderr = f
	return c.Run() == nil
}

func fixDemonstrationScript(planFile string, p *plan.Plan, goal string) bool {
	if p == nil {
		return false
	}
	goalLower := strings.ToLower(goal)
	isDemo := strings.Contains(goalLower, "show") || strings.Contains(goalLower, "demonstrate")
	hasAPI := strings.Contains(goalLower, "api") || strings.Contains(goalLower, "server") ||
		strings.Contains(goalLower, "endpoint") || strings.Contains(goalLower, "rest") ||
		strings.Contains(goalLower, "http")
	if !isDemo || hasAPI {
		return false
	}
	if !strings.Contains(strings.ToLower(p.TestCommand), "pytest") {
		return false
	}

	var mainFile string
	var testPaths []string
	for _, t := range p.Tasks {
		base := filepath.Base(t.FilePath)
		dir := filepath.Dir(t.FilePath)
		isTest := strings.HasPrefix(base, "test_") || base == "conftest.py" ||
			strings.Contains(dir, "test")
		if isTest {
			testPaths = append(testPaths, t.FilePath)
		} else if strings.HasSuffix(t.FilePath, ".py") && mainFile == "" {
			mainFile = t.FilePath
		}
	}
	if mainFile == "" || len(testPaths) == 0 {
		return false
	}

	data, err := os.ReadFile(planFile)
	if err != nil {
		return false
	}
	lines := strings.Split(string(data), "\n")
	var out []string
	for _, line := range lines {
		skip := false
		for _, tp := range testPaths {
			if strings.Contains(line, tp) || strings.Contains(line, filepath.Base(tp)) {
				skip = true
				break
			}
		}
		if skip {
			continue
		}
		if strings.TrimSpace(line) == strings.TrimSpace(p.TestCommand) {
			line = "python3 " + mainFile
		}
		out = append(out, line)
	}
	return os.WriteFile(planFile, []byte(strings.Join(out, "\n")), 0644) == nil
}
