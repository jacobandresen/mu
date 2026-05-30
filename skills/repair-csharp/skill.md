---
name: repair-csharp
description: C# repair diagnostics — map dotnet build errors to targeted fixes.
---

- `CS0111: Type 'X' already defines a member called 'Y' with the same parameter types` — two files define the same method in the same class. Each class must live in exactly one file. `Main` belongs in `Program` (or `Program.cs`), not in a domain class like `FibonacciGenerator`. Fix: move `Main` into a separate `class Program { static void Main(...) { ... } }` and remove it from any domain class.
- `CS0101: The namespace 'N' already contains a definition for 'X'` — two files declare the same class name in the same namespace. Rename one class or move it to a different namespace.
- `CS0246: The type or namespace name 'X' could not be found` — missing `using` directive. Add `using System;`, `using System.Collections.Generic;`, or whichever namespace `X` belongs to.
- `CS1022: Type or namespace definition, or end-of-file expected` — a brace is missing or mismatched. Count opening and closing `{` `}` in the file and add/remove as needed.
- `CS5001: Program does not contain a static 'Main' method` — there is no entry point. Add `static void Main(string[] args) { ... }` inside a class.
- `CS1513: } expected` — a class or method body is missing a closing `}`. Count opening and closing braces in the file; add the missing `}` at the end of the affected block.
- `CS1529: A using clause must precede all other elements` — `using` directives must appear at the very top of the file, before any namespace or class declarations. Move all `using System;` etc. to the first lines.
- `CS8803: Top-level statements must precede namespace and type declarations` — mixing top-level code (statements outside any class) with explicit class/namespace declarations is invalid. Choose one style: either wrap everything in `class Program { static void Main(string[] args) { ... } }` (classic style), or use only top-level statements with no explicit `class Program` (modern .NET 6+ style). Do not mix both.
- `dotnet run` target in Makefile must NOT pass a source file — `dotnet run Program.cs` is invalid; use `dotnet run` or `dotnet run --project .`. The `dotnet run` command finds `Main` automatically from the `.csproj`.
- Makefile for C#: use `dotnet build` to compile and `dotnet run` to execute. Do not use `csc` or `mcs` directly unless the goal explicitly asks for Mono.
