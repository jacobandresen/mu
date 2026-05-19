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

// LoadAll loads multiple named skills, strips YAML frontmatter from each,
// and joins them with a blank line separator.
func LoadAll(names []string) string {
	var parts []string
	for _, name := range names {
		if content := Load(name); content != "" {
			parts = append(parts, stripFrontmatter(content))
		}
	}
	return strings.Join(parts, "\n\n")
}

// stripFrontmatter removes the ---...--- YAML block at the start of a skill file.
func stripFrontmatter(s string) string {
	if !strings.HasPrefix(s, "---\n") {
		return s
	}
	end := strings.Index(s[4:], "\n---\n")
	if end < 0 {
		return s
	}
	return strings.TrimLeft(s[4+end+5:], "\n")
}
