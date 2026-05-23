package subcommands

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/jacobandresen/mu/internal/lmstudio"
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
		Short: "Browse and select LM Studio models",
		Long: `Browse and select LM Studio models.
With no subcommand, opens an interactive fzf picker.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			return runModelPicker()
		},
	}

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
		Short: "Show loaded models and agent config",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runModelStatus()
		},
	}

	cmd.AddCommand(modelsCmd, modelInfoCmd, statusCmd)
	return cmd
}

func runModelPicker() error {
	cat, err := lmstudio.KnownModels(lmstudio.CatalogPath())
	if err != nil {
		return err
	}
	loaded, _ := lmstudio.ListModels()
	loadedSet := make(map[string]bool)
	for _, m := range loaded {
		loadedSet[m] = true
	}
	def := lmstudio.ReadDefaultModel(settingsPath())

	var lines []string
	for id, spec := range cat {
		marks := []string{}
		if loadedSet[id] {
			marks = append(marks, "loaded")
		}
		if id == def {
			marks = append(marks, "default")
		}
		ctx := fmt.Sprintf("%dk", spec.ContextWindow/1024)
		suffix := ""
		if len(marks) > 0 {
			suffix = "  [" + strings.Join(marks, ", ") + "]"
		}
		lines = append(lines, fmt.Sprintf("%-44s %5s  %s%s\t%s", id, ctx, spec.Description, suffix, id))
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
	// Save selection as default
	if err := lmstudio.UpdateSettingsDefault(settingsPath(), model); err != nil {
		fmt.Fprintf(os.Stderr, "WARNING: could not update settings.json: %v\n", err)
	}
	fmt.Printf("Selected: %s\nLoad this model in LM Studio, then run: mu agent \"your goal\"\n", ui.Green(model))
	return nil
}

func runModelList(tsv bool) error {
	cat, err := lmstudio.KnownModels(lmstudio.CatalogPath())
	if err != nil {
		return err
	}
	loaded, _ := lmstudio.ListModels()
	loadedSet := make(map[string]bool)
	for _, m := range loaded {
		loadedSet[m] = true
	}
	def := lmstudio.ReadDefaultModel(settingsPath())

	if tsv {
		for id, spec := range cat {
			marks := []string{}
			if loadedSet[id] {
				marks = append(marks, "loaded")
			}
			if id == def {
				marks = append(marks, "default")
			}
			ctx := fmt.Sprintf("%dk", spec.ContextWindow/1024)
			suffix := ""
			if len(marks) > 0 {
				suffix = "  [" + strings.Join(marks, ", ") + "]"
			}
			fmt.Printf("%-44s %5s  %s%s\t%s\n", id, ctx, spec.Description, suffix, id)
		}
		return nil
	}

	fmt.Println(ui.Bold("Curated models (load in LM Studio before running mu agent)"))
	var rows [][]string
	for id, spec := range cat {
		marks := []string{}
		if loadedSet[id] {
			marks = append(marks, ui.Green("loaded"))
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
	cat, err := lmstudio.KnownModels(lmstudio.CatalogPath())
	if err != nil {
		return err
	}
	spec, ok := cat[model]
	if !ok {
		fmt.Printf("unknown curated model: %s\n", model)
		return nil
	}
	loaded, _ := lmstudio.ListModels()
	loadedSet := make(map[string]bool)
	for _, m := range loaded {
		loadedSet[m] = true
	}
	def := lmstudio.ReadDefaultModel(settingsPath())
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
	fmt.Printf("%-14s %s\n", "Loaded", boolStr(loadedSet[model]))
	fmt.Printf("%-14s %s\n", "Default", boolStr(def == model))
	return nil
}

func runModelStatus() error {
	fmt.Println(ui.Bold("LM Studio loaded models"))
	loaded, err := lmstudio.ListModels()
	if err != nil {
		fmt.Println(ui.Dim("  (could not reach LM Studio at " + lmstudio.Host() + ")"))
	} else if len(loaded) == 0 {
		fmt.Println(ui.Dim("  (none — load a model in LM Studio first)"))
	} else {
		rows := make([][]string, len(loaded))
		for i, m := range loaded {
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
		showKeys := []string{"model", "defaultProvider", "enableSkillCommands", "quietStartup"}
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
	lmsP, _ := providers["lmstudio"].(map[string]any)
	if lmsP == nil {
		lmsP = map[string]any{}
		providers["lmstudio"] = lmsP
	}
	models, _ := lmsP["models"].([]any)
	for _, mv := range models {
		if m, ok := mv.(map[string]any); ok {
			if m["id"] == model {
				fmt.Printf("models.json: '%s' already present\n", model)
				return nil
			}
		}
	}
	cat, _ := lmstudio.KnownModels(lmstudio.CatalogPath())
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
	}
	lmsP["models"] = append(models, entry)
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
