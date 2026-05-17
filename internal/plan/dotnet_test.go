package plan

import (
	"os"
	"strings"
	"testing"
)

func TestFixDotnetTestCommand_SingleCsproj(t *testing.T) {
	content := "## Files\n- [ ] fibonacci.csproj\n- [ ] Program.cs\n- [ ] ProgramTests.cs\n\n## Test Command\ndotnet test\n\n## Dependencies\n- dotnet\n- xunit"
	
	f, _ := os.CreateTemp("", "PLAN*.md")
	f.WriteString(content)
	f.Close()
	defer os.Remove(f.Name())

	p, err := Parse(f.Name())
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	t.Logf("TestCommand: %q", p.TestCommand)
	for _, task := range p.Tasks {
		t.Logf("Task: %q", task.FilePath)
	}

	fixed, err := FixDotnetTestCommand(f.Name(), p)
	if err != nil {
		t.Fatalf("FixDotnetTestCommand: %v", err)
	}
	if !fixed {
		t.Error("expected fixed=true, got false")
	}

	data, _ := os.ReadFile(f.Name())
	result := string(data)
	if !strings.Contains(result, "dotnet run --project fibonacci.csproj") {
		t.Errorf("expected 'dotnet run --project fibonacci.csproj' in output, got:\n%s", result)
	}
	if strings.Contains(result, "\ndotnet test\n") {
		t.Errorf("'dotnet test' should have been replaced in:\n%s", result)
	}
}
