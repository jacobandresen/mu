package sensors

import (
	"os"
	"os/exec"
	"regexp"
	"strings"
)

// FixCsprojTargetFramework rewrites the <TargetFramework> element in a .csproj file to
// match the dotnet major version installed on the machine. Models often write a fixed
// version (e.g. net6.0) that doesn't match the installed SDK.
func FixCsprojTargetFramework(f string) (bool, error) {
	out, err := exec.Command("dotnet", "--version").Output()
	if err != nil {
		return false, nil
	}
	ver := strings.TrimSpace(string(out))
	parts := strings.SplitN(ver, ".", 2)
	if len(parts) == 0 {
		return false, nil
	}
	want := "net" + parts[0] + ".0"

	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	content := string(data)
	re := regexp.MustCompile(`<TargetFramework>net\d+\.\d+</TargetFramework>`)
	fixed := re.ReplaceAllString(content, "<TargetFramework>"+want+"</TargetFramework>")
	if fixed == content {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(fixed), 0644)
}

// FixCsprojOutputType adds <OutputType>Exe</OutputType> to a .csproj file when the element
// is missing. SDK-style projects that omit OutputType are treated as Library and cannot be
// run with "dotnet run".
func FixCsprojOutputType(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	content := string(data)
	if strings.Contains(content, "<OutputType>") {
		return false, nil
	}
	fixed := strings.Replace(content, "</PropertyGroup>",
		"  <OutputType>Exe</OutputType>\n</PropertyGroup>", 1)
	if fixed == content {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(fixed), 0644)
}

// FixCsprojCompileItems removes explicit <Compile Include="..."> items from .csproj files.
// SDK-style projects auto-include all .cs files; explicit Compile items cause duplicates
// and build errors.
func FixCsprojCompileItems(f string) (bool, error) {
	data, err := os.ReadFile(f)
	if err != nil {
		return false, err
	}
	content := string(data)
	reCompile := regexp.MustCompile(`\s*<Compile\s+Include="[^"]*"\s*/>`)
	fixed := reCompile.ReplaceAllString(content, "")
	reEmptyIG := regexp.MustCompile(`(?s)\s*<ItemGroup>\s*</ItemGroup>`)
	fixed = reEmptyIG.ReplaceAllString(fixed, "")
	if fixed == content {
		return false, nil
	}
	return true, os.WriteFile(f, []byte(fixed), 0644)
}
