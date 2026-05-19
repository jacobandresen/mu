package ollama

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"
)

func Host() string {
	if h := os.Getenv("OLLAMA_HOST"); h != "" {
		return h
	}
	return "http://localhost:11434"
}

var httpClient = &http.Client{Timeout: 10 * time.Second}

func IsRunning() bool {
	resp, err := httpClient.Get(Host() + "/api/tags")
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode == 200
}

func post(path string, body any, timeout time.Duration) ([]byte, error) {
	b, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	client := &http.Client{Timeout: timeout}
	resp, err := client.Post(Host()+path, "application/json", bytes.NewReader(b))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("ollama %s: %s", path, string(data))
	}
	return data, nil
}

func ListPS() ([]string, error) {
	resp, err := httpClient.Get(Host() + "/api/ps")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var out struct {
		Models []struct {
			Name string `json:"name"`
		} `json:"models"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}
	names := make([]string, len(out.Models))
	for i, m := range out.Models {
		names[i] = m.Name
	}
	return names, nil
}

func LoadModel(model, keepAlive string) error {
	if keepAlive == "" {
		keepAlive = "30m"
	}
	_, err := post("/api/generate", map[string]any{
		"model":      model,
		"keep_alive": keepAlive,
	}, 5*time.Minute)
	return err
}

func UnloadModel(model string) error {
	_, err := post("/api/generate", map[string]any{
		"model":      model,
		"keep_alive": "0",
	}, 30*time.Second)
	return err
}

func ShowModel(model string) (map[string]any, error) {
	data, err := post("/api/show", map[string]any{"name": model}, 15*time.Second)
	if err != nil {
		return nil, err
	}
	var result map[string]any
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, err
	}
	return result, nil
}

func CreateModel(name, from string, params map[string]any) error {
	client := &http.Client{Timeout: 10 * time.Minute}
	body, _ := json.Marshal(map[string]any{
		"name":       name,
		"from":       from,
		"parameters": params,
		"stream":     false,
	})
	resp, err := client.Post(Host()+"/api/create", "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	var result map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return err
	}
	if e, ok := result["error"].(string); ok {
		return fmt.Errorf("create model: %s", e)
	}
	return nil
}

func UnloadOthers(keep string) error {
	loaded, err := ListPS()
	if err != nil {
		return err
	}
	for _, m := range loaded {
		if m != keep {
			_ = UnloadModel(m)
		}
	}
	return nil
}

// ── Chat API ──────────────────────────────────────────────────────────────────

type Message struct {
	Role      string     `json:"role"`
	Content   string     `json:"content,omitempty"`
	ToolCalls []ToolCall `json:"tool_calls,omitempty"`
}

type ToolCall struct {
	ID       string           `json:"id,omitempty"`
	Function ToolCallFunction `json:"function"`
}

type ToolCallFunction struct {
	Index     int            `json:"index,omitempty"`
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

func numCtx() int {
	if s := os.Getenv("MU_NUM_CTX"); s != "" {
		if n, err := strconv.Atoi(s); err == nil && n > 0 {
			return n
		}
	}
	return 4096
}

func NumCtx() int { return numCtx() }

func NumThread() int { return numThread() }

func numThread() int {
	if s := os.Getenv("MU_NUM_THREAD"); s != "" {
		if n, err := strconv.Atoi(s); err == nil && n > 0 {
			return n
		}
	}
	return 0
}

func numKeep() int {
	if s := os.Getenv("MU_NUM_KEEP"); s != "" {
		if n, err := strconv.Atoi(s); err == nil && n >= 0 {
			return n
		}
	}
	return -1 // -1 = not set, omit from options
}

func NumKeep() int { return numKeep() }

// ChatStats holds token usage returned by the Ollama API for a single chat call.
type ChatStats struct {
	PromptTokens    int
	GeneratedTokens int
}

func Chat(model string, messages []Message, tools []ToolDef, timeout time.Duration) (Message, ChatStats, error) {
	body := map[string]any{
		"model":    model,
		"messages": messages,
		"stream":   false,
	}
	if len(tools) > 0 {
		body["tools"] = tools
	}
	data, err := post("/api/chat", body, timeout)
	if err != nil {
		return Message{}, ChatStats{}, err
	}
	var resp struct {
		Message         Message `json:"message"`
		PromptEvalCount int     `json:"prompt_eval_count"`
		EvalCount       int     `json:"eval_count"`
	}
	if err := json.Unmarshal(data, &resp); err != nil {
		return Message{}, ChatStats{}, err
	}
	stats := ChatStats{
		PromptTokens:    resp.PromptEvalCount,
		GeneratedTokens: resp.EvalCount,
	}
	return resp.Message, stats, nil
}
