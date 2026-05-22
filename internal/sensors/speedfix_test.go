package sensors

import (
	"os"
	"strings"
	"testing"
)

func TestFixSQLiteBareListCursor_BothBugs(t *testing.T) {
	src := `import sqlite3

class TodoManager:
    def list_todos(self, completed=None):
        query = 'SELECT * FROM todos'
        if completed is not None:
            query += ' WHERE completed = ?'
        with self.conn:
            cursor = self.conn.execute(query, (completed,)) if completed is not None else self.conn.cursor()
            return [dict(row) for row in cursor.fetchall()]
`
	f, _ := os.CreateTemp("", "todo*.py")
	f.WriteString(src)
	f.Close()
	defer os.Remove(f.Name())

	fixed, err := FixSQLiteBareListCursor(f.Name())
	if err != nil {
		t.Fatal(err)
	}
	if !fixed {
		t.Fatal("expected fixed=true")
	}
	data, _ := os.ReadFile(f.Name())
	out := string(data)
	if strings.Contains(out, ".cursor()") {
		t.Errorf("bare cursor() should be gone:\n%s", out)
	}
	if strings.Contains(out, "dict(row)") {
		t.Errorf("dict(row) should be replaced:\n%s", out)
	}
	if !strings.Contains(out, "self.conn.execute(query)") {
		t.Errorf("expected unconditional execute(query):\n%s", out)
	}
	if !strings.Contains(out, "return list(cursor.fetchall())") {
		t.Errorf("expected list(cursor.fetchall()):\n%s", out)
	}
	t.Logf("Fixed:\n%s", out)
}

func TestFixSQLiteBareListCursor_NoChange(t *testing.T) {
	src := `def list_todos(self):
    return list(self.conn.execute('SELECT task FROM todos').fetchall())
`
	f, _ := os.CreateTemp("", "todo*.py")
	f.WriteString(src)
	f.Close()
	defer os.Remove(f.Name())

	fixed, _ := FixSQLiteBareListCursor(f.Name())
	if fixed {
		t.Errorf("expected no change for clean code")
	}
}

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
