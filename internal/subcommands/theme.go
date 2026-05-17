package subcommands

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/jacobandresen/mu/internal/theme"
	"github.com/spf13/cobra"
)

func NewThemeCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "theme",
		Short: "Pick and apply a base16 colour scheme",
		Long:  "Opens an fzf picker over the base16 colour scheme catalogue and applies it.",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runTheme()
		},
	}
	cmd.AddCommand(
		newThemeListCmd(),
		newThemePreviewCmd(),
		newThemeSetCmd(),
		newThemeSetClaudeCmd(),
	)
	return cmd
}

// ── sub-subcommands (called by fzf --preview and internally) ─────────────────

func newThemeListCmd() *cobra.Command {
	return &cobra.Command{
		Use:    "list <dir>",
		Short:  "List base16 schemes as name<TAB>path pairs",
		Hidden: true,
		Args:   cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			items, err := theme.List(args[0])
			if err != nil {
				return err
			}
			for _, it := range items {
				fmt.Printf("%s\t%s\n", it.Name, it.Path)
			}
			return nil
		},
	}
}

func newThemePreviewCmd() *cobra.Command {
	return &cobra.Command{
		Use:    "preview <yaml_path>",
		Short:  "Print ANSI colour swatch for a base16 scheme file",
		Hidden: true,
		Args:   cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			s, err := theme.ParseScheme(args[0])
			if err != nil {
				return err
			}
			theme.Preview(s)
			return nil
		},
	}
}

func newThemeSetCmd() *cobra.Command {
	return &cobra.Command{
		Use:    "set <config_path> <scheme_name>",
		Short:  "Update config.color_scheme in a .wezterm.lua file",
		Hidden: true,
		Args:   cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			return theme.SetWezterm(args[0], args[1])
		},
	}
}

func newThemeSetClaudeCmd() *cobra.Command {
	return &cobra.Command{
		Use:    "set-claude <settings_path> <yaml_path>",
		Short:  "Update the theme key in claude settings.json",
		Hidden: true,
		Args:   cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			name, err := theme.SetClaude(args[0], args[1])
			if err != nil {
				return err
			}
			fmt.Println(name)
			return nil
		},
	}
}

// ── interactive picker ────────────────────────────────────────────────────────

func runTheme() error {
	home, _ := os.UserHomeDir()
	xdgData := os.Getenv("XDG_DATA_HOME")
	if xdgData == "" {
		xdgData = filepath.Join(home, ".local", "share")
	}
	schemesDir := os.Getenv("SCHEMES_DIR")
	if schemesDir == "" {
		schemesDir = filepath.Join(xdgData, "tinted-theming", "schemes")
	}
	base16Dir := filepath.Join(schemesDir, "base16")

	// Clone or sparse-update the schemes repo
	if _, err := os.Stat(filepath.Join(schemesDir, ".git")); err == nil {
		_ = exec.Command("git", "-C", schemesDir, "pull", "--quiet", "--ff-only").Run()
	} else {
		_ = os.MkdirAll(filepath.Dir(schemesDir), 0755)
		c := exec.Command("git", "clone", "--depth=1", "--filter=blob:none", "--sparse",
			"https://github.com/tinted-theming/schemes", schemesDir, "--quiet")
		c.Stdout, c.Stderr = os.Stdout, os.Stderr
		if err := c.Run(); err != nil {
			return fmt.Errorf("clone schemes: %w", err)
		}
		_ = exec.Command("git", "-C", schemesDir, "sparse-checkout", "set", "base16").Run()
	}

	if _, err := os.Stat(base16Dir); err != nil {
		return fmt.Errorf("base16 schemes not found at %s", base16Dir)
	}

	// Resolve mu binary path for the fzf preview command
	muBin, err := os.Executable()
	if err != nil {
		muBin = "mu"
	}
	muBin, _ = filepath.EvalSymlinks(muBin)

	// List schemes
	items, err := theme.List(base16Dir)
	if err != nil {
		return fmt.Errorf("list schemes: %w", err)
	}

	// Build fzf input
	var lines []string
	for _, it := range items {
		lines = append(lines, it.Name+"\t"+it.Path)
	}

	fzf := exec.Command("fzf",
		"--delimiter=\t",
		"--with-nth=1",
		"--prompt=theme> ",
		"--preview="+muBin+" theme preview {2}",
		"--preview-window=right:45%",
	)
	fzf.Stdin = strings.NewReader(strings.Join(lines, "\n"))
	fzf.Stderr = os.Stderr
	chosen, err := fzf.Output()
	if err != nil || len(chosen) == 0 {
		return nil // user cancelled
	}

	line := strings.TrimRight(string(chosen), "\n")
	parts := strings.SplitN(line, "\t", 2)
	schemeName := parts[0]
	yamlPath := ""
	if len(parts) == 2 {
		yamlPath = parts[1]
	}

	weztermCfg := filepath.Join(home, ".wezterm.lua")
	if _, err := os.Stat(weztermCfg); err != nil {
		return fmt.Errorf("%s not found", weztermCfg)
	}

	if err := theme.SetWezterm(weztermCfg, schemeName); err != nil {
		return err
	}
	fmt.Printf("updated %s -> %s (base16)\n", weztermCfg, schemeName)

	// Update claude settings if present
	claudeCfg := filepath.Join(home, ".claude", "settings.json")
	if _, err := os.Stat(claudeCfg); err == nil && yamlPath != "" {
		name, err := theme.SetClaude(claudeCfg, yamlPath)
		if err == nil {
			fmt.Printf("updated %s -> %s\n", claudeCfg, name)
		}
	}

	return nil
}
