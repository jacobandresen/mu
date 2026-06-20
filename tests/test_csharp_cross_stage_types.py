"""Step 0.3 / S2 — cross-stage type-ownership reflexes.

`fix_csharp_cross_stage_duplicate_types` keeps the backend-owned definition of a
shared type and deletes the copy a second project (the test project) re-declared
(CS0101); it must never touch a uniquely-named type, and must be idempotent.
`fix_csharp_public_signature_accessibility` raises an `internal` type exposed by a
`public` signature to `public` (CS0053).
"""
from mu.reflexes.csharp import (fix_csharp_cross_stage_duplicate_types,
                                fix_csharp_public_signature_accessibility)


def _mk(tmp_path, rel, text):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


POST_BACKEND = "namespace Blog;\npublic class Post\n{\n    public int Id { get; set; }\n}\n"
POST_DUP = "namespace Blog;\npublic class Post\n{\n    public int Id { get; set; }\n}\n"


def test_removes_cross_project_duplicate_keeps_backend(tmp_path):
    backend = _mk(tmp_path, "backend/Models/Post.cs", POST_BACKEND)
    test = _mk(tmp_path, "backend.Tests/PostsApiTests.cs",
               "namespace Blog.Tests;\n" + POST_DUP +
               "\npublic class PostsApiTests\n{\n    [Fact] public void T() {}\n}\n")
    assert fix_csharp_cross_stage_duplicate_types(str(tmp_path)) is True
    # backend definition survives; the test project's duplicate Post is gone
    # (use "class Post\n" — "class Post" is a substring of "class PostsApiTests")
    assert "class Post\n" in backend.read_text()
    t = test.read_text()
    assert "class Post\n" not in t
    assert "class PostsApiTests" in t        # the test's own unique type is kept


def test_ownership_prefers_backend_even_when_test_sorts_first(tmp_path):
    # 'backend.Tests/' sorts BEFORE 'backend/' ('.' < '/'); ownership must still
    # land on the non-test file, not the lexicographically-first one.
    backend = _mk(tmp_path, "backend/Post.cs", POST_BACKEND)
    test = _mk(tmp_path, "backend.Tests/Dup.cs", POST_DUP)
    fix_csharp_cross_stage_duplicate_types(str(tmp_path))
    assert "class Post" in backend.read_text()
    assert "class Post" not in test.read_text()


def test_unique_named_type_untouched(tmp_path):
    a = _mk(tmp_path, "backend/A.cs", "public class Alpha { }\n")
    b = _mk(tmp_path, "backend.Tests/B.cs", "public class Beta { }\n")
    assert fix_csharp_cross_stage_duplicate_types(str(tmp_path)) is False
    assert "class Alpha" in a.read_text()
    assert "class Beta" in b.read_text()


def test_same_named_distinct_namespaces_single_run_is_noop(tmp_path):
    # only one definition of each -> nothing to remove
    _mk(tmp_path, "backend/Post.cs", POST_BACKEND)
    assert fix_csharp_cross_stage_duplicate_types(str(tmp_path)) is False


def test_idempotent(tmp_path):
    _mk(tmp_path, "backend/Models/Post.cs", POST_BACKEND)
    _mk(tmp_path, "backend.Tests/Dup.cs", POST_DUP)
    assert fix_csharp_cross_stage_duplicate_types(str(tmp_path)) is True
    assert fix_csharp_cross_stage_duplicate_types(str(tmp_path)) is False  # stable


def test_single_file_project_noop(tmp_path):
    _mk(tmp_path, "Program.cs", "public class Post { }\n")
    assert fix_csharp_cross_stage_duplicate_types(str(tmp_path)) is False


# --- CS0053 accessibility ------------------------------------------------------

def test_raises_internal_type_exposed_by_public_signature(tmp_path):
    model = _mk(tmp_path, "backend/Post.cs", "internal class Post { public int Id; }\n")
    _mk(tmp_path, "backend/Api.cs",
        "public class Api {\n    public Post Get() => new Post();\n}\n")
    assert fix_csharp_public_signature_accessibility(str(tmp_path)) is True
    assert "public class Post" in model.read_text()
    assert "internal class Post" not in model.read_text()


def test_internal_type_not_exposed_is_left_alone(tmp_path):
    helper = _mk(tmp_path, "backend/Helper.cs", "internal class Helper { }\n")
    _mk(tmp_path, "backend/Api.cs", "public class Api {\n    public int Get() => 1;\n}\n")
    assert fix_csharp_public_signature_accessibility(str(tmp_path)) is False
    assert "internal class Helper" in helper.read_text()


def test_accessibility_idempotent(tmp_path):
    _mk(tmp_path, "backend/Post.cs", "internal record Post(int Id);\n")
    _mk(tmp_path, "backend/Api.cs",
        "public class Api\n{\n    public Post P() => default!;\n}\n")
    first = fix_csharp_public_signature_accessibility(str(tmp_path))
    second = fix_csharp_public_signature_accessibility(str(tmp_path))
    assert first is True and second is False
