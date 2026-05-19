## Files
- [x] fibonacci.csproj
- [x] Program.cs — C# console app to generate Fibonacci sequence

## Test Command
dotnet run --project fibonacci.csproj

## Dependencies
- dotnet (SDK) | C# language server
- dotnet format (built-in with SDK)
```

## Repair History
- final test gate: all retries exhausted — still failing. Error:
  ```
  Unable to proceed with project '/Users/jacob/Projects/mu/dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-19-B/p4-fibonacci/fibonacci.csproj'.
  Ensure you have a runnable project type.
  A runnable project should target a runnable TFM (for instance, net10.0) and have OutputType 'Exe'.
  The current OutputType is 'Library'.
  ```
- test repair attempt 1 — still failing. Error:
  ```
  Unable to proceed with project '/Users/jacob/Projects/mu/dojo/claude-qwen3-8b-macos-m2-8gb-v0.4.0-2026-05-19-B/p4-fibonacci/fibonacci.csproj'.
  Ensure you have a runnable project type.
  A runnable project should target a runnable TFM (for instance, net10.0) and have OutputType 'Exe'.
  The current OutputType is 'Library'.
  ```
