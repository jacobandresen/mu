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
	"github.com/jacobandresen/mu/internal/ollama"
	"github.com/jacobandresen/mu/internal/plan"
	"github.com/jacobandresen/mu/internal/sensors"
	"github.com/jacobandresen/mu/internal/ui"
	"github.com/jacobandresen/mu/skills"
	"github.com/spf13/cobra"
)

const logDir = ".mu"

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
	cfg.BaseModel = orEnv("qwen2.5-coder:7b", "MU_AGENT_BASE_MODEL")
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
	if err := ollama.LoadModel(cfg.AgentModel, "30m"); err != nil {
		agentLog("WARNING: could not pre-load model: %v", err)
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

	// Inject Cargo.toml when plan uses cargo but forgot to list it
	if fixed := sensors.FixMissingCargoToml("PLAN.md", p); fixed {
		agentLog("Injected Cargo.toml into plan (test command uses cargo but Cargo.toml was missing).")
		p, _ = plan.Parse("PLAN.md")
		currentPlan = p
	}

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
				retryCfg := cfg
				retryCfg.WriterThinking = "medium"
				if !runWriterWithSession(&retryCfg, task.FilePath, retryPrompt, autonomousSystem) {
					agentLog("Iteration %d: %s not written after retry.", i, task.FilePath)
					exitCode = 3
					return fmt.Errorf("stalled: model did not write %s", task.FilePath)
				}
			}
		}

		// Detect near-empty written file (e.g. writer produced only "import app" for a test file).
		// Any real source file is > 100 bytes; stubs from stalled models are much smaller.
		if fi, statErr := os.Stat(task.FilePath); statErr == nil && fi.Size() < 100 {
			ext := strings.ToLower(filepath.Ext(task.FilePath))
			isConfigLike := ext == ".txt" || ext == ".toml" || ext == ".mod" || ext == ".sum" ||
				ext == ".json" || ext == ".yaml" || ext == ".yml" || ext == ".lock"
			if !plan.IsBuildFile(task.FilePath) && !isConfigLike {
				agentLog("Writer produced near-empty %s (%d bytes) — retrying with thinking.", task.FilePath, fi.Size())
				_ = os.Remove(task.FilePath)
				stubRetryPrompt := fmt.Sprintf("Write file NOW: `%s`\nYou ONLY have the Write tool. Use it immediately — do not try to run commands or install packages.\nCall Write exactly once with the complete file contents. Stop immediately after.\n\nGOAL: %s\n%s",
					task.FilePath, cfg.Goal, p.PlanContext)
				retryCfg := cfg
				retryCfg.WriterThinking = "medium"
				if !runWriterWithSession(&retryCfg, task.FilePath, stubRetryPrompt, autonomousSystem) {
					agentLog("Iteration %d: %s still near-empty after retry.", i, task.FilePath)
				}
			}
		}

		// Post-write: fix go.mod with invalid top-level directives or bad versions
		if strings.EqualFold(filepath.Base(task.FilePath), "go.mod") {
			if fixedMod, _ := sensors.FixGoMod(task.FilePath); fixedMod {
				agentLog("Fixed go.mod: moved bare pkg directives into require block.")
			}
			if fixedVer, _ := sensors.FixGoModVersions(task.FilePath); fixedVer {
				agentLog("Fixed go.mod: replaced hallucinated version(s) with known-stable pins.")
			}
		}

		// Post-write: fix SDL2 include path (model writes SDL2/SDL.h; macOS homebrew needs SDL.h)
		if goalIsGraphical && sensors.IsSDLSource(task.FilePath) {
			if fixedSDL, _ := sensors.FixSDLInclude(task.FilePath); fixedSDL {
				agentLog("Fixed SDL2 include path in %s.", task.FilePath)
			}
		}

		// Post-write: fix .csproj TargetFramework and strip duplicate Compile items
		if strings.HasSuffix(task.FilePath, ".csproj") {
			if fixedFw, _ := sensors.FixCsprojTargetFramework(task.FilePath); fixedFw {
				agentLog("Fixed TargetFramework in %s to match installed dotnet.", task.FilePath)
			}
			if fixedCI, _ := sensors.FixCsprojCompileItems(task.FilePath); fixedCI {
				agentLog("Removed explicit <Compile Include> items from %s (SDK auto-includes .cs files).", task.FilePath)
			}
		}

		// Post-write: fix Makefile issues
		if plan.IsBuildFile(task.FilePath) && strings.EqualFold(filepath.Base(task.FilePath), "makefile") {
			if fixedTargets, _ := sensors.FixNoTargets(task.FilePath); fixedTargets {
				agentLog("Fixed Makefile: wrapped shell commands in all: target (model wrote plain script).")
			}
			if fixedInline, _ := sensors.FixInlineRecipe(task.FilePath); fixedInline {
				agentLog("Fixed Makefile: split inline recipe onto tab-indented line.")
			}
			if fixedDup, _ := sensors.FixDuplicateVar(task.FilePath); fixedDup {
				agentLog("Fixed Makefile: removed duplicate variable assignments (kept first definition).")
			}
			if fixedGo, _ := sensors.FixGoMakefile(task.FilePath); fixedGo {
				agentLog("Fixed Go Makefile: added go mod init + go get before go build.")
			}
			if fixedPy, _ := plan.FixPythonMakefileTest(task.FilePath); fixedPy {
				agentLog("Fixed Python Makefile: added PYTHONPATH=. before pytest.")
			}
		}

		// Post-write: fix Cargo.toml with orphan [lib] section pointing to non-existent file
		if strings.EqualFold(filepath.Base(task.FilePath), "cargo.toml") {
			if fixedLib, _ := sensors.FixCargoTomlOrphanLib(task.FilePath); fixedLib {
				agentLog("Fixed Cargo.toml: removed [lib] section referencing non-existent file.")
			}
		}

		// Lint gate: run linter immediately after each source file is written
		if lintCmd := lintCommand(task.FilePath, p); lintCmd != "" {
			lintLog := filepath.Join(logDir, fmt.Sprintf("lint-iter-%02d.log", i))
			if !runLint(lintCmd, lintLog) {
				// Try ruff --fix before invoking the model — ruff can auto-fix many F401s
				// and similar issues without LLM involvement, and does so correctly.
				if sensors.RuffAutoFix(task.FilePath) && runLint(lintCmd, lintLog) {
					agentLog("Lint auto-fixed (ruff --fix): %s", task.FilePath)
				} else {
					agentLog("Lint failed for %s — invoking repair.", task.FilePath)
					lintHead := headFile(lintLog, 60)
					deterministicFixed := (sensors.FixMultilineSingleQuote(task.FilePath, lintHead) ||
						sensors.FixMissingCloseParen(task.FilePath, lintHead) ||
						sensors.FixCargoTomlOrphanLibOnRust(task.FilePath, lintHead) ||
						sensors.FixRustPrintlnFormat(task.FilePath, lintHead)) &&
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
		// Running "make test" before the Makefile is written always fails.
		testCmd := p.TestCommand
		if testCmd != "" && isTestFile(task.FilePath) && !plan.HasPendingBuildFile(p) {
			testLog := filepath.Join(logDir, fmt.Sprintf("tests-iter-%02d.log", i))
			if !runTests(testCmd, testLog) {
				agentLog("Tests failing after %s — invoking repair agent.", task.FilePath)
				testTail := tailFile(testLog, 80)
				runRepair(&cfg, testCmd, testTail, autonomousSystem)
				if !runTests(testCmd, testLog) {
					agentLog("Tests still failing after repair for %s.", task.FilePath)
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

// graphicalRE matches goals that produce windowed/graphical programs that cannot be run headlessly
var graphicalRE = regexp.MustCompile(`(?i)SDL2|OpenGL|ncurses|wxwidgets`)

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

	if cfg.PlannerThinking == "" {
		cfg.PlannerThinking = "off"
	}
	if cfg.WriterThinking == "" {
		cfg.WriterThinking = "off"
	}

	ctxScale := 1.0
	if ollama.NumCtx() >= 8000 {
		ctxScale = 1.5
	}
	// num_thread=1 forces single-CPU inference — 5-10x slower than auto on Apple Silicon.
	// Double all timeouts so writers and repairs don't expire before the model finishes.
	if ollama.NumThread() == 1 {
		ctxScale *= 2.0
	}
	if cfg.PlannerTimeout == 0 {
		base := map[string]int{"trivial": 120, "simple": 200, "complex": 360, "hard": 480}[complexity]
		cfg.PlannerTimeout = int(float64(base) * ctxScale)
	}
	cfg.WriterTimeout = int(float64(map[string]int{"trivial": 90, "simple": 220, "complex": 300, "hard": 400}[complexity]) * ctxScale)

	if cfg.Combined == -1 {
		// Combined mode is disabled for single-thread inference: the combined prompt is
		// significantly larger than the planner-only prompt, causing consistent timeouts
		// when num_thread=1 makes prefill/generation ~8× slower than with auto threads.
		if (complexity == "trivial" || complexity == "simple") && ollama.NumThread() != 1 {
			cfg.Combined = 1
		} else {
			cfg.Combined = 0
		}
	}
}

// ── Model setup ──────────────────────────────────────────────────────────────

func ensureAgentModel(base string) (string, error) {
	parts := strings.SplitN(base, ":", 2)
	target := parts[0] + ":agent"

	if _, err := ollama.ShowModel(target); err == nil {
		return target, nil
	}

	agentLog("Creating %s (temperature=0, thinking disabled) from %s ...", target, base)

	params := map[string]any{"temperature": 0, "num_ctx": ollama.NumCtx()}
	if err := ollama.CreateModel(target, base, params); err != nil {
		agentLog("WARNING: ollama create failed — using %s (temperature uncontrolled)", base)
		return base, nil
	}

	// Update models.json
	_ = upsertModelsJSON(modelsPath(), target)
	return target, nil
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
	// Only count commits when a .git directory exists directly here (not an ancestor repo).
	// Without this check, target dirs nested inside a git repo (like dojo/) inherit its history.
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
			agentLog("Planning: %s (planner=%s writer=%s timeout=%ds complexity=%s)",
				cfg.Goal, cfg.PlannerThinking, cfg.WriterThinking, cfg.PlannerTimeout, cfg.Complexity)
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
	prompt := buildPlannerPrompt(cfg.Goal, projectDir)
	autonomousSystem := buildAutonomousSystem(projectDir)

	systemPrompt := autonomousSystem
	if skillContent := skills.Load("task-planner"); skillContent != "" {
		systemPrompt += "\n\n" + skillContent
	}

	sess := agent.NewSession(systemPrompt)
	timeout := time.Duration(cfg.PlannerTimeout) * time.Second
	_, err := sess.Run(cfg.AgentModel, prompt, cfg.PlannerThinking, "Planning", 20, "PLAN.md", timeout)
	if err != nil {
		agentLog("Planner: %v", err)
	}
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

	autonomousSystem := buildAutonomousSystem(projectDir)
	systemPrompt := autonomousSystem
	if skillContent := skills.Load("task-planner"); skillContent != "" {
		systemPrompt += "\n\n" + skillContent
	}

	combinedTimeout := time.Duration(cfg.PlannerTimeout+cfg.WriterTimeout) * time.Second
	sess := agent.NewSession(systemPrompt)
	// Exit as soon as PLAN.md and its first source file both exist — don't wait for
	// the model's "I'm done" response, which can time out after the files are written.
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
	_, err := sess.Run(cfg.AgentModel, prompt, cfg.PlannerThinking, "Planning", 30, "", combinedTimeout)
	if err != nil {
		// Suppress timeout noise when files were already written before the deadline fired
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
	return runWriterWithSession(cfg, targetFile, prompt, autonomousSystem)
}

func runWriterWithSession(cfg *agentConfig, targetFile, prompt, autonomousSystem string) bool {
	if dir := filepath.Dir(targetFile); dir != "." {
		os.MkdirAll(dir, 0755)
	}

	writeRules := "REMINDER: Call Write ONCE for the file you are given. Complete, runnable content. Stop immediately after. Nothing else."
	systemPrompt := autonomousSystem + "\n\n" + writeRules

	sess := agent.NewSession(systemPrompt)
	timeout := time.Duration(cfg.WriterTimeout) * time.Second
	ok, err := sess.Run(cfg.AgentModel, prompt, cfg.WriterThinking, "Writing", 15, targetFile, timeout)
	if err != nil {
		agentLog("Writer: %v", err)
	}
	return ok
}

// ── Test gate ─────────────────────────────────────────────────────────────────

// runTests runs cmd, writing output to logFile.  A hard 120-second wall-clock
// timeout prevents interactive programs (reading stdin) from hanging forever.
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

func runRepair(cfg *agentConfig, testCmd, testTail, autonomousSystem string) {
	fixRules := `REPAIR PROTOCOL:
- The test output is already provided below. Do not run any commands.
- Call Edit to make the smallest targeted change. Only use Write if you must replace the entire file.
- Only modify files that already exist in the project. Do not create new files.
- One tool call only. Do not modify PLAN.md.`

	history := repairHistory()
	prompt := fmt.Sprintf("GOAL: %s\n\nTests are failing. Fix the broken code now.\n\nTest output:\n%s%s", cfg.Goal, testTail, history)
	systemPrompt := autonomousSystem + "\n\n" + fixRules

	sess := agent.NewSession(systemPrompt)
	sess.Tools = agent.RepairToolDefs
	timeout := time.Duration(cfg.WriterTimeout) * time.Second
	_, err := sess.Run(cfg.AgentModel, prompt, cfg.WriterThinking, "Repairing", 4, "", timeout)
	if err != nil {
		agentLog("Repair: %v", err)
	}
}

func runRepairLint(cfg *agentConfig, lintCmd, filePath, lintHead, autonomousSystem string) {
	// Include file content only for small files to keep prompt size manageable.
	fileContent := ""
	if data, err := os.ReadFile(filePath); err == nil && len(data) < 3000 {
		fileContent = fmt.Sprintf("\n\nCurrent file:\n```\n%s\n```", string(data))
	}

	// Add targeted hint for common, hard-to-repair errors.
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
	_, err := sess.Run(cfg.AgentModel, prompt, "off", "Repairing", 4, "", timeout)
	if err != nil {
		agentLog("Lint repair: %v", err)
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

	maxRetries := 1
	for attempt := 0; attempt <= maxRetries; attempt++ {
		testLog := filepath.Join(logDir, "tests-final.log")
		if runTests(testCmd, testLog) {
			return nil
		}
		if attempt == maxRetries {
			recordFailedRepair("final test gate: all retries exhausted", tailFile(testLog, 30))
			fmt.Printf("\n  %s\n\n", ui.Red("Tests still failing after "+strconv.Itoa(maxRetries)+" retries. Giving up."))
			return fmt.Errorf("final tests failed")
		}
		agentLog("Final tests failed — repair retry %d / %d", attempt+1, maxRetries)
		testTail := tailFile(testLog, 200)
		runRepair(cfg, testCmd, testTail, autonomousSystem)
		// Repair model may revert harness fixes (e.g. restores wrong .csproj TargetFramework).
		// Re-apply them unconditionally after each repair attempt.
		reapplyCsprojFix(p)
		// Record this failed attempt so subsequent repair turns don't repeat the same approach.
		if !testsSilent(testCmd) {
			recordFailedRepair(fmt.Sprintf("test repair attempt %d", attempt+1), tailFile(testLog, 30))
		}
	}
	return nil
}

// reapplyCsprojFix re-runs fixCsprojTargetFramework on every .csproj listed in the plan.
// The repair model sometimes rewrites .csproj files and reverts the TargetFramework to an
// older version; calling this after each repair restores the correct value.
func reapplyCsprojFix(p *plan.Plan) {
	if p == nil {
		return
	}
	for _, task := range p.Tasks {
		if strings.HasSuffix(task.FilePath, ".csproj") {
			if _, err := os.Stat(task.FilePath); err == nil {
				if fixed, _ := sensors.FixCsprojTargetFramework(task.FilePath); fixed {
					agentLog("Re-applied TargetFramework fix to %s after repair.", task.FilePath)
				}
			}
		}
	}
}

// recordFailedRepair appends a note to PLAN.md's ## Repair History section so that
// subsequent repair turns know what was already tried and avoid repeating it.
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

// repairHistory reads any ## Repair History section from PLAN.md and returns it formatted
// for inclusion in a repair prompt, so the model avoids repeating failed approaches.
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
   - 'Go' with external libraries -> MUST include go.mod as the FIRST file in ## Files.
     The Makefile should run 'go mod tidy && go build' or equivalent.
     The go.mod file sets the module path and Go version; external imports are resolved at build time via the Makefile.

3. MAKEFILE COMPLETENESS: If the Test Command references a make target, the Makefile MUST define
   that target from the start. Define test targets with a recipe even if the test source file
   does not exist yet.

4. Module functions should return values rather than printing so they can be unit-tested.
   Exception: interactive or graphical programs.

5. Include '## Test Command' with a single shell command that exits non-zero on failure.
   All paths must be project-relative, not absolute.
   GRAPHICAL PROGRAMS: Test Command must be just 'make' (compile only).

6. Include '## Dependencies' listing the compiler, required tools, AND the lint tool for
   the language: Python → ruff, C/C++ → gcc or clang-tidy, Go → go vet (built-in),
   Rust → cargo clippy, TypeScript → tsc, C# → dotnet format (built-in with SDK).

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

// ── Lint ─────────────────────────────────────────────────────────────────────

// lintCommand returns the lint command for filePath, or "" to skip.
// Skips C/C++ files in Makefile projects (the compiler handles them via make).
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
		// ruff preferred; fall back to py_compile syntax-only check
		if _, err := exec.LookPath("ruff"); err == nil {
			return "ruff check --select=E9,F " + filePath
		}
		return "python3 -m py_compile " + filePath
	case ".go":
		// Skip go vet when Makefile handles the build — go vet requires deps to be
		// downloaded first, which the Makefile does via go mod tidy / go get.
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

// fixDemonstrationScript detects when the model adds unnecessary test files to a
// "show that X works" goal. In demonstration goals the program itself is the test;
// pytest is never needed. When found, removes test tasks and rewrites the test
// command to run the main script directly (python3 <file>).
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
		// Rewrite test command line
		if strings.TrimSpace(line) == strings.TrimSpace(p.TestCommand) {
			line = "python3 " + mainFile
		}
		out = append(out, line)
	}
	return os.WriteFile(planFile, []byte(strings.Join(out, "\n")), 0644) == nil
}
