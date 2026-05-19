package subcommands

import "testing"

func TestDetectLanguage(t *testing.T) {
	cases := []struct {
		name string
		goal string
		want string
	}{
		// Dojo problems
		{
			"P1 helloworld C",
			"write a hello world program in C. Use clang to compile it and run it.",
			"c",
		},
		{
			"P2 sqlite Python",
			"write a Python todo list manager that stores todos in a SQLite database. Support add, list, and delete operations. Include a test file using pytest.",
			"python",
		},
		{
			"P3 SDL2 C",
			"render a line on screen via SDL2. Use sdl2-config in the Makefile to set up SDL2 libs.",
			"c",
		},
		{
			"P4 fibonacci C#",
			"write the fibonacci sequence using C#. Use the dotnet command to compile C#.",
			"csharp",
		},
		{
			"P5 go/gin",
			`write a Go HTTP server with a GET /ping endpoint that returns JSON {"status":"ok"}. Use the Gin framework. Include a Makefile.`,
			"go",
		},
		{
			"P6 rust",
			"write a Rust program that prints Hello, world! Use Cargo.",
			"rust",
		},
		{
			"P7 flask",
			"write a Python REST API using Flask with a SQLite backend. Support POST /todos (body: JSON with a 'task' field) and GET /todos (returns list of todos). Include a pytest test file that tests both endpoints. Provide a Makefile that installs dependencies with pip and runs pytest.",
			"python",
		},
		// False-positive guards
		{"no false positive: begin", "begin the project", ""},
		{"no false positive: trust", "we trust the system", ""},
		{"no false positive: pipeline", "CI pipeline for deployment", ""},
		{"no false positive: let's go lowercase", "let's go write something", ""},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := detectLanguage(tc.goal)
			if got != tc.want {
				t.Errorf("detectLanguage(%q) = %q, want %q", tc.goal, got, tc.want)
			}
		})
	}
}
