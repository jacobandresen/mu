# C# generation artifacts

_‹ [All challenges](README.md)_

- **ID:** `csharp-generation-artifacts`
- **Group:** Degenerate / malformed generation
- **Open list:** [item 4](README.md#open)
- **Status:** each shape covered by a named reflex

## What it is

C#-specific malformations: top-level statements before a namespace (CS1529), verbatim-string `\"` escaping (CS1056), stray keyword prefixes like `tnamespace` (CS1513), lambda chains closed with `{){` (CS1026), and the same method-signature opener stuttered several times before the body.

## Problems affected

- [p4-fibonacci](../problems/p4-fibonacci.md) — stuttered `public void TestX() {` openers
- [p14-fullstack-js-blog](../problems/p14-fullstack-js-blog.md) — mixed artifacts in generated controllers/tests
- [p15-dotnet-vue-blog](../problems/p15-dotnet-vue-blog.md) — stuttered `public void TestX() {` openers, mixed artifacts in generated controllers/tests

## Relevant reflexes & mechanisms

- [`fix_csharp_lambda_brace_confusion`](../../src/mu/reflexes/csharp/fix_csharp_lambda_brace_confusion.py) — replaces `{){` with `))`
- [`fix_csharp_keyword_prefix_artifacts`](../../src/mu/reflexes/csharp/fix_csharp_keyword_prefix_artifacts.py) — strips a stray char fused to a keyword
- [`fix_csharp_verbatim_string_escape`](../../src/mu/reflexes/csharp/fix_csharp_verbatim_string_escape.py) — drops the `@` so `\"` is valid
- [`fix_csharp_consecutive_duplicate_signatures`](../../src/mu/reflexes/csharp/fix_csharp_consecutive_duplicate_signatures.py) — collapses stuttered duplicate signature openers

## Residual / notes

Stuttered openers with real bodies between (CS0111) are left for the compiler — deleting code is not a reflex's call.
