package subcommands

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/spf13/cobra"
)

var (
	fenceRE = regexp.MustCompile(`^` + "```" + `([A-Za-z0-9_+-]*)\s*$`)
	pathCommentRE = regexp.MustCompile(
		`^\s*(?:` +
			`//\s*(\S+)` +
			`|#\s*(\S+)` +
			`|<!--\s*(\S+)\s*-->` +
			`|/\*\s*(\S+)\s*\*/` +
			`)\s*$`,
	)
)

type codeBlock struct {
	lang string
	body []string
}

func parseBlocks(text string) []codeBlock {
	lines := strings.Split(text, "\n")
	var blocks []codeBlock
	i := 0
	for i < len(lines) {
		m := fenceRE.FindStringSubmatch(lines[i])
		if m == nil {
			i++
			continue
		}
		lang := strings.ToLower(m[1])
		i++
		var body []string
		for i < len(lines) && fenceRE.FindStringSubmatch(lines[i]) == nil {
			body = append(body, lines[i])
			i++
		}
		if i < len(lines) {
			i++ // consume closing fence
		}
		blocks = append(blocks, codeBlock{lang: lang, body: body})
	}
	return blocks
}

func extractPath(body []string) string {
	if len(body) == 0 {
		return ""
	}
	m := pathCommentRE.FindStringSubmatch(body[0])
	if m == nil {
		return ""
	}
	p := ""
	for _, g := range m[1:] {
		if g != "" {
			p = g
			break
		}
	}
	if p == "" || strings.HasPrefix(p, "/") {
		return ""
	}
	for _, part := range strings.Split(p, "/") {
		if part == ".." {
			return ""
		}
	}
	if !strings.Contains(p, "/") && !strings.Contains(p, ".") {
		return ""
	}
	return p
}

func NewExtractCmd() *cobra.Command {
	var root string
	var run, yes, force bool
	cmd := &cobra.Command{
		Use:   "extract <log>",
		Short: "Salvage files from an agent iteration log",
		Long: `Parse fenced code blocks in a log file and write them as files.
Blocks with a path comment as their first line are written to disk.
Bash/sh blocks are printed; with --run they are executed.`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return runExtract(args[0], root, run, yes, force)
		},
	}
	cmd.Flags().StringVar(&root, "root", "", "Directory to write files under (default: current dir)")
	cmd.Flags().BoolVar(&run, "run", false, "Execute bash/sh blocks")
	cmd.Flags().BoolVar(&yes, "yes", false, "Skip confirmation prompts when --run is set")
	cmd.Flags().BoolVar(&force, "force", false, "Overwrite existing files")
	return cmd
}

func runExtract(logPath, root string, run, yes, force bool) error {
	if root == "" {
		root = "."
	}
	data, err := os.ReadFile(logPath)
	if err != nil {
		return fmt.Errorf("read log: %w", err)
	}
	blocks := parseBlocks(string(data))

	var files [][2]string // [path, content]
	var scripts []string

	for _, b := range blocks {
		if p := extractPath(b.body); p != "" {
			content := strings.Join(b.body[1:], "\n") + "\n"
			files = append(files, [2]string{p, content})
		} else if b.lang == "bash" || b.lang == "sh" || b.lang == "shell" {
			scripts = append(scripts, strings.Join(b.body, "\n"))
		}
	}

	fmt.Printf("[extract] %d file block(s), %d shell block(s)\n", len(files), len(scripts))

	for _, f := range files {
		dest := filepath.Join(root, f[0])
		if _, err := os.Stat(dest); err == nil && !force {
			fmt.Printf("  skip  %s (exists; use --force)\n", f[0])
			continue
		}
		if err := os.MkdirAll(filepath.Dir(dest), 0755); err != nil {
			return err
		}
		if err := os.WriteFile(dest, []byte(f[1]), 0644); err != nil {
			return err
		}
		fmt.Printf("  wrote %s (%d bytes)\n", f[0], len(f[1]))
	}

	for i, script := range scripts {
		fmt.Printf("\n--- shell block %d ---\n%s\n--- end ---\n", i+1, script)
		if !run {
			continue
		}
		if !yes {
			fmt.Printf("run shell block %d? [y/N] ", i+1)
			var ans string
			fmt.Scanln(&ans)
			if strings.ToLower(strings.TrimSpace(ans)) != "y" {
				fmt.Println("  skipped")
				continue
			}
		}
		c := runShell(script, root)
		fmt.Printf("  exit=%d\n", c)
	}
	return nil
}

func runShell(script, dir string) int {
	c := exec.Command("sh", "-c", script)
	c.Dir = dir
	c.Stdin, c.Stdout, c.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := c.Run(); err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			return ee.ExitCode()
		}
		return 1
	}
	return 0
}
