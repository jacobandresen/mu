package lmstudio

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

func Host() string {
	if h := os.Getenv("MU_LMSTUDIO_HOST"); h != "" {
		return h
	}
	return "http://localhost:1234"
}

var httpClient = &http.Client{Timeout: 10 * time.Second}

func IsRunning() bool {
	resp, err := httpClient.Get(Host() + "/v1/models")
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode == 200
}

// ListModels returns the IDs of all models currently loaded in LM Studio.
func ListModels() ([]string, error) {
	resp, err := httpClient.Get(Host() + "/v1/models")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var result struct {
		Data []struct {
			ID string `json:"id"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	ids := make([]string, len(result.Data))
	for i, m := range result.Data {
		ids[i] = m.ID
	}
	return ids, nil
}

// Message mirrors the Ollama type so callers need only change their import path.
type Message struct {
	Role      string     `json:"role"`
	Content   string     `json:"content,omitempty"`
	ToolCalls []ToolCall `json:"tool_calls,omitempty"`
}

type ToolCall struct {
	ID       string           `json:"id,omitempty"`
	Function ToolCallFunction `json:"function"`
}

// ToolCallFunction stores arguments as map[string]any after deserializing the
// JSON string that the OpenAI-compatible API returns on the wire.
type ToolCallFunction struct {
	Name      string         `json:"name"`
	Arguments map[string]any `json:"arguments"`
}

type ToolDef struct {
	Type     string       `json:"type"`
	Function ToolFunction `json:"function"`
}

type ToolFunction struct {
	Name        string         `json:"name"`
	Description string         `json:"description"`
	Parameters  map[string]any `json:"parameters"`
}

type ChatStats struct {
	PromptTokens    int
	GeneratedTokens int
}

// Chat sends a /v1/chat/completions request to LM Studio.
// temperature=0 is always included so every call is deterministic without
// needing a derived model (there is no `ollama create` equivalent in LM Studio).
func Chat(model string, messages []Message, tools []ToolDef, timeout time.Duration) (Message, ChatStats, error) {
	body := map[string]any{
		"model":       model,
		"messages":    messages,
		"stream":      false,
		"temperature": 0,
	}
	if len(tools) > 0 {
		body["tools"] = tools
	}

	b, err := json.Marshal(body)
	if err != nil {
		return Message{}, ChatStats{}, err
	}

	client := &http.Client{Timeout: timeout}
	resp, err := client.Post(Host()+"/v1/chat/completions", "application/json", bytes.NewReader(b))
	if err != nil {
		return Message{}, ChatStats{}, err
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return Message{}, ChatStats{}, err
	}
	if resp.StatusCode >= 400 {
		return Message{}, ChatStats{}, fmt.Errorf("lmstudio /v1/chat/completions: %s", string(data))
	}

	// Wire format: tool_calls[].function.arguments is a JSON-encoded string,
	// not a pre-parsed object. Deserialize it at the boundary.
	var wire struct {
		Choices []struct {
			Message struct {
				Role      string `json:"role"`
				Content   string `json:"content"`
				ToolCalls []struct {
					ID       string `json:"id"`
					Function struct {
						Name      string `json:"name"`
						Arguments string `json:"arguments"`
					} `json:"function"`
				} `json:"tool_calls"`
			} `json:"message"`
		} `json:"choices"`
		Usage struct {
			PromptTokens     int `json:"prompt_tokens"`
			CompletionTokens int `json:"completion_tokens"`
		} `json:"usage"`
	}

	if err := json.Unmarshal(data, &wire); err != nil {
		return Message{}, ChatStats{}, err
	}
	if len(wire.Choices) == 0 {
		return Message{}, ChatStats{}, fmt.Errorf("lmstudio: empty choices in response")
	}

	raw := wire.Choices[0].Message
	msg := Message{
		Role:    raw.Role,
		Content: raw.Content,
	}
	for _, tc := range raw.ToolCalls {
		var args map[string]any
		if tc.Function.Arguments != "" {
			_ = json.Unmarshal([]byte(tc.Function.Arguments), &args)
		}
		msg.ToolCalls = append(msg.ToolCalls, ToolCall{
			ID: tc.ID,
			Function: ToolCallFunction{
				Name:      tc.Function.Name,
				Arguments: args,
			},
		})
	}

	return msg, ChatStats{
		PromptTokens:    wire.Usage.PromptTokens,
		GeneratedTokens: wire.Usage.CompletionTokens,
	}, nil
}
