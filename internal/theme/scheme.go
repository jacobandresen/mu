package theme

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strings"
)

// Scheme holds the parsed fields of a base16 YAML file.
type Scheme struct {
	Name    string
	Author  string
	System  string
	Slug    string
	Variant string            // "light" or "dark"
	Palette map[string]string // "00"–"0f" → 6-digit lowercase hex
}

var (
	paletteHeaderRE = regexp.MustCompile(`^palette\s*:`)
	nonIndentRE     = regexp.MustCompile(`^\S`)
	// matches: base0A: "#RRGGBB" or base0A: #RRGGBB or base0A: RRGGBB
	slotRE = regexp.MustCompile(`(?i)base([0-9a-f]{2})\s*:\s*"?#?([0-9a-f]{6})`)
)

// ParseScheme reads a base16 YAML file and returns a Scheme.
func ParseScheme(path string) (*Scheme, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	s := &Scheme{Palette: make(map[string]string)}
	inPalette := false

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()

		if paletteHeaderRE.MatchString(line) {
			inPalette = true
		} else if inPalette && nonIndentRE.MatchString(line) {
			inPalette = false
		}

		if !inPalette {
			for _, field := range []string{"name", "author", "system", "slug", "variant"} {
				re := regexp.MustCompile(`(?i)^` + field + `\s*:\s*(.+)$`)
				if m := re.FindStringSubmatch(line); m != nil {
					val := unquote(strings.TrimSpace(m[1]))
					switch field {
					case "name":
						s.Name = val
					case "author":
						s.Author = val
					case "system":
						s.System = val
					case "slug":
						s.Slug = val
					case "variant":
						s.Variant = val
					}
				}
			}
		}

		if m := slotRE.FindStringSubmatch(line); m != nil {
			s.Palette[strings.ToLower(m[1])] = strings.ToLower(m[2])
		}
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	if s.Name == "" && len(s.Palette) == 0 {
		return nil, fmt.Errorf("not a valid base16 scheme: %s", path)
	}
	return s, nil
}

func unquote(s string) string {
	s = strings.TrimPrefix(s, `"`)
	s = strings.TrimSuffix(s, `"`)
	s = strings.TrimPrefix(s, `'`)
	s = strings.TrimSuffix(s, `'`)
	return s
}
