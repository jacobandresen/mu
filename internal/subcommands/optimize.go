package subcommands

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/jacobandresen/mu/internal/system"
	"github.com/spf13/cobra"
	"howett.net/plist"
)

func NewOptimizeCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "optimize",
		Short: "Tune ollama for the agent's sequential workload",
		Long: `Detects CPU/RAM/GPU, computes ollama settings for the agent's sequential
workload, and writes them to the system service config (launchd on macOS,
systemd on Linux). Restarts ollama. No flags.`,
		RunE: func(cmd *cobra.Command, args []string) error {
			return runOptimize()
		},
	}
}

func runOptimize() error {
	fmt.Println("Detecting system...")
	info, err := system.Detect()
	if err != nil {
		return fmt.Errorf("detect system: %w", err)
	}

	gpuLabel := "none detected"
	if info.GPUVendor != "none" {
		gpuLabel = info.GPUName + " (" + info.GPUVendor + ")"
	}
	fmt.Printf("  CPU   : %s\n", info.CPUModel)
	fmt.Printf("  Cores : %d physical / %d logical\n", info.PhysicalCores, info.LogicalThreads)
	fmt.Printf("  RAM   : %d MB (%d GB)\n", info.RAMMB, info.RAMMB/1024)
	fmt.Printf("  GPU   : %s\n", gpuLabel)
	if runtime.GOOS != "darwin" {
		fmt.Printf("  CPU governors: %s\n", strings.Join(info.Governors, ", "))
	}
	fmt.Println()

	settings := system.ComputeOllamaSettings(info)
	fmt.Println("Computed ollama settings:")
	for k, v := range settings {
		fmt.Printf("  %s=%s\n", k, v)
	}
	fmt.Println()

	if system.MemoryTier(info.RAMMB) == "low" {
		fmt.Println("Memory-pressure advice (<=8 GB host):")
		fmt.Println("  * OLLAMA_CONTEXT_LENGTH=4096 set — on 8 GB M2, num_ctx drives KV-cache size and speed:")
		fmt.Println("    16384 → 63 MB free, 3 tok/s, 500 errors; 8192 → 8 tok/s (writer timeouts on long files);")
		fmt.Println("    4096 → 14 tok/s, fits all mu per-session windows (sessions are independent).")
		fmt.Println("  * KV cache: q8_0 + flash attention already halve memory vs fp16 baseline")
		fmt.Println("  * OLLAMA_NUM_PARALLEL=1 set — prevents multiple concurrent KV-cache slots")
		fmt.Println("  * OLLAMA_KEEP_ALIVE=300 set — model stays warm for 5 min between requests")
		fmt.Println("  * Prefer smaller quants — Q3_K_M or Q2_K save ~1 GB vs Q4_K_M")
		fmt.Println("  * qwen3:4b uses ~2.5 GB, leaving ~5.5 GB for OS/apps if RAM is critical")
		fmt.Println()
	}

	if runtime.GOOS == "darwin" {
		if err := writeLaunchdEnv(settings); err != nil {
			return err
		}
		// Use launchctl unload/load instead of 'brew services restart': brew regenerates
		// the plist from its formula template on restart, wiping any env-var additions.
		fmt.Println("Restarting ollama via launchctl...")
		home, _ := os.UserHomeDir()
		plistPath := filepath.Join(home, "Library", "LaunchAgents", "homebrew.mxcl.ollama.plist")
		unload := exec.Command("launchctl", "unload", plistPath)
		unload.Stdout, unload.Stderr = os.Stdout, os.Stderr
		_ = unload.Run()
		load := exec.Command("launchctl", "load", plistPath)
		load.Stdout, load.Stderr = os.Stdout, os.Stderr
		if err := load.Run(); err != nil {
			return fmt.Errorf("reload ollama: %w", err)
		}
		fmt.Println("ollama restarted")
	} else {
		fmt.Print("sudo password: ")
		r := bufio.NewReader(os.Stdin)
		pass, _ := r.ReadString('\n')
		pass = strings.TrimRight(pass, "\n")

		sudoRun := func(args ...string) error {
			c := exec.Command("sudo", append([]string{"-S"}, args...)...)
			c.Stdin = strings.NewReader(pass + "\n")
			c.Stdout, c.Stderr = os.Stdout, os.Stderr
			return c.Run()
		}
		if err := sudoRun("true"); err != nil {
			return fmt.Errorf("wrong sudo password")
		}

		overrideDir := "/etc/systemd/system/ollama.service.d"
		overridePath := overrideDir + "/override.conf"
		if err := sudoRun("mkdir", "-p", overrideDir); err != nil {
			return err
		}
		var lines []string
		lines = append(lines, "[Service]")
		for k, v := range settings {
			lines = append(lines, fmt.Sprintf(`Environment="%s=%s"`, k, v))
		}
		content := strings.Join(lines, "\n") + "\n"
		tmpFile := "/tmp/mu_ollama_override.conf"
		if err := os.WriteFile(tmpFile, []byte(content), 0644); err != nil {
			return err
		}
		if err := sudoRun("cp", tmpFile, overridePath); err != nil {
			return err
		}
		if err := sudoRun("chmod", "644", overridePath); err != nil {
			return err
		}
		_ = os.Remove(tmpFile)
		fmt.Printf("Written: %s\n", overridePath)

		if contains(info.Governors, "performance") {
			fmt.Println("Setting CPU governor to performance...")
			entries, _ := filepath.Glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor")
			for _, gov := range entries {
				_ = sudoRun("sh", "-c", "echo performance > "+gov)
			}
			fmt.Println("CPU governor: performance")
		} else {
			fmt.Println("CPU governor: performance mode not available, skipping")
		}

		fmt.Println("Reloading systemd daemon...")
		_ = sudoRun("systemctl", "daemon-reload")
		fmt.Println("Restarting ollama...")
		_ = sudoRun("systemctl", "restart", "ollama")
	}

	fmt.Println("\nDone.")
	return nil
}

func writeLaunchdEnv(settings map[string]string) error {
	home, _ := os.UserHomeDir()
	plistPath := filepath.Join(home, "Library", "LaunchAgents", "homebrew.mxcl.ollama.plist")
	if _, err := os.Stat(plistPath); os.IsNotExist(err) {
		return fmt.Errorf("launchd plist not found: %s\nStart ollama first: brew services start ollama", plistPath)
	}

	data, err := os.ReadFile(plistPath)
	if err != nil {
		return fmt.Errorf("read plist: %w", err)
	}

	var pl map[string]any
	if _, err := plist.Unmarshal(data, &pl); err != nil {
		return fmt.Errorf("parse plist: %w", err)
	}

	envVars, _ := pl["EnvironmentVariables"].(map[string]any)
	if envVars == nil {
		envVars = map[string]any{}
	}
	for k, v := range settings {
		envVars[k] = v
	}
	pl["EnvironmentVariables"] = envVars

	out, err := plist.MarshalIndent(pl, plist.XMLFormat, "\t")
	if err != nil {
		return fmt.Errorf("marshal plist: %w", err)
	}
	if err := os.WriteFile(plistPath, out, 0644); err != nil {
		return fmt.Errorf("write plist: %w", err)
	}
	fmt.Printf("Written: %s\n", plistPath)
	return nil
}

func contains(slice []string, s string) bool {
	for _, v := range slice {
		if v == s {
			return true
		}
	}
	return false
}
