package agent

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/jacobandresen/mu/internal/ollama"
)

var ToolDefs = []ollama.ToolDef{
	{
		Type: "function",
		Function: ollama.ToolFunction{
			Name:        "Write",
			Description: "Write a file with the given content, creating parent directories as needed.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"path":    map[string]any{"type": "string", "description": "Absolute or relative file path"},
					"content": map[string]any{"type": "string", "description": "Complete file content"},
				},
				"required": []string{"path", "content"},
			},
		},
	},
	{
		Type: "function",
		Function: ollama.ToolFunction{
			Name:        "Edit",
			Description: "Replace the first occurrence of old_string with new_string in the given file.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"path":       map[string]any{"type": "string", "description": "File path"},
					"old_string": map[string]any{"type": "string", "description": "Exact string to replace"},
					"new_string": map[string]any{"type": "string", "description": "Replacement string"},
				},
				"required": []string{"path", "old_string", "new_string"},
			},
		},
	},
	{
		Type: "function",
		Function: ollama.ToolFunction{
			Name:        "Bash",
			Description: "Run a shell command and return combined stdout+stderr.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"command": map[string]any{"type": "string", "description": "Shell command to execute"},
				},
				"required": []string{"command"},
			},
		},
	},
	{
		Type: "function",
		Function: ollama.ToolFunction{
			Name:        "Read",
			Description: "Read and return the contents of a file.",
			Parameters: map[string]any{
				"type": "object",
				"properties": map[string]any{
					"path": map[string]any{"type": "string", "description": "File path to read"},
				},
				"required": []string{"path"},
			},
		},
	},
}

// RepairToolDefs is Write + Edit + Read only — no Bash.
// Repair sessions already have the error output in the prompt; removing Bash
// prevents the model from re-running test/lint commands instead of just fixing the file.
var RepairToolDefs []ollama.ToolDef

func init() {
	for _, t := range ToolDefs {
		if t.Function.Name != "Bash" {
			RepairToolDefs = append(RepairToolDefs, t)
		}
	}
}

func DispatchTool(name string, args map[string]any) string {
	switch name {
	case "Write":
		path, _ := args["path"].(string)
		content, _ := args["content"].(string)
		return toolWrite(path, content)
	case "Edit":
		path, _ := args["path"].(string)
		oldStr, _ := args["old_string"].(string)
		newStr, _ := args["new_string"].(string)
		return toolEdit(path, oldStr, newStr)
	case "Bash":
		command, _ := args["command"].(string)
		return toolBash(command)
	case "Read":
		path, _ := args["path"].(string)
		return toolRead(path)
	default:
		return fmt.Sprintf("unknown tool: %s", name)
	}
}

func toolWrite(path, content string) string {
	if dir := filepath.Dir(path); dir != "." {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return fmt.Sprintf("error creating directories: %v", err)
		}
	}
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		return fmt.Sprintf("error writing file: %v", err)
	}
	return fmt.Sprintf("wrote %s (%d bytes)", path, len(content))
}

func toolEdit(path, oldStr, newStr string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Sprintf("error reading file: %v", err)
	}
	content := string(data)
	if !strings.Contains(content, oldStr) {
		return fmt.Sprintf("old_string not found in %s", path)
	}
	fixed := strings.Replace(content, oldStr, newStr, 1)
	if err := os.WriteFile(path, []byte(fixed), 0644); err != nil {
		return fmt.Sprintf("error writing file: %v", err)
	}
	return fmt.Sprintf("edited %s", path)
}

func toolBash(command string) string {
	cmd := exec.Command("bash", "-c", command)
	out, err := cmd.CombinedOutput()
	result := string(out)
	if err != nil {
		if result == "" {
			return fmt.Sprintf("exit error: %v", err)
		}
		return result
	}
	return result
}

func toolRead(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Sprintf("error reading file: %v", err)
	}
	return string(data)
}
