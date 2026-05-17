package ui

import (
	"fmt"
	"strings"
)

const bannerInner = 58

func bannerRow(content string) string {
	visible := len(StripANSI(content))
	switch {
	case visible < bannerInner:
		content += strings.Repeat(" ", bannerInner-visible)
	case visible > bannerInner:
		content = truncateVisible(content, bannerInner-1) + "…"
	}
	return Cyan("│") + content + Cyan("│")
}

func truncateVisible(s string, max int) string {
	count := 0
	i := 0
	inEsc := false
	for i < len(s) {
		if s[i] == '\033' {
			inEsc = true
		}
		if inEsc {
			if s[i] == 'm' {
				inEsc = false
			}
			i++
			continue
		}
		if count == max {
			return s[:i]
		}
		count++
		i++
	}
	return s
}

func BannerString() string {
	rule   := strings.Repeat("─", bannerInner)
	top    := Cyan("╭" + rule + "╮")
	bottom := Cyan("╰" + rule + "╯")
	logo   := " " + Bold(Cyan("✻")) + "  " + Bold("mu agent")
	return top + "\n" + bannerRow(logo) + "\n" + bottom
}

func PrintBanner(goal string) {
	rule   := strings.Repeat("─", bannerInner)
	top    := Cyan("╭" + rule + "╮")
	bottom := Cyan("╰" + rule + "╯")
	blank  := Cyan("│") + strings.Repeat(" ", bannerInner) + Cyan("│")

	logo     := " " + Bold(Cyan("✻")) + "  " + Bold("mu agent")
	goalLine := " " + Dim("goal:") + " " + goal

	fmt.Println(top)
	fmt.Println(bannerRow(logo))
	fmt.Println(blank)
	fmt.Println(bannerRow(goalLine))
	fmt.Println(bottom)
	fmt.Println()
}
