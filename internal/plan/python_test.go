package plan

import (
	"os"
	"strings"
	"testing"
)

func TestFixPythonMakefileTest_BareTestTarget(t *testing.T) {
	content := "install:\n\tpip install -r requirements.txt\n\ntest:\n\tpytest\n"
	f, _ := os.CreateTemp("", "Makefile*")
	f.WriteString(content)
	f.Close()
	defer os.Remove(f.Name())

	fixed, err := FixPythonMakefileTest(f.Name())
	if err != nil {
		t.Fatalf("FixPythonMakefileTest: %v", err)
	}
	if !fixed {
		t.Error("expected fixed=true, got false")
	}
	data, _ := os.ReadFile(f.Name())
	result := string(data)
	if !strings.Contains(result, "\tPYTHONPATH=. pytest") {
		t.Errorf("expected PYTHONPATH=. pytest in output, got:\n%s", result)
	}
}

func TestFixPythonMakefileTest_AlreadyHasPYTHONPATH(t *testing.T) {
	content := "test:\n\tPYTHONPATH=. pytest\n"
	f, _ := os.CreateTemp("", "Makefile*")
	f.WriteString(content)
	f.Close()
	defer os.Remove(f.Name())

	fixed, err := FixPythonMakefileTest(f.Name())
	if err != nil {
		t.Fatalf("FixPythonMakefileTest: %v", err)
	}
	if fixed {
		t.Error("expected fixed=false when PYTHONPATH already set")
	}
}

func TestFixPythonMakefileTest_NoPytest(t *testing.T) {
	content := "test:\n\tgo test ./...\n"
	f, _ := os.CreateTemp("", "Makefile*")
	f.WriteString(content)
	f.Close()
	defer os.Remove(f.Name())

	fixed, err := FixPythonMakefileTest(f.Name())
	if err != nil {
		t.Fatalf("FixPythonMakefileTest: %v", err)
	}
	if fixed {
		t.Error("expected fixed=false when no pytest in Makefile")
	}
}

func TestFixPythonMakefileTest_PytestWithArgs(t *testing.T) {
	content := "test:\n\tpytest tests/ -v\n"
	f, _ := os.CreateTemp("", "Makefile*")
	f.WriteString(content)
	f.Close()
	defer os.Remove(f.Name())

	fixed, err := FixPythonMakefileTest(f.Name())
	if err != nil {
		t.Fatalf("FixPythonMakefileTest: %v", err)
	}
	if !fixed {
		t.Error("expected fixed=true for 'pytest tests/ -v'")
	}
	data, _ := os.ReadFile(f.Name())
	if !strings.Contains(string(data), "PYTHONPATH=. pytest tests/ -v") {
		t.Errorf("expected PYTHONPATH prepended, got:\n%s", string(data))
	}
}
