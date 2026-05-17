//go:build unix

package subcommands

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"

	"github.com/jacobandresen/mu/internal/ui"
	"github.com/spf13/cobra"
)

// ── categories ────────────────────────────────────────────────────────────────

var extToCategory = map[string]string{}

func init() {
	def := func(cat string, exts ...string) {
		for _, e := range exts {
			extToCategory["."+e] = cat
		}
	}
	def("Video", "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "ts", "vob")
	def("Audio", "mp3", "flac", "wav", "aac", "ogg", "m4a", "wma", "opus")
	def("Image", "jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp", "heic", "raw", "cr2", "nef")
	def("Archive", "zip", "tar", "gz", "bz2", "xz", "7z", "rar", "zst", "tgz", "tbz2", "tbz")
	def("Disk Image", "iso", "img", "vmdk", "vdi", "qcow2", "dmg")
	def("Document", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods")
	def("Code", "py", "js", "ts", "go", "rs", "c", "cpp", "h", "java", "rb", "sh")
	def("Database", "db", "sqlite", "sqlite3", "sql")
	def("Package", "deb", "rpm", "pkg", "apk", "msi", "exe")
	def("Log", "log")
	def("Cache", "cache")
	def("Backup", "bak", "old", "orig", "backup")
	def("Library", "so", "dylib", "dll", "a")
}

var deletablePaths = []string{
	"/.cache/", "/tmp/", "/var/tmp/", "/var/cache/", "/.local/share/Trash/",
	"/__pycache__/", "/node_modules/", "/.npm/_cacache/", "/.cargo/registry/cache/",
	"/go/pkg/mod/cache/", "/.gradle/caches/", "/.m2/repository/",
	"/.thumbnails/", "/thumbnails/",
}

var deletableExts = map[string]bool{
	".log": true, ".bak": true, ".old": true, ".orig": true,
	".backup": true, ".cache": true, ".pyc": true, ".pyo": true,
}

var deletableNames = map[string]bool{
	"core": true, "core.gz": true, ".DS_Store": true,
	"Thumbs.db": true, "desktop.ini": true,
	"npm-debug.log": true, "yarn-error.log": true,
}

func categorize(path, ext string) string {
	p := strings.ToLower(path)
	if strings.Contains(p, "/node_modules/") {
		return "Package"
	}
	if strings.Contains(p, "/__pycache__/") || ext == ".pyc" {
		return "Cache"
	}
	if strings.Contains(p, "/.cache/") || strings.Contains(p, "/cache/") {
		return "Cache"
	}
	if strings.Contains(p, "/log/") || strings.Contains(p, "/logs/") {
		return "Log"
	}
	if cat, ok := extToCategory[strings.ToLower(ext)]; ok {
		return cat
	}
	return "Other"
}

func isDeletable(path, ext, name string) (bool, string) {
	p := strings.ToLower(path)
	for _, pat := range deletablePaths {
		if strings.Contains(p, pat) {
			return true, "in " + strings.Trim(pat, "/")
		}
	}
	if deletableExts[strings.ToLower(ext)] {
		return true, ext + " file"
	}
	if deletableNames[strings.ToLower(name)] {
		return true, "temp/junk file"
	}
	return false, ""
}

func humanSize(n int64) string {
	f := float64(n)
	for _, u := range []string{"B", "KB", "MB", "GB", "TB"} {
		if f < 1024 {
			return fmt.Sprintf("%.1f %s", f, u)
		}
		f /= 1024
	}
	return fmt.Sprintf("%.1f PB", f)
}

func shellQuote(s string) string {
	return "'" + strings.ReplaceAll(s, "'", "'\\''") + "'"
}

func termWidth() int {
	out, err := exec.Command("tput", "cols").Output()
	if err == nil {
		if w, err := strconv.Atoi(strings.TrimSpace(string(out))); err == nil && w > 0 {
			if w > 160 {
				return 160
			}
			return w
		}
	}
	return 120
}

// ── file entry ────────────────────────────────────────────────────────────────

type fileEntry struct {
	path      string
	size      int64
	category  string
	deletable bool
	reason    string
}

// ── scan ─────────────────────────────────────────────────────────────────────

func scanFiles(roots []string, skipMounts bool, minSize int64) []fileEntry {
	seen := make(map[string]bool)
	var entries []fileEntry

	for _, root := range roots {
		var rootDev uint64
		rootDevKnown := false
		if skipMounts {
			if fi, err := os.Stat(root); err == nil {
				if stat, ok := fi.Sys().(*syscall.Stat_t); ok {
					rootDev = uint64(stat.Dev)
					rootDevKnown = true
				}
			}
		}

		filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error { //nolint:errcheck
			if err != nil {
				return nil
			}

			info, err := d.Info()
			if err != nil {
				return nil
			}

			if d.IsDir() {
				if skipMounts && rootDevKnown && path != root {
					if stat, ok := info.Sys().(*syscall.Stat_t); ok {
						if uint64(stat.Dev) != rootDev {
							return filepath.SkipDir
						}
					}
				}
				return nil
			}

			if info.Size() < minSize {
				return nil
			}

			stat, ok := info.Sys().(*syscall.Stat_t)
			if !ok {
				return nil
			}

			key := fmt.Sprintf("%d:%d", stat.Dev, stat.Ino)
			if seen[key] {
				return nil
			}
			seen[key] = true

			name := filepath.Base(path)
			ext := filepath.Ext(name)
			cat := categorize(path, ext)
			del, reason := isDeletable(path, ext, name)

			entries = append(entries, fileEntry{
				path:      path,
				size:      info.Size(),
				category:  cat,
				deletable: del,
				reason:    reason,
			})
			return nil
		})
	}

	sort.Slice(entries, func(i, j int) bool {
		return entries[i].size > entries[j].size
	})
	return entries
}

// ── output ────────────────────────────────────────────────────────────────────

const (
	colNum    = 4
	colSize   = 10
	colCat    = 12
	colReason = 22
	// display columns consumed by everything except the path field
	tableOverhead = 2 + colNum + 3 + colSize + 3 + colCat + 3 + colReason + 3 + 2
)

func hline(pathW int, left, junc, right string) string {
	segs := []string{
		strings.Repeat("─", colNum+2),
		strings.Repeat("─", colSize+2),
		strings.Repeat("─", colCat+2),
		strings.Repeat("─", colReason+2),
		strings.Repeat("─", pathW+2),
	}
	return left + strings.Join(segs, junc) + right
}

func makeRow(pathW int, num, size, cat, reason, path string) string {
	return fmt.Sprintf("│ %4s │ %10s │ %-12s │ %-22s │ %-*s │",
		num, size, cat, reason, pathW, path)
}

func truncatePath(s string, maxW int) string {
	if len(s) <= maxW {
		return s
	}
	keep := maxW - 1
	if keep < 0 {
		keep = 0
	}
	start := len(s) - keep
	if start < 0 {
		start = 0
	}
	return "…" + s[start:]
}

func printTable(entries []fileEntry, topN int) ([]fileEntry, int) {
	var deletable []fileEntry
	for _, e := range entries {
		if e.deletable {
			deletable = append(deletable, e)
		}
	}
	n := topN
	if len(deletable) < n {
		n = len(deletable)
	}
	if n == 0 {
		fmt.Println("\nNo files suggested for deletion.")
		return deletable, 0
	}

	w := termWidth()
	pathW := w - tableOverhead
	if pathW < 10 {
		pathW = 10
	}

	fmt.Printf("\n%s\n", ui.Bold(ui.Cyan(fmt.Sprintf("Deletion Candidates — Top %d by Size", n))))
	fmt.Println(ui.Dim(hline(pathW, "╭", "┬", "╮")))
	fmt.Println(ui.Bold(makeRow(pathW, "#", "Size", "Category", "Reason", "Path")))
	fmt.Println(ui.Dim(hline(pathW, "├", "┼", "┤")))

	var total int64
	for i := 0; i < n; i++ {
		e := deletable[i]
		row := makeRow(pathW, strconv.Itoa(i+1), humanSize(e.size), e.category, e.reason, truncatePath(e.path, pathW))
		fmt.Println(ui.Red(row))
		total += e.size
	}

	fmt.Println(ui.Dim(hline(pathW, "╰", "┴", "╯")))
	fmt.Printf("  %s %s (%d files)\n", ui.Bold("Total reclaimable:"), ui.Red(humanSize(total)), n)

	return deletable, n
}

func printCommands(deletable []fileEntry, n int) {
	if n == 0 {
		return
	}
	fmt.Printf("\n%s\n", ui.Bold(ui.Cyan("Suggested cleanup commands:")))
	for i := 0; i < n; i++ {
		fmt.Println("  rm -f " + shellQuote(deletable[i].path))
	}
	fmt.Println(ui.Dim("\n  # or delete all at once:"))
	paths := make([]string, n)
	for i := 0; i < n; i++ {
		paths[i] = shellQuote(deletable[i].path)
	}
	fmt.Println("  rm -f " + strings.Join(paths, " \\\n       "))
}

// ── command ───────────────────────────────────────────────────────────────────

func NewCleanCmd() *cobra.Command {
	var top int
	var minSizeBytes int64
	var noSkipMounts bool
	var yolo bool

	cmd := &cobra.Command{
		Use:   "clean [roots...]",
		Short: "Report or remove large files in the current tree",
		Long: `Scans the filesystem for large files and suggests deletion candidates.

Uses NO_COLOR=1 to suppress color output when needed.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			roots := args
			if len(roots) == 0 {
				roots = []string{"/"}
			}

			fmt.Fprintf(os.Stderr, "Scanning %s (min size: %s) ...\n",
				strings.Join(roots, ", "), humanSize(minSizeBytes))

			entries := scanFiles(roots, !noSkipMounts, minSizeBytes)

			fmt.Fprintf(os.Stderr, "Found %d files above threshold.\n", len(entries))

			if len(entries) == 0 {
				fmt.Println("No files found.")
				return nil
			}

			deletable, shown := printTable(entries, top)

			if yolo && shown > 0 {
				fmt.Fprintf(os.Stderr, "\n%s\n",
					ui.Bold(ui.Red(fmt.Sprintf("WARNING: --yolo active. Deleting %d files now...", shown))))
				for i := 0; i < shown; i++ {
					if err := os.Remove(deletable[i].path); err != nil {
						fmt.Fprintf(os.Stderr, "error removing %s: %v\n", deletable[i].path, err)
					}
				}
				fmt.Fprintln(os.Stderr, "Done.")
			} else {
				printCommands(deletable, shown)
			}
			return nil
		},
	}

	cmd.Flags().IntVarP(&top, "top", "n", 10, "number of files to show")
	cmd.Flags().Int64Var(&minSizeBytes, "min-size", 1024*1024, "minimum file size in bytes")
	cmd.Flags().BoolVar(&noSkipMounts, "no-skip-mounts", false, "cross filesystem boundaries")
	cmd.Flags().BoolVar(&yolo, "yolo", false, "WARNING: immediately deletes all candidate files with no confirmation")

	return cmd
}
