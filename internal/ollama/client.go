package ollama

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

func CreateModel(name string, modelfileContent string) error {
	client := &http.Client{Timeout: 10 * time.Minute}
	body, _ := json.Marshal(map[string]any{
		"name":      name,
		"modelfile": modelfileContent,
		"stream":    true,
	})
	resp, err := client.Post(Host()+"/api/create", "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	dec := json.NewDecoder(resp.Body)
	for {
		var line map[string]any
		if err := dec.Decode(&line); err == io.EOF {
			break
		} else if err != nil {
			return err
		}
		if s, ok := line["status"].(string); ok {
			fmt.Fprintf(os.Stderr, "\r%s", s)
		}
		if e, ok := line["error"].(string); ok {
			return fmt.Errorf("create model: %s", e)
		}
	}
	fmt.Fprintln(os.Stderr)
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
