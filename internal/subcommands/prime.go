package subcommands

import (
	"fmt"
	"os"
	"os/exec"

	"github.com/jacobandresen/mu/internal/ollama"
	"github.com/spf13/cobra"
)

func NewPrimeCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "prime",
		Short: "Pull all curated models and load the default into memory",
		Long: `Pulls every curated model from the embedded catalog, then loads the
configured default model into ollama memory. Safe to re-run.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			return runPrime()
		},
	}
}

func runPrime() error {
	cat, err := ollama.KnownModels(ollama.CatalogPath())
	if err != nil {
		return fmt.Errorf("load catalog: %w", err)
	}
	if len(cat) == 0 {
		return fmt.Errorf("model catalog is empty or not found at %s", ollama.CatalogPath())
	}

	for id := range cat {
		fmt.Printf("Pulling %s...\n", id)
		c := exec.Command("ollama", "pull", id)
		c.Stdout, c.Stderr = os.Stdout, os.Stderr
		if err := c.Run(); err != nil {
			fmt.Fprintf(os.Stderr, "WARNING: failed to pull %s: %v\n", id, err)
		}
	}

	// Load the launch model (marked _launch:true in catalog), fall back to settings default
	launchModel := ""
	for id, spec := range cat {
		if spec.Launch {
			launchModel = id
			break
		}
	}
	if launchModel == "" {
		launchModel = ollama.ReadDefaultModel(settingsPath())
	}
	if launchModel == "" {
		launchModel = "qwen3:4b"
	}

	fmt.Printf("\nLoading %s into memory...\n", launchModel)
	if err := ollama.LoadModel(launchModel, "30m"); err != nil {
		return fmt.Errorf("load model: %w", err)
	}
	fmt.Printf("Done. %s is resident.\n", launchModel)
	return nil
}
