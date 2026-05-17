package ui

import (
	"os"
	"regexp"
)

var colorEnabled = isTerminal()

func isTerminal() bool {
	if os.Getenv("NO_COLOR") != "" {
		return false
	}
	fi, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return (fi.Mode() & os.ModeCharDevice) != 0
}

func wrap(code, s string) string {
	if !colorEnabled {
		return s
	}
	return "\033[" + code + "m" + s + "\033[0m"
}

func Green(s string) string   { return wrap("32", s) }
func Yellow(s string) string  { return wrap("33", s) }
func Red(s string) string     { return wrap("31", s) }
func Cyan(s string) string    { return wrap("36", s) }
func Magenta(s string) string { return wrap("35", s) }
func Bold(s string) string    { return wrap("1", s) }
func Dim(s string) string     { return wrap("2", s) }

var ansiRE = regexp.MustCompile(`\033\[[0-9;]*m`)

func StripANSI(s string) string { return ansiRE.ReplaceAllString(s, "") }

func PrintTable(headers []string, rows [][]string) {
	cols := len(headers)
	widths := make([]int, cols)
	for i, h := range headers {
		widths[i] = len(StripANSI(h))
	}
	for _, row := range rows {
		for i, cell := range row {
			if i < cols {
				if n := len(StripANSI(cell)); n > widths[i] {
					widths[i] = n
				}
			}
		}
	}
	printRow := func(cells []string) {
		for i, cell := range cells {
			if i >= cols {
				break
			}
			pad := widths[i] - len(StripANSI(cell))
			os.Stdout.WriteString(cell)
			for range pad {
				os.Stdout.WriteString(" ")
			}
			if i < cols-1 {
				os.Stdout.WriteString("  ")
			}
		}
		os.Stdout.WriteString("\n")
	}
	printRow(headers)
	sep := make([]string, cols)
	for i, w := range widths {
		s := ""
		for range w {
			s += "-"
		}
		sep[i] = s
	}
	printRow(sep)
	for _, row := range rows {
		printRow(row)
	}
}
