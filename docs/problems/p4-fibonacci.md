# p4-fibonacci

_‹ [All problems](../README.md)_

- **Goal:** write the fibonacci sequence using C#. Use the dotnet command to compile C#.
- **Toolchains:** dotnet
- **Difficulty:** moderate
- **Minimize:** L0

## What it builds

A C# console application that prints the Fibonacci sequence (typically the first 10-20 numbers).

## Last run

_Not yet measured in this environment._

## Dominant errors

See [challenges](../challenges/) for the classes that recur across problems. p4-specific notes:

- **CS0017:** Program has more than one entry point - when the model generates both a `Main` method and top-level statements
- **CS0246:** The type or namespace name could not be found - missing `using` directives
- **CS1519:** Invalid token - malformed C# syntax in member declarations

## Token usage

_Not yet recorded._

## Reflexes that carry it

- [`fix_csharp_duplicate_classes`](../../src/mu/reflexes/csharp/fix_csharp_duplicate_classes.py)
- [`fix_csharp_missing_using`](../../src/mu/reflexes/csharp/fix_csharp_missing_using.py)
- [`fix_csharp_consecutive_duplicate_signatures`](../../src/mu/reflexes/csharp/fix_csharp_consecutive_duplicate_signatures.py)
