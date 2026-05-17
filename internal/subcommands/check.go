package subcommands

import (
	"fmt"
	"os/exec"

	"github.com/jacobandresen/mu/internal/ui"
	"github.com/spf13/cobra"
)

type dep struct {
	label string
	cmd   string
	hint  string
}

var deps = []struct {
	section string
	items   []dep
}{
	{"Core", []dep{
		{"neovim", "nvim", "mu setup"},
		{"git", "git", "mu setup"},
		{"make", "make", "mu setup"},
		{"gcc", "gcc", "mu setup"},
	}},
	{"Language runtimes", []dep{
		{"node", "node", "mu setup"},
		{"npm", "npm", "mu setup (included with node)"},
		{"python3", "python3", "mu setup"},
	}},
	{"Tools", []dep{
		{"fzf", "fzf", "mu setup"},
		{"ripgrep (rg)", "rg", "mu setup  [telescope live_grep]"},
		{"fd", "fd", "mu setup  [telescope find_files]"},
		{"jq", "jq", "mu setup  [JSON formatting]"},
		{"fpc", "fpc", "mu setup  [Free Pascal]"},
	}},
	{"Libraries", []dep{
		{"SDL2", "sdl2-config", "mu setup  [SDL2 graphics/input]"},
	}},
	{"Static analysis", []dep{
		{"clang-tidy", "clang-tidy", "mu setup  [C/C++ linter]"},
		{"ruff", "ruff", "mu setup  [Python linter]"},
		{"tsc (TypeScript)", "tsc", "mu setup  [TypeScript linter]"},
		{"cargo clippy (Rust)", "cargo", "rustup toolchain install stable"},
	}},
	{"AI backend", []dep{
		{"pi", "pi", "npm install -g @earendil-works/pi-coding-agent"},
		{"ollama", "ollama", "mu setup  [local model server]"},
	}},
}

func NewCheckCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "check",
		Short: "Verify all required dependencies are installed",
		Long: `Verifies all required tools are on PATH. Prints [OK] or [!!] per dependency
with install hints. Exits non-zero if anything is missing.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			pass, fail := 0, 0
			for _, section := range deps {
				fmt.Println(ui.Bold(section.section))
				for _, d := range section.items {
					_, err := exec.LookPath(d.cmd)
					if err == nil {
						fmt.Printf("  %s  %s\n", ui.Green("[OK]"), d.label)
						pass++
					} else {
						fmt.Printf("  %s  %-24s %s\n", ui.Red("[!!]"), d.label, ui.Dim(d.hint))
						fail++
					}
				}
				fmt.Println()
			}
			if fail == 0 {
				fmt.Printf("%s\n", ui.Green(fmt.Sprintf("All %d dependencies present.", pass)))
				return nil
			}
			fmt.Printf("%s\n", ui.Yellow(fmt.Sprintf("%d missing, %d present.", fail, pass)))
			fmt.Println(ui.Dim("Run: mu setup"))
			fmt.Println(ui.Dim("For pi: npm install -g @earendil-works/pi-coding-agent"))
			return fmt.Errorf("%d missing", fail)
		},
	}
}
