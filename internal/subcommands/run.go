package subcommands

import (
	"fmt"
	"os"
	"os/exec"
	"syscall"

	"github.com/jacobandresen/mu/internal/ollama"
	"github.com/spf13/cobra"
)

func NewRunCmd() *cobra.Command {
	return &cobra.Command{
		Use:                "run",
		Short:              "Launch pi in offline mode (checks ollama is running first)",
		Long:               "Thin wrapper around pi. Verifies ollama is running, sets PI_OFFLINE=1 and OLLAMA_KEEP_ALIVE=30m, then execs pi with all provided arguments.",
		DisableFlagParsing: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			if !ollama.IsRunning() {
				return fmt.Errorf("ollama is not running — start it with: ollama serve")
			}
			piPath, err := exec.LookPath("pi")
			if err != nil {
				return fmt.Errorf("pi not found on PATH — run: npm install -g @earendil-works/pi-coding-agent")
			}
			os.Setenv("PI_OFFLINE", "1")
			os.Setenv("OLLAMA_KEEP_ALIVE", "30m")
			return syscall.Exec(piPath, append([]string{"pi"}, args...), os.Environ())
		},
	}
}
