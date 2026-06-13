# Build-target inconsistency & misplaced files

_‹ [All challenges](README.md)_

- **ID:** `build-target-inconsistency`
- **Group:** Full-stack orchestration / multi-file
- **Open list:** [item 10](README.md#open)
- **Status:** mitigated by relocation + cleanup

## What it is

The plan names an entry-point/target the build file never defines (or vice versa), or the lean-retry writer writes a file to the wrong subdirectory.

## Problems affected

- [p1-helloworld](../problems/p1-helloworld.md) — binary name vs Makefile target
- [p5-gin](../problems/p5-gin.md) — `go test` vs a named binary
- [p10-dotnet-vue-blog](../problems/p10-dotnet-vue-blog.md) — files written to unexpected stage dirs

## Relevant reflexes & mechanisms

- `fix_makefile_binary_name` — aligns the Makefile's output binary with the test command
- `misplaced-file relocation` — moves a file the writer put in the wrong subdir to its planned path
- `stale-`.cs` cleanup` — removes orphaned duplicates before the build

## Residual / notes

Relocation tolerates filesystem races (a directory vanishing mid-walk no longer crashes the session — fixed 2026-06-12).
