package subcommands

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/jacobandresen/mu/internal/ollama"
	"github.com/jacobandresen/mu/internal/ui"
	"github.com/spf13/cobra"
)

var piAgentDir = func() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".pi", "agent")
}()

func settingsPath() string { return filepath.Join(piAgentDir, "settings.json") }
func modelsPath() string   { return filepath.Join(piAgentDir, "models.json") }

func NewModelCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "model [command]",
		Short: "Manage the ollama model used by the agent",
		Long: `Manage the ollama model used by the agent.
With no subcommand, opens an interactive fzf picker.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			return runModelPicker()
		},
	}

	var keepAlive string
	loadCmd := &cobra.Command{
		Use:   "load [model]",
		Short: "Pull if missing, set as default, load into memory",
		RunE: func(cmd *cobra.Command, args []string) error {
			model := ""
			if len(args) > 0 {
				model = args[0]
			}
			return runModelLoad(model, keepAlive)
		},
	}
	loadCmd.Flags().StringVar(&keepAlive, "keep-alive", "30m", "Keep-alive duration")

	var unloadModel string
	unloadCmd := &cobra.Command{
		Use:   "unload",
		Short: "Evict from memory (keeps it installed on disk)",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runModelUnload(unloadModel)
		},
	}
	unloadCmd.Flags().StringVar(&unloadModel, "model", "", "Model to unload (default: from settings.json)")

	var tsv bool
	modelsCmd := &cobra.Command{
		Use:   "models",
		Short: "List curated models; --tsv for fzf-friendly output",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runModelList(tsv)
		},
	}
	modelsCmd.Flags().BoolVar(&tsv, "tsv", false, "Tab-separated output for fzf")

	modelInfoCmd := &cobra.Command{
		Use:   "model-info <model>",
		Short: "Print detail for a single curated model",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return runModelInfo(args[0])
		},
	}

	statusCmd := &cobra.Command{
		Use:   "status",
		Short: "Show installed models and agent config",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runModelStatus()
		},
	}

	moveStorageCmd := &cobra.Command{
		Use:   "move-storage",
		Short: "Move /var/lib/ollama → /opt/ollama (Linux only)",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runMoveStorage()
		},
	}

	cmd.AddCommand(loadCmd, unloadCmd, modelsCmd, modelInfoCmd, statusCmd, moveStorageCmd)
	return cmd
}

func runModelPicker() error {
	cat, err := ollama.KnownModels(ollama.CatalogPath())
	if err != nil {
		return err
	}
	installed, _ := ollama.GetInstalledModels()
	instSet := make(map[string]bool)
	for _, m := range installed {
		instSet[m] = true
	}
	def := ollama.ReadDefaultModel(settingsPath())

	var lines []string
	for id, spec := range cat {
		marks := []string{}
		if instSet[id] {
			marks = append(marks, "installed")
		}
		if id == def {
			marks = append(marks, "default")
		}
		ctx := fmt.Sprintf("%dk", spec.ContextWindow/1024)
		suffix := ""
		if len(marks) > 0 {
			suffix = "  [" + strings.Join(marks, ", ") + "]"
		}
		lines = append(lines, fmt.Sprintf("%-20s %5s  %s%s\t%s", id, ctx, spec.Description, suffix, id))
	}

	fzf := exec.Command("fzf", "--ansi", "--delimiter=\t", "--with-nth=1", "--preview=mu model model-info {2}")
	fzf.Stdin = strings.NewReader(strings.Join(lines, "\n"))
	fzf.Stderr = os.Stderr
	out, err := fzf.Output()
	if err != nil || len(out) == 0 {
		return nil
	}
	parts := strings.Split(strings.TrimRight(string(out), "\n"), "\t")
	model := strings.TrimSpace(parts[len(parts)-1])
	if model == "" {
		return nil
	}
	return runModelLoad(model, "30m")
}

func runModelLoad(model, keepAlive string) error {
	if model == "" {
		model = ollama.ReadDefaultModel(settingsPath())
		if model == "" {
			model = "qwen3:4b"
		}
	}
	installed, err := ollama.GetInstalledModels()
	if err != nil {
		return fmt.Errorf("list installed models: %w", err)
	}
	found := false
	for _, m := range installed {
		if m == model {
			found = true
			break
		}
	}
	if !found {
		fmt.Printf("Pulling %s...\n", model)
		c := exec.Command("ollama", "pull", model)
		c.Stdout, c.Stderr = os.Stdout, os.Stderr
		if err := c.Run(); err != nil {
			return fmt.Errorf("pull %s: %w", model, err)
		}
	} else {
		fmt.Printf("%s: already installed\n", ui.Green(model))
	}

	if err := ollama.UpdateSettingsDefault(settingsPath(), model); err != nil {
		fmt.Fprintf(os.Stderr, "WARNING: could not update settings.json: %v\n", err)
	}
	if err := upsertModelsJSON(modelsPath(), model); err != nil {
		fmt.Fprintf(os.Stderr, "WARNING: could not update models.json: %v\n", err)
	}

	loaded, _ := ollama.ListPS()
	for _, m := range loaded {
		if m != model {
			_ = ollama.UnloadModel(m)
		}
	}

	if keepAlive == "" {
		keepAlive = "30m"
	}
	fmt.Printf("Loading %s (keep_alive=%s)...\n", model, keepAlive)
	if err := ollama.LoadModel(model, keepAlive); err != nil {
		return fmt.Errorf("load model: %w", err)
	}
	fmt.Printf("Done. %s is resident for %s.\n", ui.Green(model), keepAlive)
	return nil
}

func runModelUnload(model string) error {
	if model == "" {
		model = ollama.ReadDefaultModel(settingsPath())
		if model == "" {
			return fmt.Errorf("no model specified and settings.json has no default")
		}
	}
	fmt.Printf("Unloading %s...\n", model)
	if err := ollama.UnloadModel(model); err != nil {
		return err
	}
	fmt.Printf("Done. %s unloaded from memory (still installed).\n", model)
	return nil
}

func runModelList(tsv bool) error {
	cat, err := ollama.KnownModels(ollama.CatalogPath())
	if err != nil {
		return err
	}
	installed, _ := ollama.GetInstalledModels()
	instSet := make(map[string]bool)
	for _, m := range installed {
		instSet[m] = true
	}
	def := ollama.ReadDefaultModel(settingsPath())

	if tsv {
		for id, spec := range cat {
			marks := []string{}
			if instSet[id] {
				marks = append(marks, "installed")
			}
			if id == def {
				marks = append(marks, "default")
			}
			ctx := fmt.Sprintf("%dk", spec.ContextWindow/1024)
			suffix := ""
			if len(marks) > 0 {
				suffix = "  [" + strings.Join(marks, ", ") + "]"
			}
			fmt.Printf("%-20s %5s  %s%s\t%s\n", id, ctx, spec.Description, suffix, id)
		}
		return nil
	}

	fmt.Println(ui.Bold("Curated models"))
	var rows [][]string
	for id, spec := range cat {
		marks := []string{}
		if instSet[id] {
			marks = append(marks, ui.Green("installed"))
		}
		if id == def {
			marks = append(marks, ui.Cyan("default"))
		}
		ctx := fmt.Sprintf("%dk", spec.ContextWindow/1024)
		caps := strings.Join(spec.Input, ", ")
		if spec.Reasoning {
			caps += ", reasoning"
		}
		rows = append(rows, []string{ui.Green(id), ui.Cyan(ctx), caps, strings.Join(marks, ", ")})
	}
	ui.PrintTable([]string{"Model", "Context", "Capabilities", "Status"}, rows)
	return nil
}

func runModelInfo(model string) error {
	cat, err := ollama.KnownModels(ollama.CatalogPath())
	if err != nil {
		return err
	}
	spec, ok := cat[model]
	if !ok {
		fmt.Printf("unknown curated model: %s\n", model)
		return nil
	}
	installed, _ := ollama.GetInstalledModels()
	instSet := make(map[string]bool)
	for _, m := range installed {
		instSet[m] = true
	}
	def := ollama.ReadDefaultModel(settingsPath())
	ctx := fmt.Sprintf("%dk", spec.ContextWindow/1024)
	caps := strings.Join(spec.Input, ", ")
	if spec.Reasoning {
		caps += ", reasoning"
	}
	fmt.Println(ui.Bold(model))
	fmt.Println()
	fmt.Println(spec.Description)
	fmt.Println()
	fmt.Printf("%-14s %s\n", "Context", ctx)
	fmt.Printf("%-14s %s\n", "Capabilities", caps)
	fmt.Printf("%-14s %s\n", "Installed", boolStr(instSet[model]))
	fmt.Printf("%-14s %s\n", "Default", boolStr(def == model))
	return nil
}

func runModelStatus() error {
	fmt.Println(ui.Bold("Installed ollama models"))
	installed, err := ollama.GetInstalledModels()
	if err != nil {
		fmt.Println(ui.Dim("  (could not query ollama)"))
	} else if len(installed) == 0 {
		fmt.Println(ui.Dim("  (none)"))
	} else {
		rows := make([][]string, len(installed))
		for i, m := range installed {
			rows[i] = []string{ui.Green(m)}
		}
		ui.PrintTable([]string{"Model"}, rows)
	}

	fmt.Println()
	fmt.Printf("%s  %s\n", ui.Bold("Agent settings"), ui.Dim("("+settingsPath()+")"))
	data, e := os.ReadFile(settingsPath())
	if e != nil {
		fmt.Println(ui.Red("  settings.json not found"))
	} else {
		var cfg map[string]any
		_ = json.Unmarshal(data, &cfg)
		showKeys := []string{"defaultModel", "defaultProvider", "enableSkillCommands", "quietStartup"}
		var rows [][]string
		for _, k := range showKeys {
			if v, ok := cfg[k]; ok {
				rows = append(rows, []string{ui.Cyan(k), fmt.Sprintf("%v", v)})
			}
		}
		if len(rows) > 0 {
			ui.PrintTable([]string{"Key", "Value"}, rows)
		}
	}

	fmt.Println()
	fmt.Printf("%s  %s\n", ui.Bold("Configured models"), ui.Dim("("+modelsPath()+")"))
	mdata, e := os.ReadFile(modelsPath())
	if e != nil {
		fmt.Println(ui.Red("  models.json not found"))
	} else {
		var d map[string]any
		_ = json.Unmarshal(mdata, &d)
		var rows [][]string
		if providers, ok := d["providers"].(map[string]any); ok {
			for provider, pv := range providers {
				if pdata, ok := pv.(map[string]any); ok {
					if models, ok := pdata["models"].([]any); ok {
						for _, mv := range models {
							if m, ok := mv.(map[string]any); ok {
								mid, _ := m["id"].(string)
								ctx := "?"
								if cw, ok := m["contextWindow"].(float64); ok {
									ctx = fmt.Sprintf("%dk", int(cw)/1024)
								}
								var parts []string
								if inp, ok := m["input"].([]any); ok {
									for _, v := range inp {
										if s, ok := v.(string); ok {
											parts = append(parts, s)
										}
									}
								}
								caps := strings.Join(parts, ", ")
								if r, ok := m["reasoning"].(bool); ok && r {
									caps += ", reasoning"
								}
								rows = append(rows, []string{ui.Green(mid), ui.Yellow(provider), ui.Cyan(ctx), caps})
							}
						}
					}
				}
			}
		}
		if len(rows) > 0 {
			ui.PrintTable([]string{"Model", "Provider", "Context", "Capabilities"}, rows)
		} else {
			fmt.Println(ui.Dim("  (no models configured)"))
		}
	}
	fmt.Println()
	return nil
}

func runMoveStorage() error {
	fmt.Print("sudo password: ")
	r := bufio.NewReader(os.Stdin)
	pass, _ := r.ReadString('\n')
	pass = strings.TrimRight(pass, "\n")

	sudoRun := func(args ...string) error {
		c := exec.Command("sudo", append([]string{"-S"}, args...)...)
		c.Stdin = strings.NewReader(pass + "\n")
		c.Stdout, c.Stderr = os.Stdout, os.Stderr
		return c.Run()
	}
	if err := sudoRun("true"); err != nil {
		return fmt.Errorf("wrong sudo password")
	}
	fmt.Println("Stopping ollama...")
	_ = sudoRun("systemctl", "stop", "ollama")
	if _, err := os.Stat("/opt/ollama"); err == nil {
		_ = sudoRun("systemctl", "start", "ollama")
		return fmt.Errorf("/opt/ollama already exists — aborting")
	}
	fmt.Println("Moving /var/lib/ollama -> /opt/ollama...")
	if err := sudoRun("mv", "/var/lib/ollama", "/opt/ollama"); err != nil {
		return err
	}
	fmt.Println("Creating symlink...")
	if err := sudoRun("ln", "-s", "/opt/ollama", "/var/lib/ollama"); err != nil {
		return err
	}
	fmt.Println("Starting ollama...")
	_ = sudoRun("systemctl", "start", "ollama")
	fmt.Println("Done. Verify with: ollama list")
	return nil
}

func boolStr(b bool) string {
	if b {
		return "yes"
	}
	return "no"
}

func upsertModelsJSON(path, model string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var d map[string]any
	if err := json.Unmarshal(data, &d); err != nil {
		return err
	}
	providers, _ := d["providers"].(map[string]any)
	if providers == nil {
		providers = map[string]any{}
		d["providers"] = providers
	}
	ollamaP, _ := providers["ollama"].(map[string]any)
	if ollamaP == nil {
		ollamaP = map[string]any{}
		providers["ollama"] = ollamaP
	}
	models, _ := ollamaP["models"].([]any)
	for _, mv := range models {
		if m, ok := mv.(map[string]any); ok {
			if m["id"] == model {
				fmt.Printf("models.json: '%s' already present\n", model)
				return nil
			}
		}
	}
	cat, _ := ollama.KnownModels(ollama.CatalogPath())
	entry := map[string]any{"id": model, "input": []string{"text"}}
	if spec, ok := cat[model]; ok {
		entry = map[string]any{
			"id":            spec.ID,
			"contextWindow": spec.ContextWindow,
			"input":         spec.Input,
		}
		if spec.Reasoning {
			entry["reasoning"] = true
		}
		if spec.Launch {
			entry["_launch"] = true
		}
	}
	ollamaP["models"] = append(models, entry)
	out, err := json.MarshalIndent(d, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(path, append(out, '\n'), 0644); err != nil {
		return err
	}
	fmt.Printf("models.json: added '%s'\n", model)
	return nil
}
