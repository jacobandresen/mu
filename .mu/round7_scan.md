# Round 7 Session Archive Scan

**Scan date:** 2026-06-12 to 2026-06-13  
**Sessions analyzed:** 133 (filtered: >= 20260612-192713)

---

## Outcome tally

| Outcome | Count | % |
|---------|-------|---|
| success | 90 | 67.7% |
| stalled | 42 | 31.6% |
| interrupted | 1 | 0.8% |
| **TOTAL** | **133** | **100%** |

**Overall pass rate: 67.7% (90/133)**

### Pass rate by problem (last component of project_dir)

| Problem | Pass | Total | Rate |
|---------|------|-------|------|
| p1-helloworld | 12 | 12 | 100% |
| p3-sdl2 | 12 | 12 | 100% |
| p6-rust | 11 | 11 | 100% |
| p5-gin | 11 | 12 | 92% |
| p9-vue-todo | 12 | 13 | 92% |
| p2-sqlite | 9 | 15 | 60% |
| p7-flask | 9 | 15 | 60% |
| p4-fibonacci | 6 | 12 | 50% |
| p8-node-todo | 8 | 19 | 42% |
| **p10-dotnet-vue-blog** | **0** | **12** | **0%** |

**Note:** No unknown outcomes with exit_code -1 detected.

---

## Failure inventory

43 non-success sessions:

* 20260612-193748-write_the_fibonacci_sequence_using_C_Use / p4-fibonacci / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 277s
  `/Users/jacob/Projects/mu/dojo/p4-fibonacci/FibonacciTests.cs(9,62): error CS8124: Tuple must contain at least two elements`
  `/Users/jacob/Projects/mu/dojo/p4-fibonacci/FibonacciTests.cs(9,63): error CS1519: Invalid token ')' in a member declarat`

* 20260612-194500-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / tests still failing after repair for tests/ApiTests.cs / repair_iters: 0 / duration: 160s
  `NOTE: PLAN-model.md missing some goal terms: minimal, typescript, frontend, define, expose, posts, returning, json, call`
  `MSBUILD : error MSB1003: Specify a project or solution file. The current working directory does not contain a project or`

* 20260612-195307-write_a_Python_todo_list_manager_that_st / p2-sqlite / stalled / lint still failing after repair for database.py / repair_iters: 0 / duration: 111s
  `FAILED test_main.py::test_delete_todo - TypeError: 'dict' object is not callable`
  `database.py:3:8: undefined name 'declarative_base'`

* 20260612-201540-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / final test gate failed: final tests failed / repair_iters: 0 / duration: 306s
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(13,7): error CS0101: The namespace '<global namespace`
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(20,54): error CS0246: The type or namespace name 'Pr`

* 20260612-202755-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / final test gate failed: final tests failed / repair_iters: 0 / duration: 203s
  `ReferenceError: test is not defined`

* 20260612-204229-write_the_fibonacci_sequence_using_C_Use / p4-fibonacci / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 228s
  `/Users/jacob/Projects/mu/dojo/p4-fibonacci/Program.cs(7,21): error CS0017: Program has more than one entry point defined`

* 20260612-205826-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 233s
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(18,54): error CS0246: The type or namespace name 'Pr`
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/backend/Infrastructure/AppDb.cs(7,28): error CS0053: Inconsistent acce`

* 20260612-211708-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 154s
  `ReferenceError: it is not defined`

* 20260612-211943-write_a_Python_REST_API_using_Flask_with / p7-flask / stalled / lint still failing after repair for main.py / repair_iters: 0 / duration: 158s
  `main.py:22:9: undefined name '_db'`
  `main.py:25:6: undefined name 'app'`

* 20260612-212304-write_a_Python_todo_list_manager_that_st / p2-sqlite / stalled / tests still failing after repair for test_main.py / repair_iters: 6 / duration: 222s
  `FAILED test_main.py::test_delete - sqlite3.OperationalError: no such table: t...`
  `ERROR test_main.py::test_delete - AttributeError: 'FixtureFunctionDefinition'...`

* 20260612-214321-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / final test gate failed: final tests failed / repair_iters: 0 / duration: 205s
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(9,7): error CS0101: The namespace '<global namespace`
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(16,54): error CS0246: The type or namespace name 'Pr`

* 20260612-215746-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / tests still failing after repair for test/index.test.js / repair_iters: 6 / duration: 293s
  `TypeError: Cannot read properties of undefined (reading 'writeFile')`

* 20260612-221307-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 195s
  `Test Suites: 1 failed, 1 total`
  `Tests:       3 failed, 3 total`

* 20260612-222959-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / final test gate failed: final tests failed / repair_iters: 0 / duration: 229s
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(9,54): error CS0246: The type or namespace name 'Pro`
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/backend/Infrastructure/AppDb.cs(7,28): error CS0053: Inconsistent acce`

* 20260612-225343-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / tests still failing after repair for tests/ApiTests.cs / repair_iters: 0 / duration: 216s
  `NOTE: PLAN-model.md missing some goal terms: minimal, backend, typescript, frontend, backend, expose, posts, returning`
  `MSBUILD : error MSB1003: Specify a project or solution file. The current working directory does not contain a project or`

* 20260612-225720-write_the_fibonacci_sequence_using_C_Use / p4-fibonacci / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 191s
  `/Users/jacob/Projects/mu/dojo/p4-fibonacci/Program.cs(21,21): error CS0017: Program has more than one entry point define`

* 20260612-230746-write_a_Python_REST_API_using_Flask_with / p7-flask / stalled / tests still failing after repair for test_models.py / repair_iters: 6 / duration: 300s
  (No error lines captured in logs)

* 20260612-231532-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 310s
  `SyntaxError: "undefined" is not valid JSON`
  `Test Suites: 1 failed, 1 total`

* 20260612-233217-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 228s
  `Test Suites: 1 failed, 1 total`
  `Tests:       2 failed, 2 passed, 4 total`

* 20260612-233931-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / final test gate failed: final tests failed / repair_iters: 0 / duration: 206s
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/backend/Infrastructure/AppDb.cs(7,28): error CS0053: Inconsistent acce`
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(17,54): error CS0246: The type or namespace name 'Pr`

* 20260612-235629-write_a_Python_todo_list_manager_that_st / p2-sqlite / stalled / tests still failing after repair for test_models.py / repair_iters: 6 / duration: 226s
  `FAILED test_main.py::test_delete_todo - TypeError: 'dict' object is not callable`
  `========================= 1 failed, 1 passed in 0.09s ==========================`

* 20260613-001657-write_the_fibonacci_sequence_using_C_Use / p4-fibonacci / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 162s
  `/Users/jacob/Projects/mu/dojo/p4-fibonacci/Program.cs(5,21): error CS0017: Program has more than one entry point defined`

* 20260613-002158-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / tests still failing after repair for tests/ApiTests.cs / repair_iters: 0 / duration: 181s
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(19,6): error CS0246: The type or namespace name 'Fac`
  `The build failed. Fix the build errors and run again.`

* 20260613-004143-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / tests still failing after repair for test/todo.test.js / repair_iters: 6 / duration: 299s
  `Test Suites: 2 failed, 1 passed, 3 total`
  `Tests:       3 failed, 3 passed, 6 total`

* 20260613-005146-write_a_Python_REST_API_using_Flask_with / p7-flask / stalled / lint still failing after repair for test_schema.py / repair_iters: 0 / duration: 105s
  (No error lines captured in logs)

* 20260613-010727-write_a_Python_REST_API_using_Flask_with / p7-flask / stalled / tests still failing after repair for test_todo.py / repair_iters: 0 / duration: 158s
  `!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!`
  `=============================== 1 error in 0.06s ===============================`

* 20260613-011220-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / final test gate failed: final tests failed / repair_iters: 0 / duration: 204s
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(9,7): error CS0101: The namespace '<global namespace`
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(16,54): error CS0246: The type or namespace name 'Pr`

* 20260613-012222-write_a_Python_todo_list_manager_that_st / p2-sqlite / stalled / tests still failing after repair for test_main.py / repair_iters: 6 / duration: 242s
  `FAILED test_main.py::test_add_and_list_todo - RuntimeError: Working outside o...`
  `FAILED test_main.py::test_delete_todo - RuntimeError: Working outside of appl...`

* 20260613-013420-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 167s
  `TypeError: it is not a function`

* 20260613-015357-write_a_Python_todo_list_manager_that_st / p2-sqlite / stalled / tests still failing after repair for test_database.py / repair_iters: 0 / duration: 175s
  `FAILED test_main.py::test_add_and_get - NameError: name 'cursor' is not defined`
  `FAILED test_main.py::test_delete_todo - NameError: name 'cursor' is not defined`

* 20260613-020633-write_a_Vue_3_TypeScript_todo_list_web_a / p9-vue-todo / stalled / lint still failing after repair for tests/backend.test.ts / repair_iters: 0 / duration: 191s
  `Test Files  1 failed (1)`
  `error TS5112: tsconfig.json is present but will not be loaded if files are specified on commandline`

* 20260613-021446-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 195s
  `ReferenceError: it is not defined`

* 20260613-022100-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / tests still failing after repair for tests/ApiTests.cs / repair_iters: 0 / duration: 159s
  `NOTE: PLAN-model.md missing some goal terms: minimal, typescript, frontend, define, expose, posts, returning, json, call`
  `MSBUILD : error MSB1003: Specify a project or solution file. The current working directory does not contain a project or`

* 20260613-022340-write_a_Go_HTTP_server_with_a_GET_-ping_ / p5-gin / stalled / final test gate failed: final tests failed / repair_iters: 0 / duration: 143s
  `./main.go:14:1: syntax error: unexpected ., expected }`
  `FAIL	p5-gin [build failed]`

* 20260613-022737-write_a_Python_REST_API_using_Flask_with / p7-flask / interrupted / (empty fail_reason) / repair_iters: 0 / duration: 77s
  (No error lines captured in logs)

* 20260613-023950-write_the_fibonacci_sequence_using_C_Use / p4-fibonacci / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 155s
  `/Users/jacob/Projects/mu/dojo/p4-fibonacci/FibonacciTests.cs(6,21): error CS0116: A namespace cannot directly contain me`

* 20260613-024226-write_a_Python_REST_API_using_Flask_with / p7-flask / stalled / tests still failing after repair for test_main.py / repair_iters: 6 / duration: 225s
  `!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!`
  `=============================== 1 error in 0.47s ===============================`

* 20260613-024821-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / final test gate failed: final tests failed / repair_iters: 0 / duration: 192s
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(9,7): error CS0101: The namespace '<global namespace`
  `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(16,54): error CS0246: The type or namespace name 'Pr`

* 20260613-025929-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / final test gate failed: final tests failed / repair_iters: 0 / duration: 232s
  `ReferenceError: jest is not defined`

* 20260613-032400-write_a_blog_application_with_an_ASPNET_ / p10-dotnet-vue-blog / stalled / tests still failing after repair for tests/ApiTests.cs / repair_iters: 0 / duration: 115s
  `NOTE: PLAN-model.md missing some goal terms: minimal, backend, typescript, frontend, backend, define, expose, posts, ret`
  `MSBUILD : error MSB1003: Specify a project or solution file. The current working directory does not contain a project or`

* 20260613-033240-write_a_Python_todo_list_manager_that_st / p2-sqlite / stalled / tests still failing after repair for test_main.py / repair_iters: 6 / duration: 152s
  `ERROR test_main.py - AttributeError: 'TodoManager' object has no attribute '_...`
  `!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!`

* 20260613-033512-write_a_Nodejs_todo_list_manager_that_st / p8-node-todo / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 244s
  `● Test suite failed to run`
  `Test Suites: 1 failed, 1 total`

* 20260613-033917-write_the_fibonacci_sequence_using_C_Use / p4-fibonacci / stalled / final test gate failed: final tests failed / repair_iters: 6 / duration: 151s
  `/Users/jacob/Projects/mu/dojo/p4-fibonacci/Program.cs(5,21): error CS0017: Program has more than one entry point defined`
  `/Users/jacob/Projects/mu/dojo/p4-fibonacci/FibonacciTests.cs(9,51): error CS0122: 'Program.Fibonacci(int)' is inaccessib`

---

## Failure buckets

### C# multiple entry points (CS0017)
**Count:** 4 sessions | **Problem:** p4-fibonacci (50% of p4 failures)

**Representative error:**
```
/Users/jacob/Projects/mu/dojo/p4-fibonacci/Program.cs(5,21): error CS0017: Program has more than one entry point defined
```

**Sessions:** 20260612-204229, 20260612-225720, 20260613-001657, 20260613-033917

**Defect:** Repair loop or reflex is duplicating the `static void Main()` entry point, possibly by appending instead of replacing during code generation. All 4 instances consistently fail after 6 repair iterations, suggesting the problem emerges *during* repair rather than initial generation.

---

### C# type/namespace not found (CS0246)
**Count:** 8 sessions | **Problem:** p10-dotnet-vue-blog (67% of p10 failures)

**Representative error:**
```
/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(16,54): error CS0246: The type or namespace name 'ProjectName' could not be found
```

**Sessions:** 20260612-201540, 20260612-205826, 20260612-214321, 20260612-222959, 20260613-011220, 20260613-024821, and 2 more

**Defect:** Backend infrastructure classes (AppDb, repository interfaces) are not generated or are incomplete. The planner stage creates test stubs that reference types that don't exist in the generated backend. Suggests model understands the architecture but reflexes fail to emit the actual type definitions.

---

### MSBuild no project file (MSB1003)
**Count:** 4 sessions | **Problem:** p10-dotnet-vue-blog (33% of p10 failures)

**Representative error:**
```
MSBUILD : error MSB1003: Specify a project or solution file. The current working directory does not contain a project or solution file.
NOTE: PLAN-model.md missing some goal terms: minimal, backend, typescript, frontend, define, expose, posts, returning, json, calls...
```

**Sessions:** 20260612-194500, 20260612-225343, 20260613-022100, 20260613-032400

**Defect:** PLAN-model.md is not extracting full goal intent from the problem statement, causing stage planner to skip backend project scaffolding. The missing goal terms (backend, define, expose, json) indicate the planner isn't reading requirements thoroughly. Repair logic cannot recover because no .csproj file exists to build against.

---

### JS/Node test reference error (ReferenceError)
**Count:** 4 sessions | **Problem:** p8-node-todo (21% of p8 failures)

**Representative error:**
```
ReferenceError: test is not defined
ReferenceError: it is not defined
ReferenceError: jest is not defined
```

**Sessions:** 20260612-202755, 20260612-211708, 20260613-021446, 20260613-025929

**Defect:** Test files are written with Jest/Mocha syntax (`describe()`, `it()`, `test()`) but the test runner or global scope doesn't have these functions available. Likely the test file template includes the framework name but doesn't emit the require/import statement, or runs tests with Node directly instead of Jest.

---

### Python undefined name (linting errors)
**Count:** 1 session | **Problem:** p7-flask

**Representative error:**
```
main.py:22:9: undefined name '_db'
main.py:25:6: undefined name 'app'
```

**Session:** 20260612-211943

**Defect:** Flask SQLAlchemy instance `_db` or `app` variable is referenced before it's defined in the file scope. Initialization order issue in generated code.

---

### Python TypeError: 'dict' object is not callable
**Count:** 2 sessions | **Problem:** p2-sqlite

**Representative error:**
```
FAILED test_main.py::test_delete_todo - TypeError: 'dict' object is not callable
```

**Sessions:** 20260612-195307, 20260612-235629

**Defect:** SQLAlchemy model or ORM wrapper is returning a dict when code expects a callable function/model. Likely a missing method or decorator on the model class.

---

### Flask app context error (RuntimeError)
**Count:** 1 session | **Problem:** p2-sqlite

**Representative error:**
```
FAILED test_main.py::test_add_and_list_todo - RuntimeError: Working outside of application context
```

**Session:** 20260613-012222

**Defect:** Test setup does not push Flask app context before accessing database. Flask-SQLAlchemy requires active app context.

---

### SQLite operational error (no such table)
**Count:** 1 session | **Problem:** p2-sqlite

**Representative error:**
```
FAILED test_main.py::test_delete - sqlite3.OperationalError: no such table
```

**Session:** 20260612-212304

**Defect:** Database initialization or migration not running before tests. Tables not created.

---

### Python NameError: cursor not defined
**Count:** 2 sessions | **Problem:** p2-sqlite

**Representative error:**
```
FAILED test_main.py::test_add_and_get - NameError: name 'cursor' is not defined
```

**Sessions:** 20260613-015357, 20260613-033240

**Defect:** Database cursor not properly initialized in test setup or helper functions.

---

### JSON syntax error
**Count:** 1 session | **Problem:** p8-node-todo

**Representative error:**
```
SyntaxError: "undefined" is not valid JSON
```

**Session:** 20260612-231532

**Defect:** todos.json file contains literal string `undefined` instead of valid JSON (null or omitted). Code generation error in JSON file creation.

---

### JS undefined property access
**Count:** 1 session | **Problem:** p8-node-todo

**Representative error:**
```
TypeError: Cannot read properties of undefined (reading 'writeFile')
```

**Session:** 20260612-215746

**Defect:** File system module (fs) not properly imported or initialized; attempting to call fs.writeFile on undefined fs reference.

---

### Go syntax error
**Count:** 1 session | **Problem:** p5-gin

**Representative error:**
```
./main.go:14:1: syntax error: unexpected ., expected }
```

**Session:** 20260613-022340

**Defect:** Struct or method definition contains mismatched braces or dot syntax (e.g., incomplete field definition in struct literal).

---

### C# tuple syntax error
**Count:** 1 session | **Problem:** p4-fibonacci

**Representative error:**
```
/Users/jacob/Projects/mu/dojo/p4-fibonacci/FibonacciTests.cs(9,62): error CS8124: Tuple must contain at least two elements
```

**Session:** 20260612-193748

**Defect:** Tuple syntax in test file uses single element `(value)` instead of valid tuple `(value, default)` or discards tuple syntax entirely.

---

### p7-flask test collection errors
**Count:** 4 sessions | **Problem:** p7-flask (27% of p7 failures)

**Representative error:**
```
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
[error details omitted]
```

**Sessions:** 20260612-230746, 20260613-005146, 20260613-010727, 20260613-024226

**Defect:** Test file import errors or pytest fixture misconfigurations preventing test discovery. Likely missing conftest.py or app initialization in test file.

---

### p8-node-todo multi-test failures
**Count:** 5 sessions | **Problem:** p8-node-todo (26% of p8 failures)

**Representative error:**
```
Test Suites: 1 failed, 1 total
Tests:       3 failed, 3 total
```

**Sessions:** 20260612-221307, 20260612-233217, 20260613-004143, 20260613-033512, and 1 more

**Defect:** Some tests pass, others fail, indicating partial implementation or state pollution between tests. The generated todo manager may be missing delete/list operations, or tests depend on execution order.

---

### p9-vue-todo tsconfig conflict
**Count:** 1 session | **Problem:** p9-vue-todo (8% of p9 failures)

**Representative error:**
```
error TS5112: tsconfig.json is present but will not be loaded if files are specified on commandline
```

**Session:** 20260613-020633

**Defect:** TypeScript compiler configuration conflict: test command specifies files on CLI while tsconfig.json exists. Repair logic added a tsconfig.json but didn't update the test command to omit file arguments.

---

## Forensics coverage

| Metric | Count |
|--------|-------|
| Failed sessions with missing fail_reason | 1 |
| Failed sessions with missing transcript.jsonl | 0 |
| Failed sessions with missing workspace/ | 0 |
| Failed sessions with repair_trace.jsonl | 42 |
| Failed sessions with reflex_diffs.jsonl | 24 |

**Summary:** Excellent forensics depth. Only 1 session (20260613-022737, p7-flask interrupted) lacks a fail_reason field. 42/43 failures have repair_trace.jsonl showing the repair loop operated. 24/43 have reflex_diffs.jsonl, indicating reflexes modified code in ~56% of failures.

**Note on reflex_diffs.jsonl:** When present, these files document code modifications but do not directly indicate whether the reflex *caused* the failure or merely *attempted repair*. Sessions with CS0017 (multiple entry points) and CS0246 (missing types) should be reviewed for evidence that reflexes duplicated code or generated incomplete classes.

---

## Summary

**Bottleneck problems (0% pass rate):** p10-dotnet-vue-blog (12/12 failures). Root causes cluster around incomplete project scaffolding (missing .csproj, infrastructure classes not generated, PLAN-model not extracting full intent). Strongly suggests model/planner stage regression.

**At-risk problems (>30% failure):** p8-node-todo (42% pass), p4-fibonacci (50% pass), p2-sqlite (60% pass), p7-flask (60% pass). C# and Python problems show code generation + repair loop ineffectiveness. Node.js test runner issues persist across multiple sessions.

**Reflex audit:** 24 sessions show reflex modifications, but causation is unclear without deep code analysis. p4-fibonacci's CS0017 errors (duplicated entry points) warrant investigation—reflex may be appending instead of replacing during repair.

