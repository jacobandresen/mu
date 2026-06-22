"""Dependency build order (design criterion: build bottom-up).

`plan.build_order` reorders a plan's tasks so a module that is *called by* another
is built first, manifests come first, and tests come last — cascade control, so an
early mistake can't compound. Pure function, no model: runs in CI.
"""

from pathlib import Path

from mu.plan import Task, build_rank, build_order, reorder_plan, parse


def _ranks(paths_descs):
    return [build_rank(Task(p, d)) for p, d in paths_descs]


def _order(paths):
    return [t.file_path for t in build_order([Task(p) for p in paths])]


# ── per-file layer classification ─────────────────────────────────────────────

def test_manifests_rank_zero():
    for f in ('package.json', 'Cargo.toml', 'go.mod', 'pyproject.toml',
              'requirements.txt', 'Blog.csproj', 'tsconfig.json',
              'frontend/vite.config.ts', 'Makefile', 'CMakeLists.txt'):
        assert build_rank(Task(f)) == 0, f


def test_headers_and_decls_rank_one():
    assert build_rank(Task('src/list.h')) == 1
    assert build_rank(Task('include/widget.hpp')) == 1
    assert build_rank(Task('backend/Models/Post.cs', 'the Post model')) == 1
    assert build_rank(Task('backend/Data/BlogContext.cs')) == 1   # *context*
    assert build_rank(Task('models.py')) == 1
    assert build_rank(Task('types.ts')) == 1


def test_core_modules_rank_two():
    assert build_rank(Task('src/parser.c')) == 2
    assert build_rank(Task('frontend/src/components/PostList.vue')) == 2
    assert build_rank(Task('utils.py')) == 2


def test_wiring_and_entrypoints_rank_three():
    for f in ('main.c', 'backend/Program.cs', 'frontend/src/App.vue',
              'frontend/src/main.ts', 'app.py', 'server.js',
              'controllers/user_controller.cs', 'routes/posts.ts'):
        assert build_rank(Task(f)) == 3, f


def test_tests_rank_four():
    for f in ('tests/test_app.py', 'test_main.py', 'src/foo_test.go',
              'backend.Tests/PostsApiTests.cs', 'frontend/src/App.test.ts',
              'src/widget.spec.ts'):
        assert build_rank(Task(f)) == 4, f


# ── whole-plan ordering ───────────────────────────────────────────────────────

def test_c_with_header_orders_header_before_impl_before_main():
    order = _order(['main.c', 'list.c', 'list.h', 'Makefile'])
    assert order.index('Makefile') < order.index('list.h')
    assert order.index('list.h') < order.index('list.c')      # callee header first
    assert order.index('list.c') < order.index('main.c')      # impl before caller
    assert order[-1] != 'list.h'                              # main last of the three


def test_python_orders_manifest_model_app_test():
    order = _order(['test_app.py', 'app.py', 'models.py', 'requirements.txt'])
    assert order == ['requirements.txt', 'models.py', 'app.py', 'test_app.py']


def test_p10_fullstack_bottom_up():
    paths = [
        'backend/Program.cs', 'backend/Models/Post.cs', 'backend/Data/BlogContext.cs',
        'backend/Blog.csproj', 'backend.Tests/PostsApiTests.cs',
        'frontend/package.json', 'frontend/vite.config.ts',
        'frontend/src/App.vue', 'frontend/src/components/PostList.vue',
        'frontend/src/App.test.ts', 'Makefile',
    ]
    order = _order(paths)
    # manifests first, then the model/context, then components, then app wiring,
    # then the two tests last.
    assert order.index('backend/Blog.csproj') < order.index('backend/Models/Post.cs')
    assert order.index('backend/Models/Post.cs') < order.index('backend/Program.cs')
    assert order.index('backend/Data/BlogContext.cs') < order.index('backend/Program.cs')
    assert order.index('frontend/src/components/PostList.vue') < order.index('frontend/src/App.vue')
    assert order.index('backend/Program.cs') < order.index('backend.Tests/PostsApiTests.cs')
    assert {order[-1], order[-2]} == {'backend.Tests/PostsApiTests.cs', 'frontend/src/App.test.ts'}


def test_stable_within_layer():
    # two core modules at the same rank keep planner order
    order = _order(['beta.py', 'alpha.py'])
    assert order == ['beta.py', 'alpha.py']


def test_pure_does_not_mutate_input():
    tasks = [Task('main.c'), Task('lib.h')]
    snapshot = list(tasks)
    build_order(tasks)
    assert tasks == snapshot


# ── reorder_plan: the PLAN.md rewrite ─────────────────────────────────────────

_PLAN = """## Summary
A C program.

## Files
- [ ] main.c — entry point, calls list
- [ ] list.c — linked list implementation
- [ ] list.h — linked list interface
- [x] Makefile — build rules

## Test Command
make test
"""


def test_reorder_plan_rewrites_files_bottom_up(tmp_path):
    f = tmp_path / 'PLAN.md'
    f.write_text(_PLAN)
    order = reorder_plan(str(f))
    assert order == ['Makefile', 'list.h', 'list.c', 'main.c']
    paths = [t.file_path for t in parse(str(f)).tasks]
    assert paths == ['Makefile', 'list.h', 'list.c', 'main.c']


def test_reorder_plan_preserves_status_and_description(tmp_path):
    f = tmp_path / 'PLAN.md'
    f.write_text(_PLAN)
    reorder_plan(str(f))
    text = f.read_text()
    assert '- [x] Makefile — build rules' in text          # done-state kept
    assert '- [ ] main.c — entry point, calls list' in text  # description kept
    # other sections untouched
    assert '## Summary' in text and '## Test Command' in text and 'make test' in text


def test_reorder_plan_idempotent(tmp_path):
    f = tmp_path / 'PLAN.md'
    f.write_text(_PLAN)
    reorder_plan(str(f))
    once = f.read_text()
    assert reorder_plan(str(f)) == []      # already ordered → no-op
    assert f.read_text() == once           # byte-identical


def test_reorder_plan_noop_without_files_section(tmp_path):
    f = tmp_path / 'PLAN.md'
    f.write_text("## Summary\njust prose, no files\n")
    assert reorder_plan(str(f)) == []


def test_reorder_plan_keeps_interspersed_nontask_lines(tmp_path):
    f = tmp_path / 'PLAN.md'
    f.write_text("## Files\n- [ ] main.c — app\n\n- [ ] util.h — header\n")
    reorder_plan(str(f))
    lines = f.read_text().splitlines()
    assert lines[0] == '## Files'
    assert lines[2] == ''                  # the blank line stays in its slot
    # the header (rank 1) now precedes main.c (rank 3)
    body = [l for l in lines if l.startswith('- [')]
    assert body == ['- [ ] util.h — header', '- [ ] main.c — app']
