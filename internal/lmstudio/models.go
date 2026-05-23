package lmstudio

import (
	_ "embed"
	"encoding/json"
	"os"
)

//go:embed models-catalog.json
var embeddedCatalog []byte

type ModelSpec struct {
	ID            string   `json:"id"`
	ContextWindow int      `json:"contextWindow"`
	Input         []string `json:"input"`
	Reasoning     bool     `json:"reasoning"`
	Description   string   `json:"description"`
}

type catalog struct {
	Models []ModelSpec `json:"models"`
}

// KnownModels returns the curated model catalog. If catalogPath is non-empty and
// the file can be read, it overrides the embedded catalog.
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

// CatalogPath returns MU_CATALOG_PATH if set, otherwise empty string (use embedded).
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
