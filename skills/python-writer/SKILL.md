# Python Writer Skill

## Reflexes

Post-write fixers that fire on Python sources to repair general classes of model error:

- **fix_missing_close_paren**: Add missing `)` after triple-quoted `execute()` call.
- **fix_python_decorator_colon**: Remove spurious trailing `:` from Python decorator lines.
- **fix_python_unindented_body**: Indent a `def`/`class` body the model wrote at the parent's column.
- **fix_multiline_single_quote**: Replace multi-line single-quoted SQL strings with triple-quoted strings.
- **fix_syntax_artifact**: General regex to handle other common syntax artifacts in Python code.
- **fix_python_missing_def**: Insert a missing `def funcname():` between an orphaned decorator and the function body.
- **fix_python_method_indent**: Fix a `def` that lost its indentation after a class-level declaration.
- **fix_python_missing_stdlib_imports**: Add missing `import` statements for common stdlib modules.
- **fix_python_missing_thirdparty_imports**: Add missing imports for SQLAlchemy, Flask, pytest, and other third-party symbols.
- **fix_python_missing_project_imports**: Add intra-project imports when local modules are used but not imported.
- **fix_python_undefined_imports**: Resolve undefined names by checking sibling files and adding needed imports.
- **py_autofix**: Strip unused imports/variables from a Python file (pure-Python).

## Patterns

Generic syntax errors: Handle common patterns such as missing parentheses, incorrect indentation, missing function definitions, and undefined symbols.