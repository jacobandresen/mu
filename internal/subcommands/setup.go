package subcommands

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"

	"github.com/spf13/cobra"
)

func NewSetupCmd() *cobra.Command {
	var yes bool
	cmd := &cobra.Command{
		Use:   "setup",
		Short: "Install system dependencies for this toolchain",
		Long: `Installs system packages (brew / pacman / apt) and the pi npm package.
Detects macOS, Arch, and Debian/Ubuntu automatically.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSetup(yes)
		},
	}
	cmd.Flags().BoolVarP(&yes, "yes", "y", false, "Skip confirmation prompts")
	return cmd
}

func confirm(prompt string, yes bool) bool {
	if yes {
		return true
	}
	fmt.Printf("%s [y/N] ", prompt)
	r := bufio.NewReader(os.Stdin)
	line, _ := r.ReadString('\n')
	return strings.TrimSpace(strings.ToLower(line)) == "y"
}

func runCmd(yes bool, name string, args ...string) error {
	fmt.Printf("  $ %s %s\n", name, strings.Join(args, " "))
	if !confirm("Proceed?", yes) {
		return fmt.Errorf("aborted")
	}
	c := exec.Command(name, args...)
	c.Stdin, c.Stdout, c.Stderr = os.Stdin, os.Stdout, os.Stderr
	return c.Run()
}

func runSetup(yes bool) error {
	switch runtime.GOOS {
	case "darwin":
		pkgs := []string{
			"neovim", "make", "gcc", "llvm", "node", "python", "jq", "git",
			"fpc", "fzf", "ripgrep", "fd", "ollama", "SDL2", "ruff",
		}
		if err := runCmd(yes, "brew", append([]string{"install"}, pkgs...)...); err != nil {
			return err
		}
		// symlink clang-tidy
		c := exec.Command("brew", "--prefix", "llvm")
		out, err := c.Output()
		if err == nil {
			llvmBin := strings.TrimSpace(string(out)) + "/bin/clang-tidy"
			brewBin, _ := exec.Command("brew", "--prefix").Output()
			dest := strings.TrimSpace(string(brewBin)) + "/bin/clang-tidy"
			if _, e := os.Stat(dest); os.IsNotExist(e) {
				if _, e2 := os.Stat(llvmBin); e2 == nil {
					os.Symlink(llvmBin, dest)
				}
			}
		}
		_ = runCmd(yes, "brew", "install", "--cask", "font-terminess-ttf-nerd-font")

	case "linux":
		if _, err := os.Stat("/etc/arch-release"); err == nil {
			pkgs := []string{
				"--needed", "neovim", "ttf-terminus-nerd", "base-devel", "make", "gcc",
				"clang", "nodejs", "npm", "python", "jq", "git", "fpc", "fzf",
				"wl-clipboard", "ripgrep", "fd", "ollama", "unzip", "ruff",
			}
			if err := runCmd(yes, "sudo", append([]string{"pacman", "-S"}, pkgs...)...); err != nil {
				return err
			}
		} else if _, err := os.Stat("/etc/debian_version"); err == nil {
			if err := runCmd(yes, "sudo", "apt-get", "update"); err != nil {
				return err
			}
			if err := runCmd(yes, "sudo", "apt-get", "install", "-y", "software-properties-common"); err != nil {
				return err
			}
			if err := runCmd(yes, "sudo", "add-apt-repository", "-y", "ppa:neovim-ppa/stable"); err != nil {
				return err
			}
			if err := runCmd(yes, "sudo", "apt-get", "update"); err != nil {
				return err
			}
			pkgs := []string{
				"-y", "neovim", "build-essential", "make", "gcc", "clang", "clang-tidy",
				"nodejs", "npm", "python3", "python3-pip", "jq", "git", "fpc", "fzf",
				"ripgrep", "fd-find", "unzip",
			}
			if err := runCmd(yes, "sudo", append([]string{"apt-get", "install"}, pkgs...)...); err != nil {
				return err
			}
			if err := runCmd(yes, "pip3", "install", "--user", "ruff"); err != nil {
				fmt.Println("Warning: ruff install failed — Python linting unavailable")
			}
			// fd-find → fd symlink
			if fdf, err := exec.LookPath("fdfind"); err == nil {
				if _, e := os.Stat("/usr/local/bin/fd"); os.IsNotExist(e) {
					runCmd(yes, "sudo", "ln", "-sf", fdf, "/usr/local/bin/fd")
				}
			}
			fmt.Println("Downloading ollama installer...")
			runCmd(yes, "sh", "-c", "curl -fL# https://ollama.com/install.sh | sh")
			fmt.Println("Note: install Terminess Nerd Font manually from https://www.nerdfonts.com/font-downloads")
		} else {
			return fmt.Errorf("unsupported Linux distribution")
		}
	default:
		return fmt.Errorf("unsupported OS: %s", runtime.GOOS)
	}

	fmt.Println("\nInstalling npm globals (pi, typescript)...")
	if err := runCmd(yes, "npm", "install", "-g", "@earendil-works/pi-coding-agent", "typescript"); err != nil {
		return err
	}
	return nil
}
