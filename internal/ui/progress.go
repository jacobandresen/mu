package ui

import (
	"fmt"
	"strings"
)

func DrawProgressBar(elapsed, timeout, width int) string {
	if timeout <= 0 || width <= 0 {
		return ""
	}
	filled := elapsed * width / timeout
	if filled > width {
		filled = width
	}
	bar := strings.Repeat("█", filled) + strings.Repeat("░", width-filled)
	pct := elapsed * 100 / timeout
	if pct > 100 {
		pct = 100
	}
	return fmt.Sprintf("[%s] %3d%%  %ds/%ds", bar, pct, elapsed, timeout)
}
