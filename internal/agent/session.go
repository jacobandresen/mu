package agent

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/jacobandresen/mu/internal/lmstudio"
	"github.com/jacobandresen/mu/internal/ui"
)

type Session struct {
	SystemPrompt string
	Tools        []lmstudio.ToolDef // if nil, defaults to ToolDefs
	WatchFunc    func() bool        // optional: called after each tool dispatch; exit early if true
}

func NewSession(systemPrompt string) *Session {
	return &Session{SystemPrompt: systemPrompt}
}

// Run sends userPrompt to the model and dispatches tool calls in a loop until:
//   - no tool calls returned (model finished)
//   - watchFile exists (early exit — file was written)
//   - maxTurns exceeded
//   - timeout exceeded
//
// label: shown in the progress bar (e.g. "Planning", "Writing")
func (s *Session) Run(model, userPrompt, label string, maxTurns int, watchFile string, timeout time.Duration) (bool, error) {
	msgs := []lmstudio.Message{
		{Role: "system", Content: s.SystemPrompt},
		{Role: "user", Content: userPrompt},
	}

	fmt.Printf("  %s...\n", ui.Cyan(label))

	deadline := time.Now().Add(timeout)

	for turn := 0; turn < maxTurns; turn++ {
		remaining := time.Until(deadline)
		if remaining <= 0 {
			return false, fmt.Errorf("timeout after %v", timeout)
		}

		tools := s.Tools
		if tools == nil {
			tools = ToolDefs
		}
		msg, err := chatOrRetry(model, msgs, tools, deadline)
		if err != nil {
			return false, fmt.Errorf("chat: %w", err)
		}

		msgs = append(msgs, msg)

		if len(msg.ToolCalls) == 0 {
			if watchFile != "" {
				if _, statErr := os.Stat(watchFile); statErr == nil {
					return true, nil
				}
				// File absent — model wrote code as prose; try to extract and save it
				if code, ok := extractCodeBlock(msg.Content, watchFile); ok && code != "" {
					if writeErr := os.WriteFile(watchFile, []byte(code), 0644); writeErr == nil {
						return true, nil
					}
				}
				return false, nil
			}
			// Repair mode (no watchFile): model responded with text but called no tool.
			// Force another turn so the model actually edits the file.
			if turn < maxTurns-1 {
				msgs = append(msgs, lmstudio.Message{Role: "user", Content: "Call Write or Edit now. Do not write text — call the tool immediately."})
				continue
			}
			return false, fmt.Errorf("max turns reached without tool call")
		}

		for _, tc := range msg.ToolCalls {
			switch tc.Function.Name {
			case "Write", "Edit":
				if path, ok := tc.Function.Arguments["path"].(string); ok {
					fmt.Printf("==> [mu-agent] tool: %s(%q)\n", tc.Function.Name, path)
				}
			case "Bash":
				if cmd, ok := tc.Function.Arguments["command"].(string); ok {
					if len(cmd) > 80 {
						cmd = cmd[:77] + "..."
					}
					fmt.Printf("==> [mu-agent] tool: Bash(%q)\n", cmd)
				}
			default:
				fmt.Printf("==> [mu-agent] tool: %s\n", tc.Function.Name)
			}
			result := DispatchTool(tc.Function.Name, tc.Function.Arguments)
			msgs = append(msgs, lmstudio.Message{Role: "tool", Content: result})

			if watchFile != "" {
				if _, statErr := os.Stat(watchFile); statErr == nil {
					return true, nil
				}
			}
			if s.WatchFunc != nil && s.WatchFunc() {
				return true, nil
			}
		}
	}

	if watchFile != "" {
		_, statErr := os.Stat(watchFile)
		return statErr == nil, fmt.Errorf("max turns reached")
	}
	return false, fmt.Errorf("max turns reached")
}

// RepairLoop drives an iterative edit→test→observe repair conversation in a single
// session, mirroring the behaviour that made the v0.3 (pi) harness reach 6/7: the
// model edits, the harness runs the test and feeds the new output back, and the loop
// repeats until the test passes or the iteration budget is exhausted.
//
//	runTest:  runs the project's test command, returns (passed, tailOutput)
//	reapply:  optional deterministic fixes applied before each test run (may be nil)
//
// Returns true if the test passes by the end of the loop.
func (s *Session) RepairLoop(model, goal string, maxIters int, perTurnTimeout time.Duration,
	runTest func() (bool, string), reapply func()) bool {

	tools := s.Tools
	if tools == nil {
		tools = RepairToolDefs
	}
	msgs := []lmstudio.Message{{Role: "system", Content: s.SystemPrompt}}
	fmt.Printf("  %s...\n", ui.Cyan("Repairing"))

	for iter := 0; iter < maxIters; iter++ {
		if reapply != nil {
			reapply()
		}
		passed, testOut := runTest()
		if passed {
			if iter > 0 {
				fmt.Printf("==> [mu-agent] Repair: tests pass after %d edit(s).\n", iter)
			}
			return true
		}

		var content string
		if iter == 0 {
			content = fmt.Sprintf("GOAL: %s\n\nThe project's tests are failing. Make ONE targeted change (call Edit, or Write to replace a whole file) to fix the underlying cause. Do not run any commands — the test is run for you and the new output is shown after each edit. Test output:\n\n%s", goal, testOut)
		} else {
			content = fmt.Sprintf("Still failing after your last edit. Latest test output:\n\n%s\n\nMake ONE more targeted edit to fix the remaining cause. Do not repeat an edit that did not help.", testOut)
		}
		msgs = append(msgs, lmstudio.Message{Role: "user", Content: content})

		// Drive up to 3 model turns this iteration to obtain a single tool call.
		deadline := time.Now().Add(perTurnTimeout)
		edited := false
		for t := 0; t < 3 && time.Now().Before(deadline); t++ {
			msg, err := chatOrRetry(model, msgs, tools, deadline)
			if err != nil {
				fmt.Printf("==> [mu-agent] Repair: %v\n", err)
				break
			}
			msgs = append(msgs, msg)
			if len(msg.ToolCalls) == 0 {
				if t < 2 {
					msgs = append(msgs, lmstudio.Message{Role: "user", Content: "Call Edit or Write now — do not write prose."})
					continue
				}
				break
			}
			for _, tc := range msg.ToolCalls {
				logToolCall(tc)
				result := DispatchTool(tc.Function.Name, tc.Function.Arguments)
				msgs = append(msgs, lmstudio.Message{Role: "tool", Content: result})
			}
			edited = true
			break
		}
		if !edited {
			fmt.Printf("==> [mu-agent] Repair iter %d: model produced no edit.\n", iter+1)
		}
	}

	// Test the final edit (the loop tests at the start of each iteration, so the last
	// edit hasn't been verified yet).
	if reapply != nil {
		reapply()
	}
	passed, _ := runTest()
	return passed
}

// logToolCall prints a one-line trace of a dispatched tool call.
func logToolCall(tc lmstudio.ToolCall) {
	if tc.Function.Name == "Write" || tc.Function.Name == "Edit" {
		if path, ok := tc.Function.Arguments["path"].(string); ok {
			fmt.Printf("==> [mu-agent] tool: %s(%q)\n", tc.Function.Name, path)
			return
		}
	}
	fmt.Printf("==> [mu-agent] tool: %s\n", tc.Function.Name)
}

// extractCodeBlock extracts the first fenced code block from content that matches the
// file extension of filePath. Tries language-specific fences first, then a generic fence.
func extractCodeBlock(content, filePath string) (string, bool) {
	base := strings.ToLower(filepath.Base(filePath))
	ext := strings.ToLower(strings.TrimPrefix(filepath.Ext(filePath), "."))
	if ext == "" {
		ext = base // e.g., "makefile"
	}
	for _, lang := range codeBlockLangs(ext) {
		if code, ok := extractFence(content, "```"+lang); ok {
			return code, true
		}
	}
	if code, ok := extractFence(content, "```"); ok {
		return code, true
	}
	return "", false
}

func extractFence(content, opener string) (string, bool) {
	idx := strings.Index(content, opener+"\n")
	if idx < 0 {
		return "", false
	}
	start := idx + len(opener) + 1
	rest := content[start:]
	end := strings.Index(rest, "\n```")
	if end < 0 {
		return "", false
	}
	return rest[:end], true
}

func codeBlockLangs(ext string) []string {
	switch ext {
	case "py":
		return []string{"python", "py"}
	case "go":
		return []string{"go"}
	case "c":
		return []string{"c"}
	case "h":
		return []string{"c", "h"}
	case "cpp", "cc", "cxx":
		return []string{"cpp", "c++"}
	case "rs":
		return []string{"rust", "rs"}
	case "cs":
		return []string{"csharp", "cs"}
	case "js":
		return []string{"javascript", "js"}
	case "ts":
		return []string{"typescript", "ts"}
	case "sh":
		return []string{"bash", "sh", "shell"}
	case "toml":
		return []string{"toml"}
	case "yaml", "yml":
		return []string{"yaml", "yml"}
	case "json":
		return []string{"json"}
	case "makefile":
		return []string{"makefile", "make"}
	default:
		return []string{ext}
	}
}

// chatOrRetry calls lmstudio.Chat and retries up to 2 times on connection errors.
// Unlike the Ollama path there is no model-reload between retries; LM Studio manages
// model memory itself. Each attempt is logged individually.
func chatOrRetry(model string, msgs []lmstudio.Message, tools []lmstudio.ToolDef, deadline time.Time) (lmstudio.Message, error) {
	const maxRetries = 2
	const backoff = 5 * time.Second

	var lastErr error
	for attempt := 0; attempt <= maxRetries; attempt++ {
		remaining := time.Until(deadline)
		if remaining <= 0 {
			if lastErr != nil {
				return lmstudio.Message{}, lastErr
			}
			return lmstudio.Message{}, fmt.Errorf("deadline exceeded")
		}
		callStart := time.Now()
		msg, stats, err := lmstudio.Chat(model, msgs, tools, remaining)
		elapsed := time.Since(callStart)
		fmt.Printf("==> [mu-agent] chat: prompt=%d gen=%d time=%.1fs\n",
			stats.PromptTokens, stats.GeneratedTokens, elapsed.Seconds())

		if err != nil && attempt < maxRetries {
			fmt.Printf("==> [mu-agent] Chat error — retrying in %v (retry %d/%d): %v\n",
				backoff, attempt+1, maxRetries, err)
			time.Sleep(backoff)
			lastErr = err
			continue
		}
		return msg, err
	}
	return lmstudio.Message{}, lastErr
}
