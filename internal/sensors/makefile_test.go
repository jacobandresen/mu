package sensors

import (
	"os"
	"strings"
	"testing"
)

// TestFixOrphanTopLevelCommands_DuplicateAll verifies that when the model writes
// orphan commands AND an existing all: target, the sensor merges them without
// creating a second all: that would cause "overriding commands for target `all'".
func TestFixOrphanTopLevelCommands_DuplicateAll(t *testing.T) {
	src := `CC = gcc
CFLAGS = -I/usr/include/SDL2
gcc $(CFLAGS) -c main.c -o main.o
gcc main.o -o prog

.PHONY: all
all:
	echo done
`
	f, _ := os.CreateTemp("", "Makefile*")
	f.WriteString(src)
	f.Close()
	defer os.Remove(f.Name())

	fixed, err := FixOrphanTopLevelCommands(f.Name())
	if err != nil {
		t.Fatal(err)
	}
	if !fixed {
		t.Fatal("expected fixed=true")
	}
	data, _ := os.ReadFile(f.Name())
	out := string(data)
	count := strings.Count(out, "all:")
	if count != 1 {
		t.Errorf("expected exactly one all: target, got %d:\n%s", count, out)
	}
	if !strings.Contains(out, "main.c") {
		t.Errorf("orphan build commands should be present:\n%s", out)
	}
	t.Logf("Fixed:\n%s", out)
}
