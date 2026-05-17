package ollama

import (
	_ "embed"
	"encoding/json"
	"os"
	"os/exec"
	"strings"
)

//go:embed models-catalog.json
var embeddedCatalog []byte

type ModelSpec struct {
	ID            string   `json:"id"`
	Launch        bool     `json:"_launch"`
	ContextWindow int      `json:"contextWindow"`
	Input         []string `json:"input"`
	Reasoning     bool     `json:"reasoning"`
	Description   string   `json:"description"`
}

type catalog struct {
	Models []ModelSpec `json:"models"`
}

func KnownModels(catalogPath string) (map[string]ModelSpec, error) {
	data := embeddedCatalog
	if catalogPath != "" {
		if d, err := os.ReadFile(catalogPath); err == nil {
			data = d
		}
	}
	var c catalog
	if err := json.Unmarshal(data, &c); err != nil {
		return map[string]ModelSpec{}, nil
	}
	m := make(map[string]ModelSpec, len(c.Models))
	for _, spec := range c.Models {
		m[spec.ID] = spec
	}
	return m, nil
}

// CatalogPath returns an override path from MU_CATALOG_PATH, or empty string
// to use the embedded catalog.
func CatalogPath() string {
	return os.Getenv("MU_CATALOG_PATH")
}

func ReadDefaultModel(settingsPath string) string {
	data, err := os.ReadFile(settingsPath)
	if err != nil {
		return ""
	}
	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		return ""
	}
	if v, ok := m["model"].(string); ok {
		return v
	}
	return ""
}

func UpdateSettingsDefault(settingsPath, model string) error {
	data, _ := os.ReadFile(settingsPath)
	var m map[string]any
	if err := json.Unmarshal(data, &m); err != nil {
		m = map[string]any{}
	}
	m["model"] = model
	out, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(settingsPath, out, 0644)
}

func GetInstalledModels() ([]string, error) {
	out, err := exec.Command("ollama", "list").Output()
	if err != nil {
		return nil, err
	}
	var models []string
	for i, line := range strings.Split(string(out), "\n") {
		if i == 0 || strings.TrimSpace(line) == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) > 0 {
			models = append(models, fields[0])
		}
	}
	return models, nil
}
