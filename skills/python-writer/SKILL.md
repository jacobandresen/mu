# Python Writer Skill

This skill focuses on refining the generated Python code to ensure it adheres to common syntax and style guidelines. It includes rules to handle generic syntax errors that frequently occur in the generated code.

## Rules

1. **Syntax Error Handling**: Ensure all generated Python code is free from basic syntax errors such as missing colons, incorrect indentation, and unmatched parentheses.
2. **Variable Naming Conventions**: Use descriptive variable names that follow PEP 8 guidelines.
3. **Code Formatting**: Apply consistent formatting using tools like `black` or `autopep8` to ensure the code is readable and adheres to Python's style guide.
4. **Import Statements**: Ensure all necessary imports are present and correctly formatted, avoiding unused imports.
5. **Function Definitions**: Ensure functions are defined with proper syntax, including correct parameter lists and return types where applicable.

## Example Reflexes

- **Add Missing Colons**: If a line is missing a colon at the end of a statement (e.g., `if x = 1`), add the colon (`if x == 1:`).
- **Correct Indentation**: Ensure that code blocks are properly indented according to Python's rules.
- **Fix Unmatched Parentheses**: If there are unmatched parentheses in the code, balance them correctly.

## Implementation Details

The reflexes for this skill are implemented in the `src/mu/reflexes/python/` directory. Each reflex is a deterministic condition-action pair that checks for a specific syntax error and applies the necessary fix.

## Testing

To verify the effectiveness of these reflexes, run the following command:

```sh
mu agent "write a Python script to calculate Fibonacci numbers" --dir fib_project
```

Check that the generated code is free from syntax errors and adheres to the specified rules.