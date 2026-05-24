## Files
- [x] p4-fibonacci.csproj — auto-grounded (C# needs a project file)
- [x] Program.cs — C# source code for Fibonacci sequence
- [x] Makefile — build rules for compiling and running the program

## Test Command
make run

## Dependencies
dotnet, make

## Repair History
- final test gate: repair loop exhausted — still failing. Error:
  ```
  Program.cs	dotnet run
  make: Program.cs: Ingen sådan fil eller filkatalog
  make: *** [Makefile:7: run] Fejl 127
  ```
