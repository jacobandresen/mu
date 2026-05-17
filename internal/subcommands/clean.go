package subcommands

import (
	_ "embed"
	"fmt"
	"os"
	"os/exec"

	"github.com/spf13/cobra"
)

//go:embed large_files.lua
var largFilesLua []byte

func NewCleanCmd() *cobra.Command {
	return &cobra.Command{
		Use:                "clean",
		Short:              "Report or remove large files in the current tree",
		Long:               "Scans for large files and suggests cleanup candidates.",
		DisableFlagParsing: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			tmp, err := os.CreateTemp("", "large_files_*.lua")
			if err != nil {
				return fmt.Errorf("create temp script: %w", err)
			}
			defer os.Remove(tmp.Name())
			if _, err := tmp.Write(largFilesLua); err != nil {
				tmp.Close()
				return fmt.Errorf("write temp script: %w", err)
			}
			tmp.Close()
			c := exec.Command("lua", append([]string{tmp.Name()}, args...)...)
			c.Stdin, c.Stdout, c.Stderr = os.Stdin, os.Stdout, os.Stderr
			return c.Run()
		},
	}
}
