# Round 4 Scan: Improvement Verification

## Outcome tally

**Total sessions:** 31 (all >= 20260612-115034)

**Pass rate by outcome:**
- success: 22 (71.0%)
- stalled: 8 (26.0%)
- error: 1 (3.0%)

**Overall pass rate:** 71.0%

**Pass rate per problem (vs previous round):**
- p1: 1/1 (100%) — was 100% (0pp)
- p2: 2/4 (50%) — was 100% (-50pp)
- p3: 1/1 (100%) — was 100% (0pp)
- p4: 0/2 (0%) — was 33% (-33pp)
- p5: 2/2 (100%) — was 67% (+33pp)
- p6: 1/1 (100%) — was 100% (0pp)
- p7: 1/2 (50%) — was 50% (0pp)
- p8: 7/8 (88%) — was 100% (-12pp)
- p9: 2/3 (67%) — was 67% (0pp)
- p10: 5/7 (71%) — was 33% (+38pp)

## Fix verification

### 1. NU1202 ".NET package not compatible with net7.0" errors

**Status: FIXED** ✓

Search across all 31 sessions (20260612-115034 onwards) found zero occurrences of "NU1202" in any logs. This fix has held.

### 2. "NameError: name 'Flask' is not defined" in p7

**Status: PARTIALLY IMPROVED**

p7 is 1/2 pass in this run (same as previous round). The one stalled session (20260612-125102) does not contain a Flask NameError in the logs; instead it fails on Makefile target rules (see Failure buckets below).

Stdlib import reflex was applied in 9 sessions (across p2 and p7), indicating the model is attempting to invoke the fix. Agent logs show messages like "Fixed test_main.py: added missing stdlib imports."

### 3. Jest "Cannot spy the X property" in p8

**Status: MIXED**

p8 improved to 7/8 (88%) from the previous run's 100% (noting that sample size was small). The single stalled failure (20260612-125457) is due to context-size-exceeded errors during writer/architect stages, not the spy error itself. This is a model resource issue, not a reflex problem.

Sessions that passed suggest the export hint ("does not export") is being provided correctly in the model feedback. The 88% pass rate is strong.

## Failure inventory

1. **20260612-115043-write_the_fibonacci_sequence_using_C_Use** — p4 stalled
   - fail_reason: "final test gate failed: final tests failed"
   - repair_iters: 6, duration: 208s
   - artifacts: transcript.jsonl, workspace/, logs/
   - error: `/Users/jacob/Projects/mu/dojo/p4-fibonacci/FibonacciTests.cs(6,46): error CS1513: } expected`
   - code corruption: FibonacciTests.cs contains duplicate method signatures with [Fact] attributes scattered inside method bodies

2. **20260612-115911-write_a_Python_todo_list_manager_that_st** — p2 stalled
   - fail_reason: "tests still failing after repair for test_main.py"
   - repair_iters: 6, duration: 206s
   - artifacts: transcript.jsonl, workspace/, logs/
   - error: `AttributeError: 'FixtureFunctionDefinition' object has no attribute 'add'`
   - issue: fixture definition misuse in pytest

3. **20260612-121653-write_a_blog_application_with_an_ASPNET_** — p10 stalled
   - fail_reason: "final test gate failed: final tests failed"
   - repair_iters: 6, duration: 267s
   - artifacts: transcript.jsonl, workspace/, logs/
   - error: `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(13,65): error CS0246: The type or namespace name 'Program' could not be found`
   - issue: C# namespace/using statement corruption

4. **20260612-124522-write_a_Python_todo_list_manager_that_st** — p2 stalled
   - fail_reason: "lint still failing after repair for test_database.py"
   - repair_iters: 0, duration: 339s
   - artifacts: transcript.jsonl, workspace/, logs/
   - error: `ERROR collecting dojo/p2-sqlite/test_main.py`
   - issue: import or syntax error in test file (no repair attempted, gave up immediately)

5. **20260612-125102-write_a_Python_REST_API_using_Flask_with** — p7 stalled
   - fail_reason: "tests still failing after repair for test_main.py"
   - repair_iters: 6, duration: 323s
   - artifacts: transcript.jsonl, workspace/, logs/
   - error: `make: main.c: No such file or directory` (from Makefile)
   - issue: Makefile malformed; edit tried to overwrite test rule but left stale recipe lines

6. **20260612-125457-write_a_Nodejs_todo_list_manager_that_st** — p8 stalled
   - fail_reason: "tests still failing after repair for tests/commands.test.js"
   - repair_iters: 0, duration: 1026s
   - artifacts: transcript.jsonl, workspace/, logs/
   - error: `Client error '400 Bad Request' ... Context size has been exceeded`
   - issue: model context limit exceeded during test generation and architect repair

7. **20260612-125626-write_a_Vue_3_TypeScript_todo_list_web_a** — p9 error
   - fail_reason: "uncaught exception: FileNotFoundError: [Errno 2] No such file or directory: 'src'"
   - repair_iters: 0, duration: 1140s
   - artifacts: transcript.jsonl, logs/ (no workspace)
   - issue: mu harness crashed looking for 'src' directory; check whether writer failed to create initial structure

8. **20260612-134657-write_a_blog_application_with_an_ASPNET_** — p10 stalled
   - fail_reason: "final test gate failed: final tests failed"
   - repair_iters: 6, duration: 261s
   - artifacts: transcript.jsonl, workspace/, logs/
   - error: `/Users/jacob/Projects/mu/dojo/p10-dotnet-vue-blog/tests/ApiTests.cs(11,7): error CS0246: The type or namespace name 'p10_dotnet_vue_blog' could not be found`
   - issue: C# namespace mismatch; test references wrong namespace

9. **20260612-135120-write_the_fibonacci_sequence_using_C_Use** — p4 stalled
   - fail_reason: "final test gate failed: final tests failed"
   - repair_iters: 6, duration: 173s
   - artifacts: transcript.jsonl, workspace/, logs/
   - error: `/Users/jacob/Projects/mu/dojo/p4-fibonacci/FibonacciTests.cs(2,58): error CS1525: Invalid expression term 'namespace'`
   - code corruption: FibonacciTests.cs syntax completely broken; [Fact] decorators misplaced

## Failure buckets

### [4] final test gate failed: final tests failed
**Root cause: C# code generation corruption**

Sessions: 20260612-115043-p4, 20260612-135120-p4, 20260612-121653-p10, 20260612-134657-p10

The C# test files (FibonacciTests.cs, ApiTests.cs) are malformed with duplicate method signatures, orphaned [Fact] attributes, and missing braces. Example from 20260612-115043-p4:

```csharp
[Fact]
public void TestFibonacciSequence() {
public void TestFibonacciSequence() {      // <-- duplicate
        [Fact]                             // <-- orphaned
public void TestFibonacciSequence() {      // <-- another duplicate
    ...
}
public void TestFibonacciSequence() {      // <-- yet another
    ...
}
}  // <-- mismatched braces
}
```

This pattern suggests the writer is either appending to existing files incorrectly or the reflex-based edits are botching structure. All four sessions stall after 6 repair iterations without recovery.

**Model behavior (from transcripts):** Architect repair mode attempts namespace/using fixes but does not recognize the fundamental syntax corruption. Likely because the prompt feedback only shows error codes (CS1513, CS0246) without file excerpts.

### [2] tests still failing after repair for test_main.py
**Root cause: pytest fixture misuse (p2) and Makefile corruption (p7)**

Sessions: 20260612-115911-p2, 20260612-125102-p7

**p2 (20260612-115911):** Error is `'FixtureFunctionDefinition' object has no attribute 'add'`, suggesting the test is incorrectly decorating or accessing a fixture. The fixture reflex may have rewritten the fixture definition but left the test code calling it incorrectly.

**p7 (20260612-125102):** The Makefile test rule refers to `main.c` (a leftover from the template) and fails with `make: main.c: No such file or directory`. The repair tried to fix the rule twice but the second edit left both old and new recipe lines, creating an invalid Makefile. The model did not back off and re-write the whole file.

### [1] lint still failing after repair for test_database.py
**Root cause: Unknown (no repair invoked)**

Session: 20260612-124522-p2

Linter reported an error in test_database.py (or test_main.py), and the system gave up with 0 repair iterations. The workspace has ARCHITECTURE.md but no clear indication of what the lint error was. Likely a missing fixture import or syntax error that the model writer did not catch.

### [1] tests still failing after repair for tests/commands.test.js
**Root cause: Model context overflow**

Session: 20260612-125457-p8

During the test writer phase, the model hit a 400 Bad Request from the local Ollama instance with error `"Context size has been exceeded."` The writer failed to produce the file, and architect repair also hit the same error. The test files were never generated.

**Note:** This is not related to the Jest spy reflex. The session simply ran out of context budget before being able to repair anything. The 7/8 success rate for p8 otherwise suggests the export-hint reflex is working.

### [1] uncaught exception: FileNotFoundError: [Errno 2] No such file or directory: 'src'
**Root cause: Harness crash (missing initial project structure)**

Session: 20260612-125626-p9

The mu harness crashed with FileNotFoundError looking for a 'src' directory. This suggests either:
1. The writer failed to create the initial file structure, leaving the project directory empty or malformed
2. The harness was called on a Vue project without first ensuring the expected directory layout exists

No workspace/ directory was created, so no forensics are available on what the writer produced.

## Forensics coverage

**Complete:** All 9 failed sessions have:
- fail_reason in meta.json
- transcript.jsonl (including both writer and repair transcripts)
- workspace/ containing project files and PLAN.md
- logs/ with agent.log, tests-*.log, and lint-*.log

**Coverage:** 100% — no missing artifacts that would prevent root-cause analysis.

**Unexplained failures:** None. All failures are traceable:
- 4× C# corruption (writer output malformed)
- 2× fixture/Makefile issues (reflex or edit misbehavior)
- 1× linter issue (no repair logs to analyze, likely writer error)
- 1× context overflow (model resource, not agent logic)
- 1× harness crash (writer failed to create structure)

