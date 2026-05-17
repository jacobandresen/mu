package subcommands

import (
	"fmt"

	"github.com/jacobandresen/mu/internal/version"
	"github.com/spf13/cobra"
)

func NewVersionCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "version",
		Short: "Print mu version",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			fmt.Println("mu v" + version.Version)
			return nil
		},
	}
}
