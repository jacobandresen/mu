package theme

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
)

// ListItem is one entry returned by List.
type ListItem struct {
	Name string
	Path string
}

// List finds all *.yaml files under dir, parses them, and returns them
// sorted by name (case-insensitive). Files that fail to parse are skipped.
func List(dir string) ([]ListItem, error) {
	var items []ListItem
	err := filepath.WalkDir(dir, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return nil
		}
		if filepath.Ext(path) != ".yaml" {
			return nil
		}
		s, err := ParseScheme(path)
		if err != nil || s.Name == "" {
			return nil
		}
		items = append(items, ListItem{Name: s.Name, Path: path})
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Slice(items, func(i, j int) bool {
		return items[i].Name < items[j].Name
	})
	return items, nil
}

// Preview prints an ANSI colour swatch for the scheme to stdout, matching
// the output of the original theme.lua preview command.
func Preview(s *Scheme) {
	labelsLo := []string{"Background", "Alt Bg", "Selection", "Comments",
		"Dark Fg", "Foreground", "Light Fg", "Light Bg"}
	labelsHi := []string{"Red", "Orange", "Yellow", "Green",
		"Cyan", "Blue", "Magenta", "Brown"}

	fmt.Println()
	fmt.Printf("  \033[1m%s\033[0m\n", s.Name)
	if s.Author != "" {
		fmt.Printf("  by %s\n", s.Author)
	}
	fmt.Println()

	// base00–07 swatches
	fmt.Print("  ")
	for i := 0; i <= 7; i++ {
		fmt.Print(bgBlock(s.Palette[fmt.Sprintf("%02x", i)]))
	}
	fmt.Print("\n  ")
	for i := 0; i <= 7; i++ {
		fmt.Printf(" %c ", labelsLo[i][0])
	}
	fmt.Print("\n\n  ")

	// base08–0f swatches
	for i := 8; i <= 15; i++ {
		fmt.Print(bgBlock(s.Palette[fmt.Sprintf("%02x", i)]))
	}
	fmt.Print("\n  ")
	for i := 0; i <= 7; i++ {
		fmt.Printf(" %c ", labelsHi[i][0])
	}
	fmt.Print("\n\n")

	// accents on background
	if bg := s.Palette["00"]; bg != "" {
		fmt.Print("  Accents on background:\n  ")
		for i := 8; i <= 15; i++ {
			hex := s.Palette[fmt.Sprintf("%02x", i)]
			if hex != "" {
				fmt.Print(fgOnBg(hex, bg))
			} else {
				fmt.Print("       ")
			}
		}
		fmt.Print("\n\n")
	}

	// full palette listing
	fmt.Println("  Palette:")
	for i := 0; i <= 15; i++ {
		slot := fmt.Sprintf("%02x", i)
		if hex := s.Palette[slot]; hex != "" {
			fmt.Printf("  %s base%s #%s\n", bgBlock(hex), slot, hex)
		}
	}
	fmt.Println()
}

func bgBlock(hex string) string {
	if hex == "" {
		return "   "
	}
	r, g, b := hexToRGB(hex)
	return fmt.Sprintf("\033[48;2;%d;%d;%dm   \033[0m", r, g, b)
}

func fgOnBg(fghex, bghex string) string {
	fr, fg, fb := hexToRGB(fghex)
	br, bg, bb := hexToRGB(bghex)
	return fmt.Sprintf("\033[38;2;%d;%d;%dm\033[48;2;%d;%d;%dm %s \033[0m",
		fr, fg, fb, br, bg, bb, fghex)
}

func hexToRGB(hex string) (int, int, int) {
	if len(hex) != 6 {
		return 0, 0, 0
	}
	r, _ := strconv.ParseInt(hex[0:2], 16, 32)
	g, _ := strconv.ParseInt(hex[2:4], 16, 32)
	b, _ := strconv.ParseInt(hex[4:6], 16, 32)
	return int(r), int(g), int(b)
}

var colorSchemeRE = regexp.MustCompile(`config\.color_scheme\s*=[^\n]*`)

// SetWezterm replaces the color_scheme line in a .wezterm.lua file.
func SetWezterm(configPath, schemeName string) error {
	data, err := os.ReadFile(configPath)
	if err != nil {
		return fmt.Errorf("read %s: %w", configPath, err)
	}
	newLine := fmt.Sprintf(`config.color_scheme = "%s (base16)"`, schemeName)
	if !colorSchemeRE.Match(data) {
		return fmt.Errorf("no config.color_scheme line found in %s", configPath)
	}
	updated := colorSchemeRE.ReplaceAll(data, []byte(newLine))
	return os.WriteFile(configPath, updated, 0644)
}

var themeKeyRE = regexp.MustCompile(`"theme"\s*:\s*"[^"]*"`)

// SetClaude updates the "theme" key in claude's settings.json based on the
// scheme's variant ("light" → "light-ansi", otherwise "dark-ansi").
// Returns the theme name that was written.
func SetClaude(settingsPath, yamlPath string) (string, error) {
	s, err := ParseScheme(yamlPath)
	if err != nil {
		return "", fmt.Errorf("parse scheme: %w", err)
	}

	claudeTheme := "dark-ansi"
	if s.Variant == "light" {
		claudeTheme = "light-ansi"
	}

	data, err := os.ReadFile(settingsPath)
	if err != nil {
		return "", fmt.Errorf("read %s: %w", settingsPath, err)
	}
	if !themeKeyRE.Match(data) {
		return "", fmt.Errorf("no \"theme\" key found in %s", settingsPath)
	}
	updated := themeKeyRE.ReplaceAll(data, []byte(fmt.Sprintf(`"theme": "%s"`, claudeTheme)))
	if err := os.WriteFile(settingsPath, updated, 0644); err != nil {
		return "", err
	}
	return claudeTheme, nil
}
