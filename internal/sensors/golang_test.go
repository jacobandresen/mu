package sensors

import (
	"os"
	"strings"
	"testing"
)

func TestFixGoMod_BareGoDirective(t *testing.T) {
	content := "module ping\n\ngo 1.21\n\n\tgo\n"
	f, _ := os.CreateTemp("", "go.mod*")
	f.WriteString(content)
	f.Close()
	defer os.Remove(f.Name())

	fixed, err := FixGoMod(f.Name())
	if err != nil {
		t.Fatalf("FixGoMod: %v", err)
	}
	if !fixed {
		t.Error("expected fixed=true for bare 'go' line")
	}
	data, _ := os.ReadFile(f.Name())
	result := string(data)
	lines := strings.Split(result, "\n")
	for _, line := range lines {
		if strings.TrimSpace(line) == "go" {
			t.Errorf("bare 'go' line should have been dropped, got:\n%s", result)
		}
	}
	if !strings.Contains(result, "go 1.21") {
		t.Errorf("versioned go directive should be preserved, got:\n%s", result)
	}
}

func TestFixGoMod_NoBareGoDirective(t *testing.T) {
	content := "module app\n\ngo 1.21\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n)\n"
	f, _ := os.CreateTemp("", "go.mod*")
	f.WriteString(content)
	f.Close()
	defer os.Remove(f.Name())

	fixed, err := FixGoMod(f.Name())
	if err != nil {
		t.Fatalf("FixGoMod: %v", err)
	}
	if fixed {
		t.Error("expected fixed=false for clean go.mod")
	}
}
