package system

import (
	"bytes"
	"os"
	"os/exec"
)

func runOutput(name string, args ...string) (string, error) {
	var buf bytes.Buffer
	c := exec.Command(name, args...)
	c.Stdout = &buf
	err := c.Run()
	return buf.String(), err
}

func runOutputEnv(env []string, name string, args ...string) (string, error) {
	var buf bytes.Buffer
	c := exec.Command(name, args...)
	c.Env = append(os.Environ(), env...)
	c.Stdout = &buf
	err := c.Run()
	return buf.String(), err
}
