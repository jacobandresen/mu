package ui

import "fmt"

func PrintBanner(goal string) {
	fmt.Println(Bold(Cyan("╔══════════════════════════════╗")))
	fmt.Println(Bold(Cyan("║") + Bold("        MU AGENT              ") + Bold(Cyan("║"))))
	fmt.Println(Bold(Cyan("╚══════════════════════════════╝")))
	fmt.Println(Dim("Goal: ") + goal)
	fmt.Println()
}
