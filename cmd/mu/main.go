package main

import (
	"os"

	"github.com/jacobandresen/mu/internal/subcommands"
	"github.com/spf13/cobra"
)

func main() {
	root := &cobra.Command{
		Use:           "mu",
		Short:         "Local AI coding toolkit",
		Long:          "mu — local AI coding toolkit\n\nRequires: nvim, pi (npm install -g @earendil-works/pi-coding-agent)\n\nUse \"mu <command> --help\" for command-specific flags.\n\nJacob Andresen: jacob.andresen@gmail.com",
		SilenceUsage:  true,
		SilenceErrors: true,
	}

	root.AddCommand(
		subcommands.NewCheckCmd(),
		subcommands.NewCleanCmd(),
		subcommands.NewRunCmd(),
		subcommands.NewSetupCmd(),
		subcommands.NewThemeCmd(),
		subcommands.NewModelCmd(),
		subcommands.NewOptimizeCmd(),
		subcommands.NewExtractCmd(),
		subcommands.NewPrimeCmd(),
		subcommands.NewAgentCmd(),
		subcommands.NewVersionCmd(),
	)

	if err := root.Execute(); err != nil {
		os.Exit(1)
	}
}
