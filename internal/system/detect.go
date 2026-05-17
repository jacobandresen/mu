package system

import (
	"os"
	"regexp"
	"runtime"
	"strconv"
	"strings"
)

type SystemInfo struct {
	CPUModel       string
	PhysicalCores  int
	LogicalThreads int
	RAMMB          int
	GPUVendor      string // "nvidia"|"amd"|"intel-arc"|"apple"|"none"
	GPUName        string
	Governors      []string
}

func sysctl(key string) string {
	out, err := runOutput("sysctl", "-n", key)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(out)
}

func Detect() (SystemInfo, error) {
	if runtime.GOOS == "darwin" {
		return detectDarwin()
	}
	return detectLinux()
}

func detectDarwin() (SystemInfo, error) {
	cpu := sysctl("machdep.cpu.brand_string")
	if cpu == "" {
		cpu = "Apple " + runtime.GOARCH
	}
	phys := atoi(sysctl("hw.physicalcpu"), 1)
	logi := atoi(sysctl("hw.logicalcpu"), phys)
	memB := atoi64(sysctl("hw.memsize"), 0)
	ramMB := int(memB / (1024 * 1024))

	var gpuVendor, gpuName string
	if runtime.GOARCH == "arm64" {
		gpuVendor, gpuName = "apple", "Apple Silicon (Metal)"
	} else {
		gpuVendor, gpuName = "none", ""
		sp, _ := runOutput("system_profiler", "SPDisplaysDataType")
		spL := strings.ToLower(sp)
		chipRE := regexp.MustCompile(`chipset model:\s*(.+)`)
		switch {
		case strings.Contains(spL, "amd") || strings.Contains(spL, "radeon"):
			gpuVendor = "amd"
			if m := chipRE.FindStringSubmatch(spL); m != nil {
				gpuName = strings.TrimSpace(m[1])
			} else {
				gpuName = "AMD GPU"
			}
		case strings.Contains(spL, "nvidia"):
			gpuVendor = "nvidia"
			if m := chipRE.FindStringSubmatch(spL); m != nil {
				gpuName = strings.TrimSpace(m[1])
			} else {
				gpuName = "NVIDIA GPU"
			}
		}
	}
	return SystemInfo{
		CPUModel:       cpu,
		PhysicalCores:  phys,
		LogicalThreads: logi,
		RAMMB:          ramMB,
		GPUVendor:      gpuVendor,
		GPUName:        gpuName,
	}, nil
}

func detectLinux() (SystemInfo, error) {
	lscpu, _ := runOutputEnv([]string{"LC_ALL=C"}, "lscpu")
	cpu := lscpuField(lscpu, "Model name")
	cps := atoi(lscpuField(lscpu, "Core(s) per socket"), 1)
	skt := atoi(lscpuField(lscpu, "Socket(s)"), 1)
	phys := cps * skt
	logi := atoi(lscpuField(lscpu, "CPU(s)"), phys)

	ramMB := 0
	if data, err := os.ReadFile("/proc/meminfo"); err == nil {
		if m := regexp.MustCompile(`MemTotal:\s+(\d+)\s+kB`).FindSubmatch(data); m != nil {
			ramMB = atoi(string(m[1]), 0) / 1024
		}
	}

	gpuVendor, gpuName := "none", ""
	if smi, err := runOutput("nvidia-smi", "--query-gpu=name", "--format=csv,noheader"); err == nil {
		lines := strings.Split(strings.TrimSpace(smi), "\n")
		if len(lines) > 0 && lines[0] != "" {
			gpuVendor = "nvidia"
			gpuName = lines[0]
		}
	}
	if gpuVendor == "none" {
		lspci, _ := runOutput("lspci")
		lspciL := strings.ToLower(lspci)
		vgaRE := regexp.MustCompile(`vga.*?:\s*(.+)`)
		switch {
		case strings.Contains(lspciL, "amd") && (strings.Contains(lspciL, "radeon") || strings.Contains(lspciL, "navi") || strings.Contains(lspciL, "vega")):
			gpuVendor = "amd"
			if m := vgaRE.FindStringSubmatch(lspciL); m != nil {
				gpuName = strings.TrimSpace(m[1])
			} else {
				gpuName = "AMD GPU"
			}
		case strings.Contains(lspciL, "intel") && strings.Contains(lspciL, "arc"):
			gpuVendor = "intel-arc"
			gpuName = "Intel Arc"
		}
	}

	var governors []string
	if data, err := os.ReadFile("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"); err == nil {
		governors = strings.Fields(string(data))
	}

	return SystemInfo{
		CPUModel:       cpu,
		PhysicalCores:  phys,
		LogicalThreads: logi,
		RAMMB:          ramMB,
		GPUVendor:      gpuVendor,
		GPUName:        gpuName,
		Governors:      governors,
	}, nil
}

func MemoryTier(ramMB int) string {
	if ramMB <= 8*1024 {
		return "low"
	}
	if ramMB <= 16*1024 {
		return "mid"
	}
	return "high"
}

func ComputeOllamaSettings(info SystemInfo) map[string]string {
	tier := MemoryTier(info.RAMMB)
	cores := info.PhysicalCores
	if cores < 1 {
		cores = 1
	}
	parallel := "2"
	if tier == "low" {
		parallel = "1"
	}
	context := map[string]string{"low": "2048", "mid": "4096", "high": "4096"}[tier]
	keepAlive := "-1"
	if tier == "low" {
		keepAlive = "300"
	}
	return map[string]string{
		"OLLAMA_NUM_THREADS":      strconv.Itoa(cores),
		"OLLAMA_NUM_PARALLEL":     parallel,
		"OLLAMA_MAX_QUEUE":        "512",
		"OLLAMA_MAX_LOADED_MODELS": "1",
		"OLLAMA_SCHED_SPREAD":     "1",
		"OLLAMA_FLASH_ATTENTION":  "1",
		"OLLAMA_KV_CACHE_TYPE":    "q8_0",
		"OLLAMA_CONTEXT_LENGTH":   context,
		"OLLAMA_KEEP_ALIVE":       keepAlive,
	}
}

func lscpuField(output, key string) string {
	for _, line := range strings.Split(output, "\n") {
		parts := strings.SplitN(line, ":", 2)
		if len(parts) == 2 && strings.TrimSpace(parts[0]) == key {
			return strings.TrimSpace(parts[1])
		}
	}
	return ""
}

func atoi(s string, def int) int {
	n, err := strconv.Atoi(strings.TrimSpace(s))
	if err != nil {
		return def
	}
	return n
}

func atoi64(s string, def int64) int64 {
	n, err := strconv.ParseInt(strings.TrimSpace(s), 10, 64)
	if err != nil {
		return def
	}
	return n
}
