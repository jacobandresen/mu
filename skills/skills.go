package skills

import (
	"embed"
	"strings"
)

//go:embed */SKILL.md
var FS embed.FS

func Load(name string) string {
	data, err := FS.ReadFile(name + "/SKILL.md")
	if err != nil {
		return ""
	}
	return string(data)
}

// LoadAll loads multiple named skills and joins them with a blank line separator.
func LoadAll(names []string) string {
	var parts []string
	for _, name := range names {
		if content := Load(name); content != "" {
			parts = append(parts, content)
		}
	}
	return strings.Join(parts, "\n\n")
}
