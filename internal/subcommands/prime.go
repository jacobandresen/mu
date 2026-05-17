package subcommands

import (
	"fmt"

	"github.com/jacobandresen/mu/internal/ollama"
	"github.com/spf13/cobra"
)

func NewPrimeCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "prime",
		Short: "Load the currently selected model into memory",
		Long:  `Loads the currently selected model into ollama memory. Safe to re-run.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			return runPrime()
		},
	}
}

func runPrime() error {
	model := ollama.ReadDefaultModel(settingsPath())
	if model == "" {
		model = "qwen3:4b"
	}

	fmt.Printf("Loading %s into memory...\n", model)
	if err := ollama.LoadModel(model, "30m"); err != nil {
		return fmt.Errorf("load model: %w", err)
	}
	fmt.Printf("Done. %s is resident.\n", model)
	return nil
}
