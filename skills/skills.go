package skills

import "embed"

//go:embed task-planner/SKILL.md
var FS embed.FS

func Load(name string) string {
	data, err := FS.ReadFile(name + "/SKILL.md")
	if err != nil {
		return ""
	}
	return string(data)
}
