# Dojo

The dojo stress-tests **mu** by driving a guest model through a fixed problem set
(P1–P7) and recording where the autonomous loop breaks. Problem prompts live in
[PRACTICE.md](docs/PRACTICE.md); model selection and tuning in [MODELS.md](docs/MODELS.md)
and [TUNING.md](docs/TUNING.md); the design rationale in
[HARNESS_ENGINEERING.md](docs/HARNESS_ENGINEERING.md).

> **Honest-harness principle.** Fixes must be *language-class generic*, never
> pattern-matched to one dojo problem. A sensor that rewrites "SDL3→SDL2" or
> injects a known `.csproj` measures the harness author's knowledge of the test,
> not the agent. The Go-era sensor zoo (v0.3–v0.6) was deleted for this reason.
> Every fix below uses a real oracle — the compiler, the package manager, the
> SDK — to name the problem, so it generalises beyond P1–P7.

---

## Dojo runs

Result from the latest dojo runs are stored in the `dojo/` directory. 

They are not committed git. The results will be cleaned before each run.

---

## Top challenge 

The top challenge from the latest run will be noted in this file.
(Where to push next)

---

<a id="where-to-push-next"></a>
## Where to push next






