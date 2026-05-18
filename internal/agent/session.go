package agent

import (
	"fmt"
	"os"
	"time"

	"github.com/jacobandresen/mu/internal/ollama"
	"github.com/jacobandresen/mu/internal/ui"
)

type Session struct {
	SystemPrompt string
	Tools        []ollama.ToolDef // if nil, defaults to ToolDefs
	WatchFunc    func() bool      // optional: called after each tool dispatch; exit early if true
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
// thinking: "off" → appends /no_think, "medium"/"high" → appends /think, "" → none
func (s *Session) Run(model, userPrompt, thinking, label string, maxTurns int, watchFile string, timeout time.Duration) (bool, error) {
	prompt := userPrompt
	switch thinking {
	case "off":
		prompt += "\n/no_think"
	case "medium", "high":
		prompt += "\n/think"
	}

	msgs := []ollama.Message{
		{Role: "system", Content: s.SystemPrompt},
		{Role: "user", Content: prompt},
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
		msg, err := ollama.Chat(model, msgs, tools, remaining)
		if err != nil {
			return false, fmt.Errorf("chat: %w", err)
		}

		msgs = append(msgs, msg)

		if len(msg.ToolCalls) == 0 {
			if watchFile != "" {
				_, statErr := os.Stat(watchFile)
				return statErr == nil, nil
			}
			return true, nil
		}

		for _, tc := range msg.ToolCalls {
			result := DispatchTool(tc.Function.Name, tc.Function.Arguments)
			msgs = append(msgs, ollama.Message{Role: "tool", Content: result})

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
